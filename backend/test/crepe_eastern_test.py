"""
pytest tests for CREPE eastern/maqam quarter-tone detection.

Tests a Bayati-like scale: D4 → E-half → F4 → G4

The E-half (320.2 Hz) sits at MIDI 63.5 — exactly between D#4 and E4.
CREPE may snap to either neighbor. Both are correct.
The real signal: is_quarter flag must be ≥60% of voiced frames.
"""

import pytest
import numpy as np
from test_audio_generator import (
    generate_sine_wave_bytes,
    _pack_as_wav,
    WESTERN_NOTES,
    EASTERN_NOTES,
)
from services.crepe_service import extract_pitch


# =============================================================================
# Helpers
# =============================================================================

NOTE_DURATION = 2.5
SAMPLE_RATE = 44100


def _analyze_window(note_details, time_array, start, end):
    frames = []
    for i in range(len(time_array)):
        if start <= time_array[i] < end:
            frames.append(note_details[i])

    if not frames:
        return {"error": f"No frames in [{start}, {end})"}

    voiced = [f for f in frames if f["note"] != "Rest"]
    if not voiced:
        return {"error": "All frames silent"}

    votes = {}
    for f in voiced:
        votes[f["note"]] = votes.get(f["note"], 0) + 1

    most_common = max(votes, key=votes.get)
    avg_cents = sum(f["cents_dev"] for f in voiced) / len(voiced)
    quarter_count = sum(1 for f in voiced if f["is_quarter"])
    quarter_pct = quarter_count / len(voiced) * 100.0

    return {
        "most_common_note": most_common,
        "avg_cents_dev": round(avg_cents, 1),
        "quarter_count": quarter_count,
        "quarter_pct": round(quarter_pct, 1),
        "voiced_count": len(voiced),
        "vote_breakdown": votes,
    }


def check_quarter_tone_segment(analysis):
    """
    Validate a quarter-tone segment.

    Checks (in order):
      1. is_quarter flag on ≥60% of voiced frames (the real signal)
      2. Note is a valid neighbor (D#4, Eb4, or E4)

    avg_cents_dev is NOT checked — it's unreliable when CREPE splits
    votes between two adjacent semitones with opposite polarity (+50 and -50),
    which cancel out in the average.
    """
    detected = analysis["most_common_note"]
    quarter_pct = analysis["quarter_pct"]

    if quarter_pct < 60.0:
        return False, f"only {quarter_pct:.0f}% quarter-tone frames (need ≥60%)"

    valid = {"D#4", "Eb4", "E4"}
    if detected not in valid:
        return False, f"detected '{detected}', expected D#4 or E4"

    return True, f"OK: snapped to {detected}, quarter={quarter_pct:.0f}%"


def _build_test_audio():
    segments = [
        {"label": "D4", "freq": WESTERN_NOTES["D4"], "is_quarter": False},
        {"label": "E-half", "freq": EASTERN_NOTES["E-half"], "is_quarter": True},
        {"label": "F4", "freq": WESTERN_NOTES["F4"], "is_quarter": False},
        {"label": "G4", "freq": WESTERN_NOTES["G4"], "is_quarter": False},
    ]

    all_samples = np.array([], dtype=np.int16)
    for seg in segments:
        chunk = generate_sine_wave_bytes(seg["freq"], NOTE_DURATION, SAMPLE_RATE)
        raw = chunk[44:]
        samples = np.frombuffer(raw, dtype=np.int16)
        all_samples = np.concatenate([all_samples, samples])

    wav = _pack_as_wav(all_samples, SAMPLE_RATE, 1)

    expected = []
    for i, seg in enumerate(segments):
        expected.append(
            {
                "label": seg["label"],
                "is_quarter": seg["is_quarter"],
                "expected_note": None if seg["is_quarter"] else seg["label"],
                "start": i * NOTE_DURATION,
                "end": (i + 1) * NOTE_DURATION,
            }
        )

    return wav, expected


# =============================================================================
# Fixture (module-scoped — extract_pitch runs once per file)
# =============================================================================


@pytest.fixture(scope="module")
def crepe_result():
    wav_bytes, _expected = _build_test_audio()
    result = extract_pitch(wav_bytes, confidence_threshold=0.4, step_size_ms=10)
    return result, _expected


# =============================================================================
# Western segment tests (strict)
# =============================================================================


def test_d4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 0.0, 2.5)
    assert a["most_common_note"] == "D4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 10.0, f"{a['quarter_pct']:.0f}% quarter frames"


def test_f4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 5.0, 7.5)
    assert a["most_common_note"] == "F4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 10.0, f"{a['quarter_pct']:.0f}% quarter frames"


def test_g4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 7.5, 10.0)
    assert a["most_common_note"] == "G4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 10.0, f"{a['quarter_pct']:.0f}% quarter frames"


# =============================================================================
# Quarter-tone segment test (flexible)
# =============================================================================


def test_ehalf_quarter_tone_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 2.5, 5.0)
    passed, msg = check_quarter_tone_segment(a)
    assert passed, msg


# =============================================================================
# MusicXML quarter-tone accidental test
# =============================================================================


def test_musicxml_quarter_tone_accidentals():
    """
    Generate notes with quarter-tone inflections and verify the exported
    MusicXML contains the correct accidental elements.
    """
    from services.sheet_music_service import (
        export_musicxml,
        notes_to_music21_score,
    )
    import tempfile

    notes = [
        {
            "pitch": 64,  # E4
            "start_time_s": 0.0,
            "duration_s": 1.0,
            "amplitude": 0.7,
            "is_quarter": True,
            "cents_dev": -50,
            "type": "note",
        },
        {
            "pitch": 71,  # B4
            "start_time_s": 1.0,
            "duration_s": 1.0,
            "amplitude": 0.7,
            "is_quarter": True,
            "cents_dev": -50,
            "type": "note",
        },
        {
            "pitch": 62,  # D4
            "start_time_s": 2.0,
            "duration_s": 1.0,
            "amplitude": 0.7,
            "is_quarter": True,
            "cents_dev": 50,
            "type": "note",
        },
        {
            "pitch": 67,  # G4
            "start_time_s": 3.0,
            "duration_s": 1.0,
            "amplitude": 0.7,
            "is_quarter": False,
            "cents_dev": 0,
            "type": "note",
        },
    ]

    score, _metadata = notes_to_music21_score(
        notes, tempo_bpm=120, title="Quarter-Tone Test"
    )

    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
        export_musicxml(score, f.name)
        xml_path = f.name

    with open(xml_path, "r") as f:
        xml_content = f.read()

    import os

    os.unlink(xml_path)

    assert "<accidental>quarter-flat</accidental>" in xml_content, (
        "Expected quarter-flat accidental in MusicXML"
    )
    assert "<accidental>quarter-sharp</accidental>" in xml_content, (
        "Expected quarter-sharp accidental in MusicXML"
    )

    quarter_flat_count = xml_content.count("<accidental>quarter-flat</accidental>")
    quarter_sharp_count = xml_content.count("<accidental>quarter-sharp</accidental>")

    assert quarter_flat_count == 2, (
        f"Expected 2 quarter-flat accidentals, got {quarter_flat_count}"
    )
    assert quarter_sharp_count == 1, (
        f"Expected 1 quarter-sharp accidental, got {quarter_sharp_count}"
    )
