const dropEl = document.getElementById("drop");
const fileInput = document.getElementById("file");
const fileLabel = document.getElementById("filename");
const goBtn = document.getElementById("go");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const metaEl = document.getElementById("meta");
const barEl = document.getElementById("bar");
const jianpuEl = document.getElementById("jianpu");
const pitchEl = document.getElementById("pitch");

const state = {
  totalSec: 0,
  processedSec: 0,
  meta: null,
  times: [],
  curve: [],
  items: [],
  running: false,
};

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

function pickFile(file) {
  if (!file) return;
  const dt = new DataTransfer();
  dt.items.add(file);
  fileInput.files = dt.files;
  fileLabel.textContent = `已选择：${file.name}（${(file.size / 1024 / 1024).toFixed(2)} MB）`;
  goBtn.disabled = false;
  resultEl.classList.add("hidden");
  setStatus("");
}

dropEl.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => pickFile(fileInput.files[0]));
["dragenter", "dragover"].forEach((ev) =>
  dropEl.addEventListener(ev, (e) => {
    e.preventDefault();
    dropEl.classList.add("over");
  })
);
["dragleave", "drop"].forEach((ev) =>
  dropEl.addEventListener(ev, (e) => {
    e.preventDefault();
    dropEl.classList.remove("over");
  })
);
dropEl.addEventListener("drop", (e) => pickFile(e.dataTransfer.files[0]));

function buildSymbol(it) {
  const upDots = it.octave > 0 ? "<span>·</span>".repeat(it.octave) : "";
  const downDots = it.octave < 0 ? "<span>·</span>".repeat(-it.octave) : "";
  const digit = it.rest ? "0" : String(it.degree);
  const acc = !it.rest && it.accidental ? `<sup>${it.accidental}</sup>` : "";
  let marks = "";
  if (it.dots) marks += "·".repeat(it.dots);
  if (it.dashes) marks += "—".repeat(it.dashes);
  const lineEls = it.underlines ? "<i></i>".repeat(it.underlines) : "";
  const cls = ["note", it.rest ? "rest" : ""].join(" ").trim();
  return `<span class="${cls}">
    <span class="up">${upDots}</span>
    <span class="mid"><span class="digit">${digit}${acc}</span><span class="marks">${marks}</span></span>
    <span class="lines">${lineEls}</span>
    <span class="down">${downDots}</span>
  </span>`;
}

function measureLen() {
  const ts = (state.meta && state.meta.timeSignature) || "4/4";
  const [n, d] = ts.split("/").map(Number);
  return n * (4 / d);
}

function makeRest(d) {
  return { rest: true, duration: d, dashes: 0, underlines: d < 1 ? 1 : 0, dots: 0 };
}

function renderJianpu() {
  const ml = measureLen();
  const groups = {};
  state.items.forEach((it) => {
    const mi = Math.max(0, Math.floor(it.onset / ml));
    (groups[mi] = groups[mi] || []).push(it);
  });
  const idxs = Object.keys(groups).map(Number).sort((a, b) => a - b);
  jianpuEl.innerHTML = idxs
    .map((mi) => {
      const items = groups[mi].sort((a, b) => a.onset - b.onset);
      let cursor = mi * ml;
      const cells = [];
      items.forEach((it) => {
        if (it.onset - cursor > 0.125) cells.push(buildSymbol(makeRest(it.onset - cursor)));
        cells.push(buildSymbol(it));
        cursor = it.onset + it.duration;
      });
      return `<div class="measure"><span class="measure-no">${mi + 1}</span>${cells.join("")}</div>`;
    })
    .join("");
}

function renderMeta() {
  const m = state.meta;
  if (!m) return;
  const written = state.items.length;
  const pct = state.totalSec ? Math.round((state.processedSec / state.totalSec) * 100) : 0;
  metaEl.innerHTML = `
    <span>调号 <b>${m.key}</b></span>
    <span>拍号 <b>${m.timeSignature}</b></span>
    <span>速度 <b>${Math.round(m.tempo)}</b></span>
    <span>已写出 <b>${written}</b> 个音</span>
    <span>进度 <b>${Math.min(pct, 100)}%</b></span>
  `;
}

