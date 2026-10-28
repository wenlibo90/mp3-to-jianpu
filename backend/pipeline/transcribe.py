from pathlib import Path


def transcribe_midi(audio_path: Path, out_dir: Path) -> Path:
    """使用 basic-pitch 将音频转录为 MIDI。"""
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    out_dir.mkdir(parents=True, exist_ok=True)
    _model_output, midi_data, _note_events = predict(
        str(audio_path), ICASSP_2022_MODEL_PATH
    )
    midi_path = out_dir / "transcription.mid"
    midi_data.write(str(midi_path))
    return midi_path
