"""
pytest tests for CREPE western note detection.

Tests a 4-note ascending arpeggio: C4 → E4 → G4 → A4
Each note is a pure sine wave at standard A4=440 Hz tuning.

Expected behavior:
  - Each note detected at the correct note name
  - cents_dev near 0 (not a quarter tone)
  - is_quarter = False for all frames
"""

import pytest
import numpy as np
from test_audio_generator import generate_sine_wave_bytes, _pack_as_wav, WESTERN_NOTES
from services.crepe_service import extract_pitch


# =============================================================================
# Helpers
# =============================================================================

NOTE_DURATION = 2.0
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

    quarter_pct = quarter_count / len(voiced) * 100.0 if voiced else 0.0

    return {
        "most_common_note": most_common,
        "avg_cents_dev": round(avg_cents, 1),
        "quarter_count": quarter_count,
        "quarter_pct": round(quarter_pct, 1),
        "voiced_count": len(voiced),
        "vote_breakdown": votes,
    }


def _build_test_audio():
    melody = [
        {"name": "C4", "freq": WESTERN_NOTES["C4"]},
        {"name": "E4", "freq": WESTERN_NOTES["E4"]},
        {"name": "G4", "freq": WESTERN_NOTES["G4"]},
        {"name": "A4", "freq": WESTERN_NOTES["A4"]},
    ]

    all_samples = np.array([], dtype=np.int16)
    for note in melody:
        chunk = generate_sine_wave_bytes(note["freq"], NOTE_DURATION, SAMPLE_RATE)
        raw = chunk[44:]
        samples = np.frombuffer(raw, dtype=np.int16)
        all_samples = np.concatenate([all_samples, samples])

    wav = _pack_as_wav(all_samples, SAMPLE_RATE, 1)

    expected = []
    for i, note in enumerate(melody):
        expected.append(
            {
                "name": note["name"],
                "start": i * NOTE_DURATION,
                "end": (i + 1) * NOTE_DURATION,
            }
        )

    return wav, expected


# =============================================================================
# Fixture (module-scoped — extract_pitch runs once)
# =============================================================================


@pytest.fixture(scope="module")
def crepe_result():
    wav_bytes, _expected = _build_test_audio()
    result = extract_pitch(wav_bytes, confidence_threshold=0.5, step_size_ms=10)
    return result, _expected


# =============================================================================
# Tests
# =============================================================================


def test_c4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 0.0, 2.0)
    assert a["most_common_note"] == "C4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 1.0, f"{a['quarter_pct']}% quarter frames"


def test_e4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 2.0, 4.0)
    assert a["most_common_note"] == "E4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 1.0, f"{a['quarter_pct']}% quarter frames"


def test_g4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 4.0, 6.0)
    assert a["most_common_note"] == "G4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 1.0, f"{a['quarter_pct']}% quarter frames"


def test_a4_detected(crepe_result):
    result, expected = crepe_result
    a = _analyze_window(result["note_details"], result["time"], 6.0, 8.0)
    assert a["most_common_note"] == "A4", f"Got {a['most_common_note']}"
    assert abs(a["avg_cents_dev"]) <= 25, f"cents {a['avg_cents_dev']:.1f}"
    assert a["quarter_pct"] < 1.0, f"{a['quarter_pct']}% quarter frames"