function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, h / 2, w / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function renderPitch() {
  const dpr = window.devicePixelRatio || 1;
  const rect = pitchEl.getBoundingClientRect();
  if (rect.width === 0) return;
  pitchEl.width = Math.round(rect.width * dpr);
  pitchEl.height = Math.round(rect.height * dpr);
  const ctx = pitchEl.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = rect.width;
  const H = rect.height;
  ctx.clearRect(0, 0, W, H);
  if (!state.totalSec) return;

  const vals = state.curve.filter((v) => v != null);
  let lo = 55, hi = 79;
  if (vals.length) {
    lo = Math.min(...vals) - 1;
    hi = Math.max(...vals) + 1;
  }
  const x = (t) => (t / state.totalSec) * W;
  const y = (m) => H - ((m - lo) / (hi - lo || 1)) * H;

  ctx.strokeStyle = "rgba(154,163,199,.18)";
  ctx.lineWidth = 1;
  for (let m = Math.ceil(lo); m <= hi; m++) {
    const yy = Math.round(y(m)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(0, yy);
    ctx.lineTo(W, yy);
    ctx.stroke();
  }

  const step = Math.max(1, Math.round(state.items.length / 4000) || 1);
  ctx.fillStyle = "rgba(139,123,255,.55)";
  for (let i = 0; i < state.items.length; i++) {
    const it = state.items[i];
    if (it.startSec == null) continue;
    const bx = x(it.startSec);
    const bw = Math.max(3, x(it.endSec) - bx);
    roundRect(ctx, bx, y(it.midi) - 4, bw, 9, 3);
    ctx.fill();
  }

  ctx.strokeStyle = "#f5b64b";
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  let started = false;
  for (let i = 0; i < state.times.length; i++) {
    const v = state.curve[i];
    if (v == null) {
      started = false;
      continue;
    }
    const xx = x(state.times[i]);
    const yy = y(v);
    if (!started) {
      ctx.moveTo(xx, yy);
      started = true;
    } else {
      ctx.lineTo(xx, yy);
    }
  }
  ctx.stroke();
}

function renderAll() {
  renderMeta();
  barEl.style.width = `${state.totalSec ? Math.min(100, (state.processedSec / state.totalSec) * 100) : 0}%`;
  renderPitch();
  renderJianpu();
}

function dispatch(event, data) {
  switch (event) {
    case "start":
      state.totalSec = data.totalSec;
      break;
    case "meta":
      state.meta = data;
      break;
    case "curve":
      state.times = data.times || [];
      state.curve = data.midi || [];
      break;
    case "notes":
      if (data.items && data.items.length) state.items.push(...data.items);
      state.processedSec = data.processedSec || state.processedSec;
      break;
    case "done":
      state.meta = Object.assign({}, state.meta, data);
      state.processedSec = state.totalSec;
      break;
    case "error":
      setStatus(`处理失败：${data.message}`, true);
      break;
  }
  renderAll();
}

function handleMessage(raw) {
  const lines = raw.split("\n");
  let event = "message";
  let data = "";
  for (const l of lines) {
    if (l.startsWith("event:")) event = l.slice(6).trim();
    else if (l.startsWith("data:")) data += l.slice(5).trim();
  }
  if (!data) return;
  try {
    dispatch(event, JSON.parse(data));
  } catch (e) {}
}

async function transcribe() {
  const file = fileInput.files[0];
  if (!file || state.running) return;
  state.running = true;
  state.totalSec = 0;
  state.processedSec = 0;
  state.meta = null;
  state.times = [];
  state.curve = [];
  state.items = [];
  goBtn.disabled = true;
  resultEl.classList.remove("hidden");
  jianpuEl.innerHTML = "";
  setStatus("正在分析音频并逐块转写…");

  const fd = new FormData();
  fd.append("file", file);

  try {
    const res = await fetch("/api/transcribe/stream", { method: "POST", body: fd });
    if (!res.ok || !res.body) throw new Error(res.statusText);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        handleMessage(raw);
      }
    }
    setStatus("转换完成。");
  } catch (err) {
    setStatus(`转换失败：${err.message}`, true);
  } finally {
    state.running = false;
    goBtn.disabled = false;
  }
}

goBtn.addEventListener("click", transcribe);
window.addEventListener("resize", renderPitch);
