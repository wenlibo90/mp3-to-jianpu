# 用户指令记忆

本文件记录了用户的指令、偏好和教导，用于在未来的交互中提供参考。

## 格式

### 用户指令条目
[用户指令摘要]
- Date: [YYYY-MM-DD]
- Context: [提及的场景或时间]
- Instructions:
  - [用户教导或指示的内容，逐行描述]

### 项目知识条目
[项目知识摘要]
- Date: [YYYY-MM-DD]
- Context: Agent 在执行 [具体任务描述] 时发现
- Category: [运维部署|构建方法|测试方法|排错调试|工作流协作|环境配置]
- Instructions:
  - [具体的知识点，逐行描述]

## 去重策略
- 添加新条目前，检查是否存在相似或相同的指令
- 若发现重复，跳过新条目或与已有条目合并
- 合并时，更新上下文或日期信息
- 这有助于避免冗余条目，保持记忆文件整洁

## 条目

[Python 依赖镜像与 HuggingFace 访问配置]
- Date: 2026-10-28
- Context: Agent 在搭建 MP3 转简谱项目、安装 torch/demucs/basic-pitch 时发现
- Category: 环境配置
- Instructions:
  - 官方 PyPI 源（pypi.org / files.pythonhosted.org）与 download.pytorch.org 极慢（约 20kB/s），会长时间卡住
  - pip 默认源设为清华镜像：`pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`
  - torch CPU 版从阿里镜像安装（实测约 6.6MB/s）：`pip3 install "torch==2.6.0+cpu" "torchaudio==2.6.0+cpu" --find-links https://mirrors.aliyun.com/pytorch-wheels/cpu/`
  - HuggingFace 官方站（huggingface.co）在当前环境不可达，需设置 `HF_ENDPOINT=https://hf-mirror.com` 走镜像
  - pip 安装需带 `--break-system-packages`（系统 Python 环境）

[Demucs 人声分离运行特性]
- Date: 2026-10-28
- Context: Agent 在实现路线 C（人声分离 + 音符转录）流水线时发现
- Category: 构建方法
- Instructions:
  - demucs 4.x 依赖 HuggingFace 下载模型，必须设置 `HF_ENDPOINT=https://hf-mirror.com`，否则报 "Network is unreachable" 并反复重试
  - demucs 在 CPU 上分离极慢，约 15 倍实时（11.7 秒音频耗时约 180 秒），长音频不适合同步请求
  - basic-pitch 0.4.0 依赖 TensorFlow（非 torch），首次导入约 16 秒，模型推理为 CPU

[项目启动方式]
- Date: 2026-10-28
- Context: Agent 在部署本项目预览时确认
- Category: 运维部署
- Instructions:
  - 启动命令：`uvicorn backend.main:app --host 0.0.0.0 --port 8000`（工作目录为仓库根）
  - 前端静态页面由 FastAPI 在根路径 `/` 托管，单端口访问
