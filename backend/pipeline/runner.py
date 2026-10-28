import uuid
from pathlib import Path

from .audio import to_wav
from .separate import separate_vocals
from .transcribe import transcribe_midi
from .score import build_score_data, export_musicxml
from ..config import WORK_DIR


def run_pipeline(input_path: Path, separate: bool = True) -> dict:
    """路线 C 主流程：人声分离 -> MIDI 转录 -> 简谱映射。

    人声分离失败时自动降级为直接转录原始音频。
    """
    job_id = uuid.uuid4().hex
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    wav = to_wav(input_path, job_dir / "input.wav")

    target = wav
    vocals_used = False
    if separate:
        try:
            target = separate_vocals(wav, job_dir / "stems")
            vocals_used = True
        except Exception:
            target = wav

    midi = transcribe_midi(target, job_dir)
    data = build_score_data(midi)
    xml = export_musicxml(midi, job_dir / "score.musicxml")

    data["jobId"] = job_id
    data["vocalsSeparated"] = vocals_used
    data["hasMusicxml"] = xml.exists()
    return data
