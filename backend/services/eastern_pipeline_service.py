"""
Eastern music multi-section pipeline orchestrator.

Pipeline:
  1. Demucs separation → vocals stem
  2. CREPE pitch extraction
  3. Frame-to-note segmentation
  4. Multi-cue section detection
  5. Per-section maqam + tonic + tempo analysis
  6. Adjacent section merging (same maqam, same tonic, similar BPM)
  7. MusicXML + MIDI export with rehearsal marks and quarter-tone accidentals
"""

from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from models.schema import (
    EasternPipelineResponse,
    NoteEvent,
    SectionAnalysis,
    SectionBoundary,
)
from shared.logger import logger
from services.crepe_service import extract_pitch
from services.demucs_service import separate_audio
from services.eastern_music_service import detect_maqam, detect_quarter_tones
from services.sheet_music_service import (
    export_midi_from_score,
    export_musicxml,
    notes_to_music21_score_with_sections,
)
from utils.note_segmentation import segment_notes
from utils.section_detection import detect_sections
from utils.tempo_analysis import detect_comprehensive_tempo


_BPM_MERGE_THRESHOLD = 0.20
_OUTPUT_DIR = "tmp/pipeline"


def _notes_in_section(
    notes: List[NoteEvent], boundary: SectionBoundary
) -> List[Dict[str, Any]]:
    """Extract notes within a time window and return as dicts (skips rests)."""
    result = []
    for n in notes:
        if n.pitch == 0:
            continue
        if boundary.start_time <= n.start_time_s < boundary.end_time:
            result.append(
                {
                    "pitch": n.pitch,
                    "midi_continuous": n.midi_continuous,
                    "start_time_s": n.start_time_s,
                    "duration_s": n.duration_s,
                    "cents_dev": n.cents_dev,
                    "is_quarter": n.is_quarter,
                    "frequency": n.frequency,
                    "amplitude": n.amplitude,
                }
            )
    return result


def _extract_audio_segment(audio_bytes: bytes, start_s: float, end_s: float) -> bytes:
    """Extract a segment from raw audio bytes using librosa/soundfile."""
    import io
    import soundfile as sf

    y, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if len(y.shape) > 1:
        y = y.mean(axis=1)

    start_idx = int(start_s * sr)
    end_idx = int(end_s * sr)
    start_idx = max(0, start_idx)
    end_idx = min(len(y), end_idx)

    if end_idx <= start_idx:
        return b""

    segment = y[start_idx:end_idx]

    buf = io.BytesIO()
    sf.write(buf, segment, sr, format="WAV")
    return buf.getvalue()


def _merge_adjacent_sections(
    sections: List[SectionAnalysis],
) -> List[SectionAnalysis]:
    """Merge sections with same maqam, same tonic, and BPM within 20%."""
    if len(sections) < 2:
        return sections

    merged: List[SectionAnalysis] = []
    current = sections[0]

    for next_sec in sections[1:]:
        same_maqam = current.maqam == next_sec.maqam
        same_tonic = current.tonic == next_sec.tonic
        bpm_diff = abs(current.bpm - next_sec.bpm) / min(current.bpm, next_sec.bpm)
        should_merge = same_maqam and same_tonic and bpm_diff <= _BPM_MERGE_THRESHOLD

        if should_merge:
            current = SectionAnalysis(
                label=f"{current.label}-{next_sec.label}",
                start_time=current.start_time,
                end_time=next_sec.end_time,
                maqam=current.maqam,
                tonic=current.tonic,
                confidence=max(current.confidence, next_sec.confidence),
                bpm=(current.bpm + next_sec.bpm) / 2.0,
                notes=current.notes + next_sec.notes,
            )
        else:
            merged.append(current)
            current = next_sec

    merged.append(current)
    return merged


