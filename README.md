# Ollama 模型下载、四种 API 调用与对外服务实验

使用同一个本地 `qwen3.5:0.8b` 模型，演示 Ollama API、OpenAI Chat Completions、OpenAI Responses、Anthropic Messages；提供带认证的流式网关、工具调用与知识库 RAG 示例。Python 核心程序仅使用标准库。

本项目参考阅读了 [yuzhangzhe/model](https://gitcode.com/yuzhangzhe/model) 的本地聊天服务和 [tim-ux123/nailong](https://github.com/tim-ux123/nailong) 的美食工具 Agent，代码为本实验独立编写。详细分析见 [参考仓库阅读记录](docs/references.md)。

## 已实际完成

- 本机 Ollama `0.40.6`，下载并运行 `qwen3.5:0.8b`（约 1.32 GB）。
- 四种协议各完成非流式、流式请求，共八种实际推理调用。
- 网关随机密钥认证、模型与路由白名单、请求体大小限制、并发上限；Ollama 管理接口不对外提供。
- 原生 function calling 完成计算器调用：`(123+456)*7 = 4053`。
- 本地知识库检索后生成带资料来源的回答。
- 结果与原始响应保存在 [验证报告](reports/verification.json)。实际对外地址和验证范围见 [部署记录](reports/deployment.md)。

## 快速开始（Windows）

先安装 [Ollama](https://ollama.com/download/windows)、Python 3.10+，然后在项目根目录运行：

```powershell
# 启动 Ollama、拉取模型、生成本地随机密钥并启动网关
./scripts/start.ps1

# 四种接口普通调用 / 流式调用
./scripts/call.ps1
./scripts/call.ps1 -Stream

# 运行验证，生成 reports/verification.json
python -X utf8 scripts/verify.py

# 使用工具和 RAG（密钥只在本地读取）
$env:SERVICE_API_KEY = (Get-Content .local/service.key -Raw).Trim()
python -X utf8 examples/tool_agent.py
python -X utf8 examples/rag.py

# 停止网关
./scripts/stop.ps1
```

`start.ps1` 在已有 Ollama 服务可用时复用它，否则启动项目自己的实例，并将模型存到 `.runtime/models`。默认模型名称与两个参考项目一致。原始模型文件由 `ollama pull` 获取，不上传 GitHub。`.local` 内的密钥、`.runtime` 内的运行日志与可执行文件均已排除。

其他操作系统可先运行 `ollama serve` 和 `ollama pull qwen3.5:0.8b`，设置 `SERVICE_API_KEY` 为至少 32 字符随机值后运行 `python gateway.py`。程序通过进程环境变量读取配置，不自动加载 `.env`。

## 四种接口的区别

这四种方式是**同一模型的不同接口协议**。本实验将请求交给同一个 Ollama 进程；改接口名称不会把 Qwen 变成 GPT 或 Claude。即使提示词相同，参数映射、模板和随机采样也可能影响结果；冷启动耗时不能用来判断协议性能。

| 方式 | 路径 | 主要输入 | 正文读取 | 流式格式 | 使用场景 |
|---|---|---|---|---|---|
| Ollama API | `/api/chat`；单次生成另有 `/api/generate` | `messages` / `prompt`，`options`、`think` 等原生设置 | `message.content` / `response` | NDJSON，一行一个 JSON | 本地开发、模型管理、细调本地推理参数 |
| OpenAI Chat Completions | `/v1/chat/completions` | `messages`，`max_tokens`，`tools` | `choices[0].message.content` | SSE，`choices[].delta`，最后 `[DONE]` | 接入已有 OpenAI SDK/聊天应用 |
| OpenAI Responses | `/v1/responses` | `input`，`instructions`，`max_output_tokens` | `output[].content[]` 的 `output_text`；OpenAI SDK 提供 `.output_text` | SSE，如 `response.output_text.delta` | 使用 Responses 风格客户端、按类型处理输出项与工具调用 |
| Anthropic Messages | `/v1/messages` | `messages`，顶层 `system`，`max_tokens` | `content[]` 中 `type=text` 的块 | SSE，如 `content_block_delta`、`message_stop` | 接入 Anthropic SDK、Messages 风格工具生态 |

原生协议多轮也需要传入历史 `messages`。Responses 在 OpenAI 官方服务中可以使用服务端会话状态和托管工具，但 Ollama 的 Responses 是兼容子集，官方说明不支持 `previous_response_id` / `conversation` 的有状态用法；这里应自己保管历史并回传。Ollama `/v1/messages` 的兼容也不意味着可以使用 Anthropic 云端特有功能。第三方工具仍需要模型有相应能力、上下文长度足够并且应用正确执行工具。依据：[OpenAI 迁移文档](https://developers.openai.com/api/docs/guides/migrate-to-responses)、[Ollama OpenAI 兼容说明](https://docs.ollama.com/api/openai-compatibility)、[Ollama Anthropic 兼容说明](https://docs.ollama.com/api/anthropic-compatibility)。

直接调用本地 Ollama 时，示例 SDK 的 `api_key="ollama"` 仅为客户端占位值，本地 Ollama 不以此认证。**经过本项目网关时必须使用真实的随机网关密钥**。OpenAI SDK 的 `base_url` 以 `/v1` 结尾；Anthropic SDK 的 `base_url` 指向服务根地址，避免重复拼接 `/v1`。参考 [SDK 示例](examples/sdk_clients.py)，可选依赖安装：`pip install ollama openai anthropic`。

## 一个请求的例子

```powershell
$key = (Get-Content .local/service.key -Raw).Trim()
$headers = @{ Authorization = "Bearer $key" }
$body = @{
  model = 'qwen3.5:0.8b'
  messages = @(@{role='user'; content='用一句中文介绍Ollama'})
  stream = $false
  think = $false
} | ConvertTo-Json -Depth 6
Invoke-RestMethod http://127.0.0.1:8088/api/chat -Method Post `
  -Headers $headers -ContentType 'application/json; charset=utf-8' `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

四种请求体、返回值与流式解析的完整可运行实现见 [call_four_apis.py](examples/call_four_apis.py)。设 `SERVICE_BASE_URL` 或使用 `--base-url` 可切换局域网/公网地址。

## 对外服务

```text
外部客户端 → HTTPS 反向代理或隧道 → 8088 认证网关 → 127.0.0.1:11434 Ollama → 本地模型
```

- 局域网：停止已有网关后，运行 `./scripts/start.ps1 -Lan`，监听 `0.0.0.0:8088`。客户端使用服务器的真实局域网 IP；`0.0.0.0` 不是客户端访问地址。
- Windows 防火墙需要放行 TCP 8088，建议仅限可信子网；局域网 HTTP 适用于受信网络，跨网络使用 HTTPS。
- 公网演示：运行 `./scripts/public-tunnel.ps1`，终端日志输出临时 HTTPS 地址。此入口仍需网关密钥。Quick Tunnel 官方限制不支持 SSE，因此用 `stream:false` 演示；流式调用已在本机网关验证。
- 固定域名部署：使用 [Caddy 配置示例](deploy/Caddyfile)，将域名 DNS 指向服务器，配置 80/443，网关保持回环监听。也可使用有账号的正式 Cloudflare Tunnel。临时隧道不等于长期在线托管服务。

详细步骤和停止隧道方式见 [部署说明](docs/deployment.md)。

## 还能给模型什么“外挂”？

“外挂”通常装在模型外层的应用中，由应用提供资料、工具、状态和权限，详见 [模型扩展说明](docs/extensions.md)。

| 扩展 | 解决什么问题 | 如何接入 |
|---|---|---|
| RAG 知识库 | 回答私有文档、课程资料、公司规范 | 文档切块→关键词/向量检索→片段入上下文；本仓库有 [可运行示例](examples/rag.py) |
| Function calling | 计算、天气、菜谱、业务 API | 模型输出结构化参数→程序验证并调用函数→结果回传；本仓库有 [计算器闭环](examples/tool_agent.py) |
| MCP | 统一连接文件、数据库和外部工具 | 应用充当 MCP 客户端，将工具 schema 提供给模型并负责执行 |
| 联网搜索/浏览器 | 获取模型训练之后的信息 | 接搜索服务/浏览器工具，返回网页片段与来源 |
| 长期记忆 | 跨会话保存偏好、任务状态 | 应用将授权记忆存入数据库，按需检索，不等于模型自己记住了 |
| 数据库/代码运行器 | 查询事实、分析数据、执行程序 | 只读 SQL、限定工具白名单、隔离执行环境 |
| 视觉/语音 | 图片理解、语音对话 | 选支持视觉的模型；ASR 转文字、TTS 播放回答 |
| 工作流与评测 | 多步骤任务、重试、结果质量检查 | 应用编排 Agent、记录工具结果、测试事实一致性 |
| LoRA/微调 | 改变特定领域的风格和任务行为 | 修改/增量训练权重，区别于外接工具；需要数据和训练流程 |

原生工具调用由模型生成结构化指令，本实验不执行模型给出的任意代码。RAG 示例使用中文二元词重叠检索，无额外 embedding 模型；它展示检索流程，不代表大规模语义检索的质量。提示词和工具结果能减少幻觉，无法保证小模型永不编造。

## 文件导航

| 文件 | 用途 |
|---|---|
| `gateway.py` | 四协议透明转发、认证与访问边界 |
| `scripts/start.ps1` / `stop.ps1` | Windows 启停 |
| `scripts/call.ps1` / `examples/call_four_apis.py` | 四协议普通与流式调用 |
| `examples/sdk_clients.py` | 可选官方客户端 SDK 示例 |
| `examples/tool_agent.py` | 真正执行函数并回填结果 |
| `examples/rag.py` / `knowledge/` | 知识库检索与生成 |
| `scripts/verify.py` / `reports/` | 实测证据 |
| `docs/` / `deploy/` | 阅读笔记、扩展说明、部署方案 |

## 验证与限制

`python -m unittest discover -s tests -v` 使用模拟上游验证网关边界；`python scripts/verify.py` 执行真实模型测试。SDK 示例为可选用法，是否实际运行以验证报告为准。核心网关适合课程实验，不含多用户计费、持久化限流和完整生产运维功能。电脑休眠、服务停止或网络变化会使本机服务不可达。
