"""
Multi-cue section detector — splits a note sequence into sections using
pitch histogram shifts (primary), silence gaps (secondary), and tempo
changes (tertiary).
"""

from typing import List

import numpy as np

from models.schema import NoteEvent, SectionBoundary


_SILENCE_GAP_S = 0.5
_TEMPO_CHANGE_PCT = 15.0
_BOUNDARY_MERGE_WINDOW_S = 1.0
_MIN_SECTION_DURATION_S = 5.0
_HISTOGRAM_WINDOW_S = 3.0
_HISTOGRAM_STEP_S = 1.0
_HISTOGRAM_THRESHOLD = 0.4


def build_pitch_histogram(notes: List[NoteEvent]) -> np.ndarray:
    """
    Build a 12-bin pitch-class histogram weighted by amplitude.

    Each note contributes its ``amplitude`` to the bin corresponding to
    ``midi_continuous % 12``.
    """
    hist = np.zeros(12, dtype=np.float64)
    for n in notes:
        pc = int(round(n.midi_continuous)) % 12
        hist[pc] += n.amplitude
    return hist


def histogram_distance(h1: np.ndarray, h2: np.ndarray) -> float:
    """
    Cosine distance between two normalized histograms.
    Returns 0.0 for identical, 1.0 for orthogonal.
    """
    n1 = h1 / (np.linalg.norm(h1) + 1e-10)
    n2 = h2 / (np.linalg.norm(h2) + 1e-10)
    return float(1.0 - np.dot(n1, n2))


def _pitch_histogram_candidates(notes: List[NoteEvent]) -> List[float]:
    """Find section boundaries based on pitch histogram shifts."""
    if len(notes) < 10:
        return []

    total_duration = notes[-1].start_time_s + notes[-1].duration_s
    if total_duration <= _HISTOGRAM_WINDOW_S:
        return []

    candidates: List[float] = []
    t = 0.0
    prev_hist: np.ndarray | None = None

    while t + _HISTOGRAM_WINDOW_S <= total_duration:
        window_notes = [
            n for n in notes if t <= n.start_time_s < t + _HISTOGRAM_WINDOW_S
        ]
        if len(window_notes) < 3:
            t += _HISTOGRAM_STEP_S
            continue

        hist = build_pitch_histogram(window_notes)
        if prev_hist is not None:
            dist = histogram_distance(prev_hist, hist)
            if dist > _HISTOGRAM_THRESHOLD:
                mid = t + _HISTOGRAM_WINDOW_S / 2.0
                candidates.append(mid)

        prev_hist = hist
        t += _HISTOGRAM_STEP_S

    return candidates


def _silence_gap_candidates(notes: List[NoteEvent]) -> List[float]:
    """Find section boundaries based on silence gaps between notes."""
    candidates: List[float] = []
    for i in range(1, len(notes)):
        prev_end = notes[i - 1].start_time_s + notes[i - 1].duration_s
        gap = notes[i].start_time_s - prev_end
        if gap > _SILENCE_GAP_S:
            candidates.append((prev_end + notes[i].start_time_s) / 2.0)
    for n in notes:
        if n.pitch == 0 and n.duration_s > _SILENCE_GAP_S:
            candidates.append(n.start_time_s + n.duration_s / 2.0)
    return candidates


def _tempo_change_candidates(audio_bytes: bytes) -> List[float]:
    """
    Find section boundaries based on tempo changes.
    Uses ``detect_comprehensive_tempo`` from ``utils.tempo_analysis``.
    """
    from utils.tempo_analysis import detect_comprehensive_tempo

    tempo_info = detect_comprehensive_tempo(audio_bytes)
    beat_times = tempo_info.get("beat_times", [])
    if len(beat_times) < 6:
        return []

    intervals = np.diff(beat_times)
    candidates: List[float] = []

    for i in range(3, len(intervals) - 3):
        window_before = intervals[i - 3 : i]
        window_after = intervals[i : i + 3]
        avg_before = np.mean(window_before)
        avg_after = np.mean(window_after)
        if avg_before > 0 and avg_after > 0:
            change_pct = (
                abs(avg_after - avg_before) / min(avg_before, avg_after) * 100.0
            )
            if change_pct > _TEMPO_CHANGE_PCT:
                candidates.append(beat_times[i])

    return candidates


def _merge_boundaries(candidates: List[float], merge_window: float) -> List[float]:
    """Collapse boundary candidates within merge_window into single points."""
    if not candidates:
        return []

    sorted_c = sorted(candidates)
    merged = [sorted_c[0]]

    for c in sorted_c[1:]:
        if c - merged[-1] <= merge_window:
            merged[-1] = (merged[-1] + c) / 2.0
        else:
            merged.append(c)

    return merged


def detect_sections(
    notes: List[NoteEvent], audio_bytes: bytes
) -> List[SectionBoundary]:
    """
    Detect section boundaries using three independent cues.

    Args:
        notes: Segmented NoteEvent list (from ``segment_notes``).
        audio_bytes: Raw audio bytes for tempo analysis.

    Returns:
        Sorted list of SectionBoundary objects.
    """
    if not notes:
        return [SectionBoundary(start_time=0.0, end_time=0.0)]

    total_duration = notes[-1].start_time_s + notes[-1].duration_s

    hist_candidates = _pitch_histogram_candidates(notes)
    silence_candidates = _silence_gap_candidates(notes)
    tempo_candidates = _tempo_change_candidates(audio_bytes)

    all_candidates = list(set(hist_candidates + silence_candidates + tempo_candidates))
    merged = _merge_boundaries(all_candidates, _BOUNDARY_MERGE_WINDOW_S)

    merged = [
        m
        for m in merged
        if _MIN_SECTION_DURATION_S < m < total_duration - _MIN_SECTION_DURATION_S
    ]

    # Filter out boundaries that would create sections with too few notes
    MIN_NOTES_PER_SECTION = 5
    filtered = []
    for m in merged:
        notes_before = [n for n in notes if n.start_time_s < m]
        notes_after = [n for n in notes if n.start_time_s >= m]
        if len([n for n in notes_before if n.pitch > 0]) < MIN_NOTES_PER_SECTION:
            continue
        if len([n for n in notes_after if n.pitch > 0]) < MIN_NOTES_PER_SECTION:
            continue
        filtered.append(m)
    merged = filtered

    boundaries = [0.0] + merged + [total_duration]

    sections: List[SectionBoundary] = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1]
        if end - start >= _MIN_SECTION_DURATION_S:
            sections.append(SectionBoundary(start_time=start, end_time=end))

    if not sections:
        sections.append(SectionBoundary(start_time=0.0, end_time=total_duration))

    return sections
