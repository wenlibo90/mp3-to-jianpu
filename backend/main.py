import asyncio
import json
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .config import FRONTEND_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, WORK_DIR
from .pipeline.runner import run_pipeline
from .pipeline import stream as st
from .pipeline.audio import to_wav
from .pipeline.score import group_measures

app = FastAPI(title="MP3 转简谱", version="0.2.0")


@app.get("/api/health")
def health():
    return {"status": "ok"}


async def _save_upload(file: UploadFile) -> Path:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext or '未知'}")
    upload_dir = WORK_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp = upload_dir / f"{uuid.uuid4().hex}{ext}"
    size = 0
    with open(tmp, "wb") as f:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "文件超过 30MB 限制")
            f.write(chunk)
    return tmp


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/transcribe/stream")
async def transcribe_stream(file: UploadFile = File(...)):
    """流式转录：SSE 逐块推送音高曲线、音符与进度。"""
    tmp = await _save_upload(file)
    job_dir = WORK_DIR / uuid.uuid4().hex
    job_dir.mkdir(parents=True, exist_ok=True)
    wav = await run_in_threadpool(
        to_wav, tmp, job_dir / "input.wav", 22050, 1
    )

    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def emit(event: str, data):
        loop.call_soon_threadsafe(q.put_nowait, (event, data))

    def worker():
        try:
            y = st.load_audio(wav)
            total = len(y) / st.SR
            emit("start", {"totalSec": round(total, 2)})

            tonic, mode = st.detect_key(y)
            do_pc, key_str = st.key_display(tonic, mode)
            base_do = 60 + do_pc
            tempo = st.detect_tempo(y)
            emit(
                "meta",
                {
                    "key": key_str,
                    "mode": mode,
                    "tempo": round(tempo, 1),
                    "timeSignature": "4/4",
                    "totalSec": round(total, 2),
                },
            )

            times, curve = st.pitch_curve(y)
            emit("curve", {"times": times, "midi": curve})

            all_items = []
            for chunk in st.transcribe_chunks(job_dir, y, base_do, tempo):
                all_items.extend(chunk["items"])
                emit("notes", chunk)

            emit(
                "done",
                {
                    "key": key_str,
                    "mode": mode,
                    "tempo": round(tempo, 1),
                    "timeSignature": "4/4",
                    "noteCount": len(all_items),
                    "measures": group_measures(all_items, 4, 4),
                },
            )
        except Exception as e:
            emit("error", {"message": str(e)})
        finally:
            emit("__end__", None)

    threading.Thread(target=worker, daemon=True).start()

    async def gen():
        while True:
            event, data = await q.get()
            if event == "__end__":
                break
            yield _sse(event, data)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), separate: bool = Query(False)):
    """兼容接口：整段处理并一次性返回。"""
    tmp = await _save_upload(file)
    try:
        return await run_in_threadpool(run_pipeline, tmp, separate)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"处理失败: {e}")


app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
