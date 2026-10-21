# 两个参考仓库的阅读记录

阅读日期：2026-10-21（Asia/Shanghai）。本仓库独立实现网关与示例，不复制未明确授权的参考仓库源码。

## 1. yuzhangzhe/model

- 地址：https://gitcode.com/yuzhangzhe/model
- 阅读提交：`39b0eaa55f69693958a752f04a5a0d64c6f32871`。
- 阅读文件：`README.md`、`server.js`、`start.bat`、`public/` 前端结构。
- Node 原生 HTTP 服务承载聊天页面，默认 `5173` 端口，后端调用 `qwen3.5:0.8b`。
- 它将 Ollama 的 NDJSON 转为 SSE，提供健康检查、流式和非流式聊天路径。README 记录过推理引擎文件缺失的修复经验；这是该仓库的环境记录，本机本次没有出现该故障。
- `ACCESS_TOKEN` 可用于认证，代码接受请求头或 query token；本实验采用请求头密钥，不使用 URL token，避免密钥进入 URL 日志。
- 该项目的应用层 `/api/chat` 会转换格式，不能直接当作四种标准协议的统一入口。因此本实验另做透明代理，让 Ollama 自己处理各协议。

## 2. tim-ux123/nailong

- 地址：https://github.com/tim-ux123/nailong
- 阅读提交：`d46a968d3aaa9d5b3123a7be35a7fa89199905e9`。
- 阅读文件：`README.md`、`food_agent.py`、`server.py`、前端结构。
- Python 标准库实现的美食 Agent，本地模型同样是 `qwen3.5:0.8b`，Web 服务使用 `8000` 端口。
- 提供菜谱、营养与口味推荐三个本地数据工具，通过解析 `Action: 工具(参数)`、回填 Observation 并继续询问模型构成循环。
- 工具数据为代码内置样例，不能仅因为由程序返回就视作权威或实时营养依据；提示词限制也不是严格的事实保证。
- 本实验采用 Ollama 原生 `tools` / `tool_calls`，避免靠自然语言正则识别 Action，且用算术白名单函数验证真实执行过程。

## 3. 官方接口依据

- [Ollama API 简介](https://docs.ollama.com/api/introduction)：本地 API 入口。
- [Ollama OpenAI 兼容说明](https://docs.ollama.com/api/openai-compatibility)：Chat Completions 与 Responses 的兼容范围。
- [Ollama Anthropic 兼容说明](https://docs.ollama.com/api/anthropic-compatibility)：Messages 请求和内容块。
- [OpenAI Responses 迁移文档](https://developers.openai.com/api/docs/guides/migrate-to-responses)：OpenAI 官方协议差异。
- [Ollama FAQ](https://docs.ollama.com/faq)：监听地址、代理与环境变量。
- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)：临时公网入口与 SSE 限制。

文档可能随版本更新；本实验是否成功以 `reports/verification.json` 中记录的本机版本、请求和响应为准。
