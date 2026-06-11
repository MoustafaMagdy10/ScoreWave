"""
Integration test for the eastern music pipeline using synthetic audio.

Generates a 2-section audio file with known characteristics:
  Section 1: D4, E-half, F4, G4 (repeated) — has quarter-tone
  Silence gap: 1s
  Section 2: D4, F4, G4, A4 (repeated) — no quarter-tones

Runs the full pipeline (skipping Demucs) and validates:
  - Section detection splits at the silence gap (≥2 sections)
  - Each section produces valid maqam/tonic
  - MusicXML output has rehearsal marks
"""

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

from test_audio_generator import (
    _pack_as_wav,
    generate_sine_wave_bytes,
    WESTERN_NOTES,
    EASTERN_NOTES,
)

from services.crepe_service import extract_pitch
from services.eastern_music_service import detect_maqam, detect_quarter_tones
from services.sheet_music_service import (
    export_musicxml,
    notes_to_music21_score_with_sections,
)
from utils.note_segmentation import segment_notes
from utils.section_detection import detect_sections
from utils.tempo_analysis import detect_comprehensive_tempo


SAMPLE_RATE = 44100
NOTE_DURATION = 0.25
SILENCE_DURATION = 1.0


def _build_test_audio() -> bytes:
    """
    Build a 2-section WAV audio file.

    Section 1 (0-8s): D4, E-half, F4, G4 (repeated 8×) — quarter-tone present
    Silence   (8-9s): 1s gap
    Section 2 (9-17s): D4, F4, G4, A4 (repeated 8×) — no quarter-tones
    """
    section1 = [
        (WESTERN_NOTES["D4"], "D4"),
        (EASTERN_NOTES["E-half"], "E-half"),
        (WESTERN_NOTES["F4"], "F4"),
        (WESTERN_NOTES["G4"], "G4"),
    ] * 8

    section2 = [
        (WESTERN_NOTES["D4"], "D4"),
        (WESTERN_NOTES["F4"], "F4"),
        (WESTERN_NOTES["G4"], "G4"),
        (WESTERN_NOTES["A4"], "A4"),
    ] * 8

    all_samples = np.array([], dtype=np.int16)

    for freq, _name in section1:
        chunk = generate_sine_wave_bytes(freq, NOTE_DURATION, SAMPLE_RATE)
        raw = chunk[44:]
        all_samples = np.concatenate([all_samples, np.frombuffer(raw, dtype=np.int16)])

    silence = np.zeros(int(SAMPLE_RATE * SILENCE_DURATION), dtype=np.int16)
    all_samples = np.concatenate([all_samples, silence])

    for freq, _name in section2:
        chunk = generate_sine_wave_bytes(freq, NOTE_DURATION, SAMPLE_RATE)
        raw = chunk[44:]
        all_samples = np.concatenate([all_samples, np.frombuffer(raw, dtype=np.int16)])

    return _pack_as_wav(all_samples, SAMPLE_RATE, 1)


def _notes_in_window(notes, start_s, end_s):
    """Extract notes within a time window as dicts."""
    result = []
    for n in notes:
        if start_s <= n.start_time_s < end_s:
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
    """Slice raw audio bytes by time."""
    import io
    import soundfile as sf

    y, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    if len(y.shape) > 1:
        y = y.mean(axis=1)
    si = max(0, int(start_s * sr))
    ei = min(len(y), int(end_s * sr))
    if ei <= si:
        return b""
    buf = io.BytesIO()
    sf.write(buf, y[si:ei], sr, format="WAV")
    return buf.getvalue()


# =============================================================================
# Tests
# =============================================================================


