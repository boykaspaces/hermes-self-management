# Hermes Token Observer

本插件记录每一次 Hermes 主对话模型 API 尝试和每一次 tool 调用，用于定位 Token、
上下文膨胀、缓存、重试、fallback 和 tool 返回体积问题。

## 隐私边界

数据库不会保存 prompt、消息正文、system prompt、tool 参数值、tool 返回正文、API URL
或 provider 错误消息。Session、task、turn 和 tool-call 标识使用本机随机 salt 做 HMAC
后再保存。

## 覆盖范围

- 主对话模型请求：逐 API attempt 记录，包括失败、重试和 provider fallback。
- Tool：逐调用记录，包括状态、耗时、参数/结果字符数，并通过匿名 API request关联到
  触发它的具体 Loop。
- 辅助模型：Hermes 0.20.0 当前不为辅助客户端发出 request-scoped API hook；其 Token
  仍由 Hermes 自带的 `session_model_usage` 按 task/model 聚合。本插件不会把聚合值伪装成
  逐调用数据。

## 安装

将目录复制到：

```text
~/.hermes/plugins/observability/token_observer
```

然后启用并重启 Hermes Gateway：

```bash
hermes plugins enable observability/token_observer
```

默认数据库位置：

```text
~/.hermes/observability/ai-calls.sqlite3
```

可选环境变量：

- `HERMES_TOKEN_OBSERVER_DB`：覆盖数据库位置。
- `HERMES_TOKEN_OBSERVER_RETENTION_DAYS`：保留天数，默认 30。

## 查询

```bash
python3 ~/.hermes/plugins/observability/token_observer/report.py --days 7
python3 ~/.hermes/plugins/observability/token_observer/report.py --days 7 --json
```

报告包含 model、tool和 loop三组矩阵，并在 `state.db`存在时一并显示 Hermes已有的
辅助模型聚合记账。JSON中的 `coverage`字段会明确说明两种数据的粒度差异。

Hermes在 Bedrock路径会先从消息列表提取 system prompt，且大型 sanitized request可能
被截断。插件在这种情况下使用 Hermes提供的整体 message字符估算减去其余消息体积，
记录 `system_chars_inferred=1`；同时用 provider精确 prompt Token减去 Hermes message
Token估算得到 `non_message_prompt_tokens_estimate`。后者主要反映 tool schema和 provider
编码开销，只作为诊断估算，不伪装成 provider提供的精确 tool Token。

从插件 v0.2起，会在进程启动时安装一个轻量 Runtime instrumentation adapter：它包装
Hermes已有的 system-prompt构造和 hook request-sanitizer，在内容尚未丢失来源边界时只提取
字符数，并给截断后的 hook payload增加 size-only sidecar。新调用因此可拆分为基础指令、
workspace context、skills、memory/user profile、runtime信息、对话历史、逐 Tool/MCP schema和
未归因差额；差额可能同时包含 Provider隐藏指令、协议封装与字符估算误差，不能全部解释为
Provider开销。组件 Token由字符数估算，Provider总 Token仍保持精确。

该 adapter不会修改 Hermes checkout，也不会产生 dirty git文件。执行`hermes update`后，
Gateway重启会从 CloudFormation管理的插件包重新安装 adapter。包装器带版本标记、幂等检查
和函数签名检查：兼容版本自动恢复；接口不兼容时安全降级到合并 System/History统计，不会
阻断模型调用。这样避免了 Hermes更新器 stash/restore本地源码补丁产生冲突的问题。

CloudFormation运行时同步使用 staging目录和原子目录替换，上一版插件保留在
`~/.hermes/plugins/observability/.token_observer.previous`。因此恢复分成两种情况：Hermes
正常升级只需重启 Gateway并做一次组件覆盖验收；插件新版自身异常时，可以停 Gateway、将
该备份目录恢复为`token_observer`后再启动。长期版本基线仍以仓库和 CloudFormation中的确定性
归档为准，现场备份只用于短期回滚。

插件仅使用 Python 标准库；SQLite schema、size-only sidecar和报告不依赖 Bedrock，可迁移到
其他 Hermes实例或模型 provider。

## Web Viewer

Viewer是可选的只读伴随服务，不参与 Hermes请求链路。它只监听回环地址并用 SQLite
`mode=ro`读取同一数据库：

```bash
python3 ~/.hermes/plugins/observability/token_observer/viewer.py \
  --host 127.0.0.1 --port 9120
```

页面聚焦总 Token、缓存命中率、模型矩阵和 Agent调用链，不再把 P95 latency、全局 Tool矩阵
和重复的最近 attempt列表放在首页。“Agent 调用链”按匿名 turn关联同一次执行中的所有 Loop；
点击一次执行可查看每个模型 attempt的精确 Prompt/Cache/Output、估算的 Prompt组件，以及该
Loop触发的每个 Tool/MCP名称和调用次数。这里只统计调用次数，不展示参数、结果或耗时。
所有 HTML、CSS和 JavaScript均随插件本地提供，不加载 CDN；API只返回数据库中已脱敏的维度
和数值，不返回 prompt正文或原始 session/task/turn标识。`--host`只接受 loopback IP，不能
意外监听公网。

长期运行时安装`hermes-token-observer-viewer.service`为 Hermes用户级 systemd服务。
远程访问必须使用 SSM端口转发，不开放 EC2安全组入站端口。
