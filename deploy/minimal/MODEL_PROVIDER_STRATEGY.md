# Hermes 模型调用与硬停止策略

> Reference policy: prefer `openai-codex` with ChatGPT subscription OAuth;
> evaluate `openai-api` only through a separate reviewed deployment decision.

## 目标

当前阶段的目标不是获得一个可以自行填写金额的模型预算，而是：

1. 复用已经购买的 ChatGPT 订阅，不新增按量计费 API账单。
2. 订阅额度耗尽时，由 OpenAI服务端拒绝后续模型调用。
3. Hermes不得在限额、认证或网络错误后静默切换到 Bedrock或其他按量计费 Provider。
4. 所有主模型和辅助模型调用继续进入 Token Observer，能够按 Agent Loop检查实际路由。

OpenAI官方认证文档区分两条路径：ChatGPT登录用于订阅访问，API Key用于按量计费访问。
设备码登录适合没有本地浏览器回调的服务器环境：

- [OpenAI Authentication](https://learn.chatgpt.com/docs/auth)
- [OpenAI Codex App Server authentication and rate limits](https://learn.chatgpt.com/docs/app-server)

The template pins a full Hermes source revision. Before changing that revision,
review the matching upstream provider documentation and repeat authentication,
refresh, limit, and no-fallback tests.

## 当前调用边界

```text
Hermes主调用
  -> openai-codex / OpenAICodexModel
  -> ChatGPT订阅 OAuth

Hermes辅助调用
  -> provider: main
  -> 与主调用使用同一个 openai-codex模型和同一订阅额度

认证失败、限额、429或服务端错误
  -> 不配置主模型 fallback
  -> 不配置辅助模型 fallback_chain
  -> EC2 Role没有 Bedrock InvokeModel权限
  -> 当前任务明确失败并停止，不产生其他模型账单
```

CloudFormation参数`OpenAICodexModel`保存期望模型，默认值为`gpt-5.6-sol`。模型是否可用
最终由当前 ChatGPT账户的实时 Codex模型目录决定；如果账户未提供默认模型，必须先在
`hermes model`中查看可用模型，再用该模型值更新 CloudFormation参数。

## OAuth凭证边界

OAuth是个人身份凭证，不进入 CloudFormation、Secrets Manager、User Data、`.env`、日志、
Token Observer或状态备份。Hermes将凭证保存在：

```text
/home/hermes/.hermes/auth.json
```

文件必须保持`0600 hermes:hermes`。模板只会在文件存在时校正权限，不会创建、导入、输出
或备份其中的 Token。实例重建后必须由订阅所有者重新执行设备码授权。

授权命令：

```bash
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes auth add openai-codex'
```

命令会显示一次性网址和设备码。只在 OpenAI官方登录页面输入设备码；不要把设备码或
`auth.json`内容写入工单、聊天、仓库或 CloudFormation参数。

查看和选择账户实际提供的模型：

```bash
sudo -iu hermes bash -lc \
  'PATH="$HOME/.local/bin:$PATH" hermes model'
```

`hermes model`会立即改写本机配置。生产期望值仍以 CloudFormation的
`OpenAICodexModel`参数为准，Gateway每次启动前都会重新应用该值。

## 生产切换顺序

切换必须按以下顺序执行，避免在凭证尚未建立时先停用当前模型：

1. 在当前实例上执行`hermes auth add openai-codex`，完成个人设备码授权。
2. 通过`hermes model`确认账户提供`OpenAICodexModel`所指定的模型。
3. 停止 Gateway，避免变更窗口内接收新任务。
4. 发布 CloudFormation模板，检查 Change Set不得替换`HermesInstance`。
5. 执行 Change Set；确认 EC2 Role的 Bedrock调用策略被删除。
6. 启动 Gateway。`ExecStartPre`会设置主模型、辅助模型并清除全部 fallback。
7. 执行一个最小模型调用，并在 Token Observer确认：
   - `provider = openai-codex`；
   - `api_mode = codex_responses`；
   - 没有`bedrock`调用；
   - 没有 fallback attempt。
8. 重启 Gateway再次执行最小调用，确认 OAuth刷新状态和声明式配置能够跨重启工作。

不主动耗尽订阅额度作为首次验收，因为这会同时影响所有共享该 ChatGPT账户额度的 Codex
客户端。限额停止行为先通过无 fallback配置、IAM拒绝边界和 Hermes错误路径检查确认；只有
确实需要端到端耗尽测试时，才在所有者明确同意后执行。

## 运行检查

查看有效配置时不得输出`auth.json`：

```bash
sudo -iu hermes bash -lc \
  'sed -n "/^model:/,/^[^ ]/p; /^auxiliary:/,/^[^ ]/p; /^fallback_/p" "$HOME/.hermes/config.yaml"'
```

预期主配置：

```yaml
model:
  provider: openai-codex
  default: gpt-5.6-sol
  base_url: https://chatgpt.com/backend-api/codex
```

`fallback_providers`和`fallback_model`都不应存在；所有已配置的`auxiliary.<task>.provider`
应为`main`，且不应存在`fallback_chain`。

## 后续方案：`openai-api`

以下任一条件出现时，再评估迁移到`openai-api`：

- ChatGPT订阅额度不足以承载 Hermes工作量；
- 个人 OAuth重新认证频率不能满足无人值守要求；
- Hermes与 Codex OAuth后端出现持续兼容问题；
- 需要独立于个人 Codex使用的服务身份、稳定配额或可配置金额上限；
- 需要只在 OpenAI公共 API提供的模型、功能或治理能力。

后续迁移不得直接复用个人 OAuth文件。应新建独立 OpenAI Project，使用项目级服务凭证和
Hard Spend Limit，并把 Key放入受控 Secret而不是模板。迁移必须作为单独 Change Set完成，
重新检查辅助模型和 fallback，防止同时启用 ChatGPT订阅、OpenAI API和 Bedrock三条计费路径。

## 回滚边界

回滚到 Bedrock不是自动 fallback，而是需要所有者批准的部署变更。回滚时必须同时恢复：

1. EC2 Role的 Bedrock最小调用权限；
2. 主模型和必要辅助模型配置；
3. AWS预算与 Budget Action有效性验证；
4. Token Observer中的 Provider路由验收。

这保证“模型供应商切换”始终是可审查的基础设施变更，而不是 Agent运行时自行做出的付费决策。
