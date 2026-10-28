import os
import subprocess
from pathlib import Path


def separate_vocals(wav_path: Path, out_dir: Path) -> Path:
    """使用 demucs 分离人声，返回 vocals.wav 路径。

    失败时抛出异常，由上层决定是否降级为直接转录原始音频。
    demucs 4.x 需要从 HuggingFace 拉取模型，此处使用国内镜像端点。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    cmd = [
        "demucs",
        "--two-stems=vocals",
        "-o", str(out_dir),
        "--name", "htdemucs",
        str(wav_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"demucs 分离失败: {proc.stderr[-500:]}")

    matches = sorted(Path(out_dir).glob("htdemucs/*/vocals.wav"))
    if not matches:
        raise RuntimeError("demucs 未生成 vocals.wav")
    return matches[0]