def run_eastern_pipeline(
    audio_bytes: bytes, job_id: str = ""
) -> EasternPipelineResponse:
    """
    Run the complete eastern music pipeline.

    Args:
        audio_bytes: Raw audio file bytes (MP3, WAV, FLAC, M4A).
        job_id: Optional job identifier for output filenames. If empty, one is
                generated.

    Returns:
        EasternPipelineResponse with sections and file paths.
    """
    logger.info("Starting eastern music pipeline...")

    # Step 1: Demucs separation → get vocals stem
    logger.info("Step 1/7: Separating audio with Demucs...")
    stems = separate_audio(audio_bytes, "tmp/stems")
    vocals_path = Path(stems["vocals"])
    if not vocals_path.exists():
        raise RuntimeError("Vocals stem not found after separation")
    vocals_bytes = vocals_path.read_bytes()

    # Auto-detect: if vocals stem is near-silent, use 'other' stem instead
    import io
    import soundfile as sf

    y_vocals, _ = sf.read(io.BytesIO(vocals_bytes), dtype="float32")
    rms = float(np.sqrt(np.mean(y_vocals**2)))
    if rms < 0.01:
        logger.warning(f"Vocals stem near-silent (RMS={rms:.4f}), using 'other' stem")
        vocals_bytes = Path(stems["other"]).read_bytes()
    else:
        logger.info(f"  Vocals stem extracted (RMS={rms:.4f})")

    # Step 2: CREPE pitch extraction
    logger.info("Step 2/7: Extracting pitch with CREPE...")
    crepe_result = extract_pitch(
        vocals_bytes, confidence_threshold=0.2, step_size_ms=10
    )
    logger.info(
        f"  Extracted {crepe_result['frames_total']} frames "
        f"({crepe_result['frames_kept']} kept)"
    )

    # Step 3: Frame-to-note segmentation
    logger.info("Step 3/7: Segmenting frames into notes...")
    notes = segment_notes(crepe_result)
    logger.info(f"  Segmented into {len(notes)} notes")

    if not notes:
        return EasternPipelineResponse(
            sections=[],
            musicxml_filename=None,
            midi_filename=None,
            total_duration_s=0.0,
        )

    total_duration = notes[-1].start_time_s + notes[-1].duration_s

    # Step 4: Multi-cue section detection
    logger.info("Step 4/7: Detecting sections...")
    boundaries = detect_sections(notes, vocals_bytes)
    logger.info(f"  Detected {len(boundaries)} section(s)")

    # Step 5: Per-section analysis
    logger.info("Step 5/7: Analyzing each section...")
    section_analyses: List[SectionAnalysis] = []

    for i, boundary in enumerate(boundaries):
        section_notes_dicts = _notes_in_section(notes, boundary)
        if not section_notes_dicts:
            logger.warning(f"  Section {i}: empty, skipping")
            continue

        section_audio = _extract_audio_segment(
            vocals_bytes, boundary.start_time, boundary.end_time
        )

        # Maqam detection
        maqam, tonic, maqam_confidence = detect_maqam(section_notes_dicts)
        section_notes_dicts = detect_quarter_tones(
            section_notes_dicts,
            [n["frequency"] for n in section_notes_dicts],
        )

        # Tempo detection
        if section_audio:
            tempo_info = detect_comprehensive_tempo(section_audio)
            bpm = tempo_info.get("bpm", 120.0)
        else:
            bpm = 120.0

        # Build NoteEvent list
        section_note_events = [
            NoteEvent(
                start_time_s=n["start_time_s"],
                duration_s=n["duration_s"],
                pitch=n["pitch"],
                midi_continuous=n.get("midi_continuous", float(n["pitch"])),
                cents_dev=n.get("cents_dev", 0),
                is_quarter=n.get("is_quarter", False),
                frequency=n.get("frequency", 0.0),
                amplitude=n.get("amplitude", 0.5),
            )
            for n in section_notes_dicts
        ]

        section = SectionAnalysis(
            label=f"Section {i + 1}",
            start_time=boundary.start_time,
            end_time=boundary.end_time,
            maqam=maqam,
            tonic=tonic,
            confidence=maqam_confidence,
            bpm=round(bpm, 1),
            notes=section_note_events,
        )
        section_analyses.append(section)

        logger.info(
            f"  Section {i + 1}: {maqam} (tonic={tonic}, "
            f"confidence={maqam_confidence:.2f}, bpm={bpm:.1f}, "
            f"{len(section_note_events)} notes)"
        )

    # Step 6: Merge adjacent sections
    logger.info("Step 6/7: Merging similar sections...")
    merged = _merge_adjacent_sections(section_analyses)
    logger.info(f"  Merged {len(section_analyses)} → {len(merged)} section(s)")

    # Step 7: MusicXML + MIDI export
    logger.info("Step 7/7: Exporting sheet music...")
    if not job_id:
        import uuid

        job_id = str(uuid.uuid4())[:8]
    output_dir = Path(_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    section_dicts = []
    for sec in merged:
        section_dicts.append(
            {
                "maqam": sec.maqam,
                "bpm": sec.bpm,
                "notes": [
                    {
                        "pitch": n.pitch,
                        "start_time_s": n.start_time_s,
                        "duration_s": n.duration_s,
                        "amplitude": n.amplitude,
                        "is_quarter": n.is_quarter,
                        "cents_dev": n.cents_dev,
                        "type": "rest" if n.pitch == 0 else None,
                    }
                    for n in sec.notes
                ],
            }
        )

    score, metadata = notes_to_music21_score_with_sections(
        section_dicts, title="Eastern Music Transcription"
    )

    musicxml_path = export_musicxml(
        score, str(output_dir / f"eastern_{job_id}.musicxml")
    )
    midi_path = export_midi_from_score(score, str(output_dir / f"eastern_{job_id}.mid"))

    musicxml_filename = Path(musicxml_path).name
    midi_filename = Path(midi_path).name

    logger.info(
        f"Pipeline complete: {len(merged)} section(s), "
        f"MusicXML={musicxml_filename}, MIDI={midi_filename}"
    )

    return EasternPipelineResponse(
        sections=merged,
        musicxml_filename=musicxml_filename,
        midi_filename=midi_filename,
        total_duration_s=round(total_duration, 2),
    )
