"""流式转录：分块调用 Basic Pitch 并逐块产出简谱条目。

设计目标（P1）：
- 不依赖 Demucs，直接对音频分块推理，首块最快出结果
- 全局做一次调性与速度估计，作为先验约束简谱映射
- 提供音高曲线用于前端可视化
"""

import math
import os
from pathlib import Path
from typing import Generator, List, Tuple

import numpy as np

from .score import TONIC_NAMES, pitch_to_item

SR = 22050
CHUNK_SEC = 10.0
OVERLAP_SEC = 1.0

KMAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KMINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_model = None


def get_model():
    global _model
    if _model is None:
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model

        _model = Model(ICASSP_2022_MODEL_PATH)
    return _model


def load_audio(path: Path) -> np.ndarray:
    import librosa

    y, _ = librosa.load(str(path), sr=SR, mono=True)
    return y.astype(np.float32)


def detect_key(y: np.ndarray) -> Tuple[int, str]:
    """基于色度特征与 Krumhansl 模板估计调性，返回 (主音音级, 调式)。"""
    import librosa

    chroma = librosa.feature.chroma_cqt(y=y, sr=SR)
    prof = chroma.mean(axis=1)
    prof = prof - prof.mean()
    best = (-2.0, 0, "major")
    for shift in range(12):
        for tmpl, mode in ((KMAJOR, "major"), (KMINOR, "minor")):
            t = np.roll(tmpl, shift)
            t = t - t.mean()
            denom = (np.linalg.norm(prof) * np.linalg.norm(t)) or 1.0
            corr = float(np.dot(prof, t) / denom)
            if corr > best[0]:
                best = (corr, shift, mode)
    _, tonic_pc, mode = best
    return int(tonic_pc), mode


def detect_tempo(y: np.ndarray, default: float = 100.0) -> float:
    import librosa

    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=SR)
        val = float(np.atleast_1d(tempo)[0])
        return val if 40 <= val <= 240 else default
    except Exception:
        return default


def pitch_curve(y: np.ndarray, max_points: int = 1500):
    """返回 (times, midi曲线)。未发声或无有效音高处为 None。"""
    import librosa

    hop = 1024
    f0 = librosa.yin(y, fmin=65.4, fmax=1046.5, sr=SR, hop_length=hop)
    times = librosa.times_like(f0, sr=SR, hop_length=hop)
    midi = 69 + 12 * np.log2(np.maximum(f0, 1e-3) / 440.0)
    t_list = times.tolist()
    m_list = []
    for m in midi:
        if not np.isfinite(m) or m < 36 or m > 96:
            m_list.append(None)
        else:
            m_list.append(round(float(m), 2))
    step = max(1, len(t_list) // max_points)
    return [round(t, 3) for t in t_list[::step]], m_list[::step]


def transcribe_chunks(
    job_dir: Path,
    y: np.ndarray,
    base_do: int,
    tempo: float,
    chunk_sec: float = CHUNK_SEC,
    overlap: float = OVERLAP_SEC,
) -> Generator[dict, None, None]:
    """分块推理并逐块产出新增简谱条目。"""
    import soundfile as sf
    from basic_pitch.inference import predict

    model = get_model()
    total = len(y) / SR
    step = max(1.0, chunk_sec - overlap)
    start = 0.0
    emitted_until = 0.0
    idx = 0

    while start < total - 0.5:
        end = min(start + chunk_sec, total)
        seg = y[int(start * SR) : int(end * SR)]
        cpath = job_dir / f"chunk_{idx}.wav"
        sf.write(str(cpath), seg, SR)

        try:
            _, _, note_events = predict(str(cpath), model)
        except Exception:
            note_events = []

        new_items: List[dict] = []
        for ev in note_events:
            s, e, pitch = float(ev[0]), float(ev[1]), float(ev[2])
            gs = start + s
            ge = start + e
            if ge <= emitted_until + 1e-3:
                continue
            gs = max(gs, emitted_until)
            if ge - gs <= 0.02:
                continue
            item = pitch_to_item(pitch, gs * tempo / 60.0, (ge - gs) * tempo / 60.0, base_do)
            item["startSec"] = round(gs, 3)
            item["endSec"] = round(ge, 3)
            new_items.append(item)

        emitted_until = end
        idx += 1
        start += step
        yield {
            "items": new_items,
            "processedSec": round(end, 2),
            "totalSec": round(total, 2),
        }


def key_display(tonic_pc: int, mode: str) -> Tuple[int, str]:
    """返回 (do 音级, 简谱调号字符串)。"""
    do_pc = (tonic_pc + 3) % 12 if mode == "minor" else tonic_pc
    return do_pc, f"1={TONIC_NAMES[do_pc]}"
