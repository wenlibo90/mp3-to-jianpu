import subprocess
from pathlib import Path


def to_wav(src: Path, dst: Path, sample_rate: int = 44100, channels: int = 2) -> Path:
    """使用 ffmpeg 将任意音频转码为 wav。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-ac", str(channels),
        "-ar", str(sample_rate),
        "-vn", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dst.exists():
        raise RuntimeError(f"ffmpeg 转码失败: {proc.stderr[-500:]}")
    return dst