class TestEasternPipelineIntegration:
    """End-to-end integration test for the eastern music pipeline."""

    @pytest.fixture(scope="class")
    def pipeline_result(self) -> Dict[str, Any]:
        audio = _build_test_audio()

        crepe = extract_pitch(audio, confidence_threshold=0.4, step_size_ms=10)
        notes = segment_notes(crepe)
        boundaries = detect_sections(notes, audio)

        sections = []
        for i, b in enumerate(boundaries):
            sec_notes = _notes_in_window(notes, b.start_time, b.end_time)
            if not sec_notes:
                continue
            sec_audio = _extract_audio_segment(audio, b.start_time, b.end_time)
            sec_notes = detect_quarter_tones(
                sec_notes, [n["frequency"] for n in sec_notes]
            )
            maqam, tonic, maqam_conf = detect_maqam(sec_notes)
            bpm = 120.0
            if sec_audio:
                bpm = detect_comprehensive_tempo(sec_audio).get("bpm", 120.0)

            sections.append(
                {
                    "index": i + 1,
                    "start": b.start_time,
                    "end": b.end_time,
                    "maqam": maqam,
                    "tonic": tonic,
                    "confidence": maqam_conf,
                    "bpm": bpm,
                    "note_count": len(sec_notes),
                    "quarter_count": sum(1 for n in sec_notes if n.get("is_quarter")),
                }
            )

        section_dicts_for_score = []
        for b in boundaries:
            sec_notes = _notes_in_window(notes, b.start_time, b.end_time)
            if sec_notes:
                section_dicts_for_score.append(
                    {
                        "maqam": "Section",
                        "bpm": 120.0,
                        "notes": sec_notes,
                    }
                )

        score, _md = notes_to_music21_score_with_sections(
            section_dicts_for_score, title="Integration Test"
        )

        import shutil
        import tempfile

        tmp = tempfile.mkdtemp()
        xml_path = str(Path(tmp) / "test.musicxml")
        export_musicxml(score, xml_path)
        with open(xml_path) as f:
            xml_content = f.read()
        shutil.rmtree(tmp)

        return {
            "notes": notes,
            "boundaries": boundaries,
            "sections": sections,
            "xml_content": xml_content,
        }

    # ── Section detection ────────────────────────────────────────────────

    def test_detects_at_least_two_sections(self, pipeline_result):
        """1s silence gap should split audio into ≥2 sections."""
        sections = pipeline_result["sections"]
        assert len(sections) >= 2, (
            f"Expected ≥2 sections, got {len(sections)}: "
            f"{[(s['maqam'], s['start'], s['end']) for s in sections]}"
        )

    def test_section_boundaries_cover_audio(self, pipeline_result):
        """Sections should span the full audio duration."""
        sections = pipeline_result["sections"]
        assert sections[0]["start"] == pytest.approx(0.0, abs=0.1)
        assert sections[-1]["end"] == pytest.approx(17.0, abs=0.5)

    # ── Maqam detection ──────────────────────────────────────────────────

    def test_each_section_has_maqam(self, pipeline_result):
        """Every detected section should have a recognized maqam."""
        for s in pipeline_result["sections"]:
            assert s["maqam"] != "Unknown", f"Section {s['index']} has unknown maqam"

    def test_each_section_has_reasonable_confidence(self, pipeline_result):
        """Maqam confidence should be above zero."""
        for s in pipeline_result["sections"]:
            assert s["confidence"] > 0.0, f"Section {s['index']} has zero confidence"

    # ── Quarter-tones ────────────────────────────────────────────────────

    def test_section1_has_quarter_tones(self, pipeline_result):
        """Section 1 (with E-half) should have some quarter-tone notes."""
        s1 = pipeline_result["sections"][0]
        assert s1["quarter_count"] > 0, (
            f"Section 1: expected quarter-tones, got 0 out of {s1['note_count']} notes"
        )

    def test_section1_quarter_ratio(self, pipeline_result):
        """At least 10% of section 1 notes should be flagged as quarter-tones."""
        s1 = pipeline_result["sections"][0]
        ratio = s1["quarter_count"] / max(s1["note_count"], 1)
        assert ratio >= 0.1, (
            f"Section 1: only {s1['quarter_count']}/{s1['note_count']} "
            f"({ratio:.1%}) quarter-tone notes"
        )

    def test_section1_tonic_in_midi_range(self, pipeline_result):
        """Section 1 tonic should be a valid MIDI note (>20, excludes rest=0)."""
        s1 = pipeline_result["sections"][0]
        assert s1["tonic"] > 20, (
            f"Section 1 tonic {s1['tonic']} should be > 20 (got 0 from rest notes)"
        )

    # ── MusicXML output ──────────────────────────────────────────────────

    def test_musicxml_contains_section_label(self, pipeline_result):
        """MusicXML should contain section labels (<words> from TextExpression)."""
        xml = pipeline_result["xml_content"]
        assert "<words>" in xml or "Section" in xml, (
            "Expected section label in MusicXML"
        )

    def test_musicxml_contains_multiple_measures(self, pipeline_result):
        """MusicXML should have more than one measure."""
        xml = pipeline_result["xml_content"]
        measure_count = xml.count("<measure ")
        assert measure_count > 1, f"Expected >1 measure, got {measure_count}"
