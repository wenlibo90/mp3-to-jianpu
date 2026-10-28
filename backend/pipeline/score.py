import math
from pathlib import Path

from music21 import converter, meter, tempo, chord as m21chord

TONIC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

MAJOR_SCALE = {0: 1, 2: 2, 4: 3, 5: 4, 7: 5, 9: 6, 11: 7}
SHARP_MAP = {1: (1, "#"), 3: (2, "#"), 6: (4, "#"), 8: (5, "#"), 10: (6, "#")}

QUANT = 0.25


def parse_midi(midi_path: Path):
    return converter.parse(str(midi_path))


def detect_key(score):
    try:
        k = score.analyze("key")
        return int(k.tonic.pitchClass), k.mode, str(k)
    except Exception:
        return 0, "major", "C major"


def detect_tempo(score, default=120.0):
    try:
        marks = score.flatten().getElementsByClass(tempo.MetronomeMark)
        if marks:
            return float(marks[0].number)
    except Exception:
        pass
    return default


def detect_meter(score, default=(4, 4)):
    try:
        sigs = score.flatten().getElementsByClass(meter.TimeSignature)
        if sigs:
            return sigs[0].numerator, sigs[0].denominator
    except Exception:
        pass
    return default


def collect_notes(score):
    notes = []
    for n in score.flatten().notes:
        if isinstance(n, m21chord.Chord):
            p = max(n.pitches, key=lambda x: x.midi)
        else:
            p = n.pitch
        notes.append(
            {
                "onset": float(n.offset),
                "duration": float(n.quarterLength),
                "midi": int(p.midi),
            }
        )
    notes.sort(key=lambda x: (x["onset"], -x["midi"]))
    return notes


def reduce_monophonic(notes):
    """将复音音符序列压缩为单声部旋律，重叠时保留先出现的音。"""
    result = []
    last_end = -1.0
    for n in notes:
        if n["onset"] < last_end - 1e-6:
            continue
        result.append(n)
        last_end = n["onset"] + n["duration"]
    return result


def degree_of(pc_in):
    if pc_in in MAJOR_SCALE:
        return MAJOR_SCALE[pc_in], ""
    if pc_in in SHARP_MAP:
        return SHARP_MAP[pc_in]
    return 1, ""


def subdivide(v):
    if v <= 0:
        return 0, 0
    table = {
        0.75: (1, 1),
        0.5: (1, 0),
        0.375: (2, 1),
        0.25: (2, 0),
        0.1875: (3, 1),
        0.125: (3, 0),
    }
    for k, (u, d) in table.items():
        if abs(v - k) < 1e-6:
            return u, d
    u = max(0, int(round(math.log2(1.0 / v))))
    return min(u, 4), 0


def analyze_duration(ql):
    """返回 (增时线数量, 下划线数量, 附点数量)。"""
    if ql <= 0:
        return 0, 0, 0
    ql = round(ql / 0.0625) * 0.0625
    if ql >= 1:
        whole = int(ql)
        remainder = round(ql - whole, 4)
        dashes = max(0, whole - 1)
        u, d = subdivide(remainder) if remainder > 0 else (0, 0)
        return dashes, u, d
    u, d = subdivide(ql)
    return 0, u, d


def _make_rest(d):
    dashes, u, dots = analyze_duration(d)
    return {
        "rest": True,
        "duration": round(d, 4),
        "dashes": dashes,
        "underlines": u,
        "dots": dots,
    }


def fill_rests(measure_items, measure_start, measure_len):
    out = []
    cursor = measure_start
    for it in measure_items:
        if it["onset"] - cursor > QUANT / 2:
            out.append(_make_rest(it["onset"] - cursor))
        out.append(it)
        cursor = it["onset"] + it["duration"]
    end = measure_start + measure_len
    if end - cursor > QUANT / 2:
        out.append(_make_rest(end - cursor))
    return out


def pitch_to_item(midi, onset_beats, dur_beats, base_do):
    """将单个音高转换为简谱条目（供流式转录复用）。"""
    nrel = int(round(midi)) - base_do
    octave = nrel // 12
    pc_in = nrel - octave * 12
    degree, acc = degree_of(pc_in)
    dur = max(QUANT, round(dur_beats / QUANT) * QUANT)
    dashes, underlines, dots = analyze_duration(dur)
    onset = round(onset_beats / QUANT) * QUANT
    return {
        "onset": round(onset, 4),
        "degree": degree,
        "accidental": acc,
        "octave": int(octave),
        "duration": float(dur),
        "underlines": underlines,
        "dots": dots,
        "dashes": dashes,
        "midi": int(round(midi)),
    }


def group_measures(items, num, den):
    """按拍号将简谱条目分组为小节，并在空隙填充休止符。"""
    measure_len = num * (4.0 / den)
    grouped = {}
    for it in items:
        mi = max(0, int(it["onset"] // measure_len))
        grouped.setdefault(mi, []).append(it)
    measures = []
    last_index = max(grouped) if grouped else -1
    for mi in range(last_index + 1):
        m_items = sorted(grouped.get(mi, []), key=lambda x: x["onset"])
        filled = fill_rests(m_items, mi * measure_len, measure_len)
        measures.append({"index": mi + 1, "items": filled})
    return measures


def build_score_data(midi_path: Path):
    score = parse_midi(midi_path)
    tonic_pc, mode, key_name = detect_key(score)
    num, den = detect_meter(score)
    tempo_val = detect_tempo(score)

    do_pc = (tonic_pc + 3) % 12 if mode == "minor" else tonic_pc
    base_do = 60 + do_pc

    notes = reduce_monophonic(collect_notes(score))
    measure_len = num * (4.0 / den)

    items = []
    for n in notes:
        onset = round(n["onset"] / QUANT) * QUANT
        dur = max(QUANT, round(n["duration"] / QUANT) * QUANT)
        nrel = n["midi"] - base_do
        octave = nrel // 12
        pc_in = nrel - octave * 12
        degree, acc = degree_of(pc_in)
        dashes, underlines, dots = analyze_duration(dur)
        items.append(
            {
                "onset": round(onset, 4),
                "degree": degree,
                "accidental": acc,
                "octave": int(octave),
                "duration": float(dur),
                "underlines": underlines,
                "dots": dots,
                "dashes": dashes,
                "midi": n["midi"],
            }
        )

    measures = group_measures(items, num, den)

    return {
        "key": f"1={TONIC_NAMES[do_pc]}",
        "keyName": key_name,
        "mode": mode,
        "timeSignature": f"{num}/{den}",
        "tempo": tempo_val,
        "noteCount": len(items),
        "measures": measures,
    }


def export_musicxml(midi_path: Path, out_path: Path) -> Path:
    score = parse_midi(midi_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(out_path))
    return out_path
