from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
WORK_DIR = Path("/tmp/jianpu_work")
WORK_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}
