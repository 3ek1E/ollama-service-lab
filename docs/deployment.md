# 对外部署与操作说明

## 本机与局域网

默认网关 `127.0.0.1:8088`；运行 `scripts/start.ps1 -Lan` 监听所有网卡的 `8088`。Ollama 保持 `127.0.0.1:11434`。只通过网关暴露推理与模型列表/信息查询，不开放拉取、删除、创建或复制模型的管理路由。

管理员 PowerShell 可创建范围明确的局域网防火墙规则：

```powershell
New-NetFirewallRule -DisplayName 'Ollama Lab Gateway 8088' `
  -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8088 `
  -RemoteAddress LocalSubnet -Profile Any
```

撤销时使用 `Remove-NetFirewallRule -DisplayName 'Ollama Lab Gateway 8088'`。不要直接把 Ollama 11434 映射到公网。本项目网关只限制同时执行数量，不是按用户配额计费系统。

其他机器访问 `http://<服务器局域网IP>:8088`，使用 `Authorization: Bearer <密钥>` 或 `x-api-key: <密钥>`。密钥在 `.local/service.key`，不在 GitHub。使用同一网络的另一台机器验证才算完成跨设备验收；服务机访问自身局域网 IP 只能证明绑定可用，不能证明 Wi-Fi 客户端隔离与防火墙已完全放通。

## 临时公网 HTTPS

`scripts/public-tunnel.ps1` 下载 Cloudflare 官方 Windows cloudflared，在后台转发到 `127.0.0.1:8088`。读取 `.runtime/tunnel.stderr.log` 获取 `https://....trycloudflare.com` 地址。保持网关密钥认证；第三方隧道会承载请求流量，公网 URL 本身不是访问密钥。

```powershell
$publicUrl = 'https://<本次生成的名称>.trycloudflare.com'
./scripts/call.ps1 -BaseUrl $publicUrl
```

[Cloudflare 官方说明](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)：Quick Tunnel 用于开发测试，地址会变化、无持续可用保证，且不支持 SSE。本实验的公网测试使用 `stream:false`。本机和支持无缓冲转发的正式 HTTPS 入口可用四种流式协议。

停止临时隧道（先核对进程确为本项目记录的 cloudflared）：

```powershell
$tunnelPid = [int](Get-Content .runtime/tunnel.pid -Raw)
Get-Process -Id $tunnelPid | Select-Object Id,ProcessName,Path
# 核对 Path 指向本项目 .runtime/cloudflared.exe 后执行
Stop-Process -Id $tunnelPid
```

## 固定地址服务

有公网服务器和域名时：安装 Ollama 与 Python；配置模型和随机密钥；使用进程管理器保持 `gateway.py` 存活；把 `deploy/Caddyfile` 的域名替换为真实域名，DNS 指向服务器，开放 80/443 并启动 Caddy。Caddy 终止 TLS，网关仍检查认证头。

也可以使用已授权 Cloudflare 账号下的正式 Tunnel，绑定自己的域名并配置访问策略。此处只提供配置样例，没有替用户购买服务器、注册域名或声称已部署长期托管。

## 检查与故障定位

- `/healthz` 为无需密钥的存活检查；它不代表模型已就绪。
- 带密钥访问 `/api/tags` 确认模型存在，真实 `/api/chat` 才验证推理能力。
- `401` 检查认证头；不要把密钥写进 URL；`404` 检查白名单路径和重复 `/v1`。
- `429` 表示网关并发槽位已满；减少并发后重试。
- `502` 检查本机 Ollama；`504` 检查模型载入、可用内存和超时。
- 模型文件缺失或引擎损坏时使用官方安装包修复，勿直接套用他人 README 的历史故障结论。
- `.runtime/gateway.stderr.log` 和 Ollama 自身日志供本地排查；不提交请求内容和密钥。
