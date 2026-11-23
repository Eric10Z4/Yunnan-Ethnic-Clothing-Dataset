# 本地运行配置

## 环境与依赖

建议在独立的 Python 3.11 或 3.12 环境中安装：

```powershell
python -m pip install -r code/requirements.txt
```

`scipy` 是清洗脚本的直接依赖。`python-docx`、`python-pptx` 用于重新生成 Word/PPT；仅使用已保存的数据、标注与报告时不必运行这些生成器。

分割脚本使用 Rembg 的 `u2net`。重新运行主体分割还需要适配硬件的 ONNX Runtime 后端和模型权重。CPU 环境可按 [Rembg 官方安装说明](https://github.com/danielgatis/rembg#installation)安装 `rembg[cpu]`；GPU 环境按官方的 GPU/CUDA 兼容要求选择后端。不要把 Python 包安装完成等同于模型权重已准备完成；重建时应记录实际包版本、权重来源与校验摘要。

## VLM 服务

五个 QC、历史诊断及标注脚本统一通过 `vlm_config.py` 读取服务配置。仓库不启动本机中转服务，也不保存真实认证参数；请使用你已经部署的、支持图像输入及 OpenAI 风格 chat-completions 请求的服务。

优先级为：环境变量 > 本地 JSON > 非认证默认值。服务 URL 没有默认地址；未配置时直接报配置错误，不发起请求。模型默认名保留原工程设置，可按服务实际支持的模型修改。认证字段可为空，此时不发送 Authorization 头。

| 环境变量 | 本地 JSON 字段 | 说明 |
| --- | --- | --- |
| `YECID_VLM_API_URL` | `api_url` | 完整 HTTP(S) chat-completions URL，必填 |
| `YECID_VLM_MODEL` | `model` | 服务支持的模型名 |
| `YECID_VLM_API_KEY` | `api_key` | 可选认证参数，禁止提交真实值 |
| `YECID_VLM_CONFIG` | - | 可选配置文件路径；相对路径按项目根目录解析 |

默认本地文件为 **`code/configs/vlm.local.json`**，已加入 `.gitignore`。可按下列格式在自己电脑创建；这里的地址只是格式示例，认证值保持为空：

```json
{
  "api_url": "http://localhost:8000/v1/chat/completions",
  "model": "gemini-3.1-flash-lite",
  "api_key": ""
}
```

也可以在启动脚本的同一 PowerShell 中设置环境变量。根目录 `.env.example` 仅是模板，程序不会自动读取 `.env`。显式设置 `YECID_VLM_CONFIG` 为空字符串会禁用本地 JSON，离线测试使用此方式避免读取机器上的认证配置。

真实认证值只放在本地忽略文件或环境变量中。不要把配置内容、请求 Authorization 头或含认证值的诊断日志加入提交。

## 独立数据工作区

V1/V2 标注脚本默认使用本项目的 `dataset/`。处理另一个已物化的数据集时，可在启动前设置 `YECID_DATASET_DIR`；绝对路径直接使用，相对路径按项目根目录解析。此设置同时选择该数据目录中的 mapping、标注输出和重试队列，运行前应确认目标为独立工作区，避免覆盖已验收数据。

显式设置该变量时，图像只按新数据目录下的 mapping `path` 读取，不会被旧电脑的绝对 `local_dest` 抢占。未设置时保留旧 `local_dest` 行为；新 mapping 缺少此字段时使用 `dataset/path`。相对路径必须留在选定的数据目录内，且文件必须已存在。`source_path` 仅是原图来源记录，不作为标注输入；先把分割白底后的标准化图像物化到 `images/{split}/{image_id}.jpg`，再运行标注。该设置不触发下载、分割或数据迁移，也不改变质量审计入口。

## 历史人工复审诊断输入

`03_diagnose_95_fails.py` 不再读取固定聊天软件目录中的私有 CSV。需要运行历史诊断时，显式提供原人工复审导出的 CSV：

```powershell
python code/03_diagnose_95_fails.py --review-csv "path/to/human_review.csv"
```

该操作会调用所配置的 VLM 并写入诊断输出，属于重建操作，不是只读核验。默认项目目录由脚本所在位置推导。

输入 CSV 使用人工复审导出的 `human_decision`、`filename`、`ethnicity`、`item_id`、`fail_reason`、`fail_code`、`fail_detail` 列；脚本只选取 `human_decision` 为 `FAIL` 的记录。

## 离线核验

```powershell
python code/test_vlm_config.py
python code/test_pipeline_offline.py
```

配置测试不请求网络；原生产标注测试使用明确的离线环境配置并 mock 网络响应。两者不重跑采集、图像处理、VLM 标注或报告生成。
