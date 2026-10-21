# 模型服务配置

本实验的网关默认使用 8088 端口。Ollama 上游服务使用 11434 端口并绑定回环地址。
网关采用 Authorization: Bearer 访问密钥进行认证；兼容 Anthropic 的 x-api-key 请求头。
访问密钥保存在本地 .local/service.key 文件中，不应提交到 GitHub。
公开健康检查路径 /healthz 仅表示网关进程存活；带认证请求 /api/tags 检查上游模型清单。
