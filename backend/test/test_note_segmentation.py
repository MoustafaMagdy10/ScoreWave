"""
Unit tests for utils.note_segmentation.segment_notes().

Uses synthetic CREPE-like frame data to verify:
  - Frame grouping (pitch continuity, quarter-tone merging)
  - Minimum note duration filter
  - Confidence threshold filtering
  - Rest insertion between notes
  - Quarter-tone flag propagation
  - Pitch majority vote
"""

from typing import Any, Dict, List

import pytest

from utils.note_segmentation import segment_notes


# ── Constants ────────────────────────────────────────────────────────────────

_STEP_S = 0.01  # 10 ms step (matches _STEP_SIZE_MS = 10)
_FRAME_RATE = int(1 / _STEP_S)  # 100 frames/sec

_MIDI_E4 = 64
_MIDI_Ds4 = 63
_MIDI_F4 = 65
_MIDI_G4 = 67

_FREQ_E4 = 329.63
_FREQ_Ds4 = 311.13
_FREQ_F4 = 349.23
_FREQ_G4 = 392.00

_CONF_HIGH = 0.9
_CONF_LOW = 0.3  # below the 0.4 threshold


# ── Helper ───────────────────────────────────────────────────────────────────


def _make_crepe_result(frames: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a CREPE result dict from a list of frame dicts.

    Each frame dict can have:
        freq (float):  frequency in Hz (0.0 = silence)
        conf (float):  confidence (0.0-1.0)
        midi (int):    nearest MIDI note (None if silent)
        cents (int):   cents deviation from nearest MIDI
        quarter (bool): is this a quarter-tone frame?

    If ``freq`` is omitted or 0, a silent frame is generated.
    """
    times = []
    frequencies = []
    confidences = []
    note_details = []

    for i, f in enumerate(frames):
        t = i * _STEP_S
        freq = f.get("freq", 0.0)
        conf = f.get("conf", _CONF_HIGH)
        midi = f.get("midi", None)
        cents = f.get("cents", 0)
        is_quarter = f.get("quarter", False)

        times.append(t)
        frequencies.append(freq)
        confidences.append(conf)
        note_details.append(
            {
                "note": "Rest" if freq <= 0 else _midi_to_name(midi, cents),
                "midi": midi if freq > 0 else None,
                "cents_dev": cents,
                "is_quarter": is_quarter,
                "frequency": freq,
            }
        )

    return {
        "time": times,
        "frequency": frequencies,
        "confidence": confidences,
        "note_details": note_details,
        "duration_s": round(times[-1] + _STEP_S, 2) if times else 0.0,
        "frames_total": len(times),
        "frames_kept": sum(1 for f in frequencies if f > 0),
    }


def _midi_to_name(midi: int, cents: int) -> str:
    """Crude MIDI-to-name (only for notes in C4-C5 range)."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    pc = midi % 12
    octave = (midi // 12) - 1
    return f"{names[pc]}{octave}" + (f"+{cents}c" if cents else "")


def _note_frame(
    midi: int,
    freq: float,
    cents: int = 0,
    quarter: bool = False,
    conf: float = _CONF_HIGH,
) -> Dict[str, Any]:
    """Create a voiced frame dict."""
    return {
        "freq": freq,
        "conf": conf,
        "midi": midi,
        "cents": cents,
        "quarter": quarter,
    }


def _silent_frame(conf: float = _CONF_HIGH) -> Dict[str, Any]:
    """Create a silent/rest frame dict."""
    return {"freq": 0.0, "conf": conf, "midi": None, "cents": 0, "quarter": False}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestSegmentNotes:
    """Tests for segment_notes()."""

    def test_empty_input(self):
        """Empty frame list → empty list."""
        crepe = _make_crepe_result([])
        assert segment_notes(crepe) == []

    def test_single_sustained_note(self):
        """15 consecutive E4 frames → 1 NoteEvent with pitch=64, ~0.15s duration."""
        frames = [_note_frame(_MIDI_E4, _FREQ_E4)] * 15
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 1
        n = result[0]
        assert n.pitch == _MIDI_E4
        assert n.frequency == pytest.approx(_FREQ_E4, rel=0.1)
        assert n.amplitude == pytest.approx(_CONF_HIGH, rel=0.1)
        assert n.start_time_s == pytest.approx(0.0, abs=_STEP_S)
        assert n.duration_s == pytest.approx(0.15, abs=_STEP_S)
        assert not n.is_quarter
        assert n.cents_dev == 0

    def test_two_notes_with_gap(self):
        """2 note groups separated by silence → 2 NoteEvents + 1 rest."""
        frames = (
            [_note_frame(_MIDI_E4, _FREQ_E4)] * 15  # note 1: 0.0-0.15s
            + [_silent_frame()] * 10  # silence: 0.15-0.25s
            + [_note_frame(_MIDI_G4, _FREQ_G4)] * 15  # note 2: 0.25-0.4s
        )
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 3  # 2 notes + 1 rest
        assert result[0].pitch == _MIDI_E4
        assert result[0].frequency > 0

        # Rest in the middle
        assert result[1].pitch == 0
        assert result[1].frequency == 0.0
        assert result[1].is_quarter is False

        assert result[2].pitch == _MIDI_G4
        assert result[2].frequency > 0

    def test_note_boundary_at_pitch_change(self):
        """Pitch shift > 30¢ → separate notes."""
        frames = (
            [_note_frame(_MIDI_E4, _FREQ_E4)] * 15  # E4
            + [_note_frame(_MIDI_F4, _FREQ_F4)] * 15  # F4 (100¢ > 30¢ threshold)
        )
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 2
        assert result[0].pitch == _MIDI_E4
        assert result[1].pitch == _MIDI_F4

    def test_quarter_tone_merge(self):
        """
        Adjacent D#4↔E4 frames where BOTH have is_quarter=True → merged.
        The quarter-tone exception overrides the 30¢ threshold.
        """
        frames = (
            [_note_frame(_MIDI_Ds4, _FREQ_Ds4, cents=50, quarter=True)] * 8  # D#4+50¢
            + [_note_frame(_MIDI_E4, _FREQ_E4, cents=-50, quarter=True)] * 8  # E4-50¢
        )
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 1, "quarter-tone D#4↔E4 should merge into one note"
        assert result[0].is_quarter, "merged note should be quarter-tone"

    def test_quarter_tone_flag(self):
        """Majority of frames are quarter-tones → NoteEvent.is_quarter=True."""
        frames = [_note_frame(_MIDI_E4, _FREQ_E4, cents=-50, quarter=True)] * 12 + [
            _note_frame(_MIDI_E4, _FREQ_E4, cents=0, quarter=False)
        ] * 3
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 1
        assert result[0].is_quarter is True

    def test_confidence_filter(self):
        """Frames below confidence threshold (0.4) → treated as rest."""
        frames = [_note_frame(_MIDI_E4, _FREQ_E4, conf=_CONF_LOW)] * 10
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 0, "low-confidence frames should produce no notes"

    def test_short_note_discarded(self):
        """Group with < 12 frames → discarded."""
        frames = [_note_frame(_MIDI_E4, _FREQ_E4)] * 3  # only 3 frames
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 0, "3-frame group should be discarded (min=12)"

    def test_pitch_majority_vote(self):
        """Mixed MIDI values → majority wins."""
        frames = (
            [_note_frame(_MIDI_E4, _FREQ_E4)] * 18  # 18 votes for E4 (64)
            + [_note_frame(_MIDI_F4, _FREQ_F4)] * 6  # 6 votes for F4 (65)
        )
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 1
        assert result[0].pitch == _MIDI_E4  # 6 > 4

    def test_rest_insertion(self):
        """Gap > 0.05s between two notes → rest inserted."""
        frames = (
            [_note_frame(_MIDI_E4, _FREQ_E4)] * 15  # 0.0-0.15s
            + [_silent_frame()] * 10  # 0.15-0.25s (gap > 0.05s)
            + [_note_frame(_MIDI_G4, _FREQ_G4)] * 15  # 0.25-0.4s
        )
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        rests = [n for n in result if n.pitch == 0]
        assert len(rests) == 1
        assert rests[0].frequency == 0.0
        assert rests[0].duration_s == pytest.approx(0.1, abs=_STEP_S)

    def test_midi_continuous_value(self):
        """cents_dev of +50 → midi_continuous = 64.5, cents_dev=50."""
        frames = [_note_frame(_MIDI_E4, _FREQ_E4, cents=50, quarter=True)] * 15
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 1
        n = result[0]
        assert n.midi_continuous == pytest.approx(64.5, abs=0.01)
        assert n.cents_dev == 50
        assert n.is_quarter is True

    def test_boundary_not_split_within_threshold(self):
        """
        Frames within 30¢ of each other → same note.

        E4 (64) with +10¢ cents and +20¢ cents are only 10¢ apart → one note.
        """
        frames = [_note_frame(_MIDI_E4, _FREQ_E4, cents=10, quarter=False)] * 8 + [
            _note_frame(_MIDI_E4, _FREQ_E4, cents=20, quarter=False)
        ] * 8
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        assert len(result) == 1, "10¢ difference should stay within same note"

    def test_confidence_mixed_frames(self):
        """
        High-confidence frames sandwiching low-confidence frames.
        Only high-confidence groups produce notes.
        """
        frames = (
            [_note_frame(_MIDI_E4, _FREQ_E4, conf=_CONF_HIGH)] * 15
            + [_note_frame(_MIDI_E4, _FREQ_E4, conf=_CONF_LOW)] * 10
            + [_note_frame(_MIDI_E4, _FREQ_E4, conf=_CONF_HIGH)] * 15
        )
        crepe = _make_crepe_result(frames)
        result = segment_notes(crepe)

        # Two separate high-confidence groups → 2 notes (+ possible rests)
        notes = [n for n in result if n.pitch != 0]
        assert len(notes) == 2, "two high-confidence groups should produce 2 notes"
