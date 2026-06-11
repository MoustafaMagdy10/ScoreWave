"""
Frame-to-note converter — groups CREPE frames into discrete NoteEvents.
"""

from typing import List, Dict, Any

from models.schema import NoteEvent


_NOTE_MERGE_THRESHOLD_CENTS = 30
_MIN_NOTE_DURATION_MS = 120
_MIN_NOTE_FRAMES = 12
_CONFIDENCE_THRESHOLD = 0.4
_REST_GAP_S = 0.05
_STEP_SIZE_MS = 10


def segment_notes(crepe_result: Dict[str, Any]) -> List[NoteEvent]:
    """
    Convert CREPE frame-level pitch data into discrete NoteEvent objects.

    Args:
        crepe_result: Dict from ``services.crepe_service.extract_pitch``
            with keys ``time``, ``frequency``, ``confidence``, ``note_details``.

    Returns:
        Sorted list of NoteEvent objects.
    """
    times = crepe_result["time"]
    frequencies = crepe_result["frequency"]
    confidences = crepe_result["confidence"]
    note_details = crepe_result["note_details"]

    if not times:
        return []

    step_s = _STEP_SIZE_MS / 1000.0

    midi_continuous_per_frame = []
    for nd in note_details:
        if nd["midi"] is not None and nd["frequency"] > 0:
            m = nd["midi"] + nd["cents_dev"] / 100.0
        else:
            m = 0.0
        midi_continuous_per_frame.append(m)

    groups = []
    current_group = None

    for i in range(len(times)):
        freq = frequencies[i]
        conf = confidences[i]
        nd = note_details[i]
        midi_c = midi_continuous_per_frame[i]

        if freq <= 0 or conf < _CONFIDENCE_THRESHOLD:
            if current_group is not None:
                groups.append(current_group)
            current_group = None
            continue

        if current_group is None:
            current_group = []
            current_group.append(i)
        else:
            prev_idx = current_group[-1]
            prev_midi_c = midi_continuous_per_frame[prev_idx]
            diff_cents = abs(midi_c - prev_midi_c) * 100.0

            nd_cur = note_details[i]
            nd_prev = note_details[prev_idx]
            both_quarter = nd_cur.get("is_quarter") and nd_prev.get("is_quarter")

            if diff_cents <= _NOTE_MERGE_THRESHOLD_CENTS or both_quarter:
                current_group.append(i)
            else:
                groups.append(current_group)
                current_group = [i]

    if current_group is not None and len(current_group) >= _MIN_NOTE_FRAMES:
        groups.append(current_group)

    notes: List[NoteEvent] = []
    for g in groups:
        if len(g) < _MIN_NOTE_FRAMES:
            continue

        first_idx = g[0]
        last_idx = g[-1]
        start_time = times[first_idx] if first_idx < len(times) else 0.0
        end_time = times[last_idx] + step_s if last_idx < len(times) else start_time
        duration = end_time - start_time

        midi_values = []
        cents_values = []
        is_quarter_votes = 0
        freq_values = []
        amp_values = []
        for idx in g:
            if idx >= len(times):
                continue
            nd = note_details[idx]
            if nd["midi"] is not None:
                midi_values.append(nd["midi"])
            cents_values.append(nd["cents_dev"])
            if nd.get("is_quarter"):
                is_quarter_votes += 1
            freq_values.append(frequencies[idx])
            amp_values.append(confidences[idx])

        if not midi_values:
            continue

        pitch = _majority_vote(midi_values)
        avg_midi_continuous = sum(
            m
            for idx in g
            if idx < len(midi_continuous_per_frame)
            for m in [midi_continuous_per_frame[idx]]
        ) / len(g)
        avg_cents = int(round((avg_midi_continuous - pitch) * 100.0))
        is_quarter = (is_quarter_votes / len(g)) > 0.5
        avg_freq = sum(freq_values) / len(freq_values)
        avg_amp = sum(amp_values) / len(amp_values)

        notes.append(
            NoteEvent(
                start_time_s=start_time,
                duration_s=duration,
                pitch=pitch,
                midi_continuous=round(avg_midi_continuous, 4),
                cents_dev=avg_cents,
                is_quarter=is_quarter,
                frequency=round(avg_freq, 2),
                amplitude=round(avg_amp, 4),
            )
        )

    notes.sort(key=lambda n: n.start_time_s)

    inserted = _insert_rests(notes, step_s)
    return inserted


def _insert_rests(notes: List[NoteEvent], step_s: float) -> List[NoteEvent]:
    """Insert rest markers between notes where gap exceeds threshold."""
    if len(notes) < 2:
        return notes

    result: List[NoteEvent] = []
    for i in range(len(notes)):
        if i > 0:
            prev_end = notes[i - 1].start_time_s + notes[i - 1].duration_s
            gap = notes[i].start_time_s - prev_end
            if gap > _REST_GAP_S:
                result.append(
                    NoteEvent(
                        start_time_s=prev_end,
                        duration_s=gap,
                        pitch=0,
                        midi_continuous=0.0,
                        cents_dev=0,
                        is_quarter=False,
                        frequency=0.0,
                        amplitude=0.0,
                    )
                )
        result.append(notes[i])

    return result


def _majority_vote(values: List[int]) -> int:
    """Return the most common value in a list of ints."""
    if not values:
        return 0
    return max(set(values), key=values.count)
