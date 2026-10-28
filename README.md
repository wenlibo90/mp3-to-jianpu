# MP3 转简谱

把一首 MP3 歌曲转成简谱（数字谱）。上传音频后，服务端分块转录并以 SSE 流式逐音符返回，前端边接收边渲染，同时绘制「原唱音高 vs 写出音符」的对比曲线，让等待过程变成可见的生成过程。

## 特性

- 流式转写：音频分块推理，首批音符通常在数秒内出现
- 音高可视化：黄色曲线为原唱音高，紫色块为写出的音符
- 简谱渲染：高低音点、下划线、增时线、附点、小节划分与休止填充
- 先验约束：全局估计调性与速度，用于简谱映射
- 单端口部署：FastAPI 同时托管前端静态页面与 API，根路径即首页

## 技术栈

| 层 | 选型 |
| --- | --- |
| 后端服务 | FastAPI + Uvicorn |
| 音频转码 | ffmpeg |
| 音高分析 | librosa |
| 音符转录 | Basic Pitch (ICASSP 2022 模型) |
| 乐谱处理 | music21 |
| 实时通道 | Server-Sent Events (SSE) |
| 前端 | 原生 HTML / CSS / JS + Canvas |

## 快速开始

### 依赖

- Python 3.11
- ffmpeg

### 安装

```bash
pip install -r requirements.txt
```

国内网络建议使用镜像（否则依赖下载会非常慢）：

```bash
pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 运行

```bash
bash run.sh
```

或直接启动：

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000 即可使用。

## 目录结构

```
backend/
  config.py              路径与上传限制配置
  main.py                FastAPI 应用与 SSE 接口
  pipeline/
    audio.py             ffmpeg 音频转码
    separate.py          Demucs 人声分离（可选，默认关闭）
    transcribe.py        Basic Pitch 整段转录
    stream.py            分块流式转录 + 调性/速度/音高曲线
    score.py             调性与简谱映射、小节分组、MusicXML 导出
    runner.py            整段处理流程编排
frontend/
  index.html             上传页与结果区
  app.js                 SSE 消费、音高曲线绘制、简谱渲染
  styles.css             样式
run.sh                   启动脚本
requirements.txt         Python 依赖
```

## API

### POST /api/transcribe/stream

流式转写，返回 `text/event-stream`。请求为 multipart 表单，字段名 `file`。

事件序列：

| 事件 | 说明 |
| --- | --- |
| `start` | `{ totalSec }` 音频总时长 |
| `meta` | `{ key, mode, tempo, timeSignature, totalSec }` 调性与速度 |
| `curve` | `{ times[], midi[] }` 音高曲线，`null` 表示该帧无有效音高 |
| `notes` | `{ items[], processedSec, totalSec }` 本块新增的简谱条目 |
| `done` | `{ ..., noteCount, measures[] }` 完整结果 |
| `error` | `{ message }` 处理失败 |

### POST /api/transcribe

兼容接口，整段处理并一次性返回 JSON。

## 工作流程

```
上传音频
  -> ffmpeg 转码为单声道 22.05kHz
  -> 估计调性与速度（色度特征 + Krumhansl 模板 / 节拍跟踪）
  -> 计算原唱音高曲线（librosa YIN）
  -> 分块（10s，1s 重叠）调用 Basic Pitch 转录
  -> 音高映射为简谱条目并逐块推送
  -> 汇总为小节，前端增量渲染
```

## 环境注意事项

- pip 官方源与 PyTorch 官方源在国内极慢，建议使用清华 / 阿里镜像
- Demucs 4.x 需要从 HuggingFace 拉取模型，当前环境需设置 `HF_ENDPOINT=https://hf-mirror.com`
- Demucs 在 CPU 上约 15 倍实时，一首歌需数分钟，因此默认关闭，仅作为可选的分流手段

## 路线图

- P1（已完成）流式转录 + 音高曲线可视化 + 进度指示
- P2 音频指纹识别、本地曲谱库命中、歌词逐字对齐
- P3 音符编辑器、曲谱库数据飞轮、版权方案

## 已知限制

- 复音自动转录质量有上限，聚焦单旋律（清唱 / 哼唱 / 主旋律）效果更好
- 速度估计精度会影响时值量化（拍的长短）
- 歌词与外部曲谱库尚未接入，歌词对齐在 P2 实现
- 拍号目前固定按 4/4 处理

## 许可

仅供学习与研究使用。音频、歌词与曲谱内容的版权归各自权利人所有。
