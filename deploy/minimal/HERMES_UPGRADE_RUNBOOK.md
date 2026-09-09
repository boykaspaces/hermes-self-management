# Hermes升级与本地 Patch恢复手册

本手册是 Hermes生产升级的强制门禁。升级不能只以`hermes update`命令成功或 Gateway恢复
运行作为完成标准；必须逐项处理下表中的本地改动，并把文末验收记录保存到部署方的
私有 operations repository 后才能关闭升级任务。

## Patch清单

| ID | 状态 | 类型 | 文件/入口 | 目的 | 升级后的处理 |
| --- | --- | --- | --- | --- | --- |
| `P-001` | 已退役 | Hermes源码 | `agent/bedrock_adapter.py` | 从 Nova prompt-cache allowlist删除`amazon.nova`，避免发送不兼容的`cachePoint` | 当前唯一 Provider为`openai-codex`且 EC2 Role无 Bedrock调用权限，不再恢复。升级后确认该本地 diff自然消失；重新启用 Bedrock/Nova前必须重新评估。 |
| `P-002` | 活跃，安全关键 | Hermes源码 | `tools/browser_tool.py` | 让本机 Chromium同样执行私网与 IMDS URL检查 | 先检查新版本是否原生覆盖本机 backend；没有则移植旧补丁。私网、IMDS和跳转测试未通过时禁止启动生产 Gateway。 |
| `P-003` | 活跃，资源关键 | Hermes源码与测试 | `tools/environments/docker.py`、`tests/tools/test_docker_environment.py` | 使用 Podman兼容的`{{.Labels}}`并解析 Podman/Docker两种 label格式，恢复跨进程容器复用 | 先检查上游是否已修复；没有则移植旧补丁。必须验证不同 Hermes进程复用同一容器且 egress标签不被错误复用。 |
| `P-004` | 活跃 | 插件运行时包装 | `token_observer/runtime_instrumentation.py` | 给 Hook副本增加 Prompt组件大小，不修改模型请求 | 不恢复 Hermes源码。Gateway重启后由 CloudFormation管理的插件自动重新挂载；必须用一次真实调用确认组件数据重新出现。 |
| `P-005` | 活跃，网络关键 | Hermes源码与测试 | `hermes_cli/proxy_cli.py`、`tests/test_iron_proxy_cli.py` | 支持没有 Provider Secret映射的显式 allowlist-only代理配置 | 先检查上游是否已有等价模式；没有则移植补丁，并验证空映射、冲突参数和默认拒绝行为。 |
| `P-006` | Source候选，沙箱兼容关键 | Hermes源码与测试 | `tools/environments/docker.py`、`tests/tools/test_docker_environment.py` | 仅把目标恰好为`/workspace`的 volume视为替换父沙箱，嵌套挂载继续保留父沙箱 | 先检查上游是否已改为精确目标判断；没有则移植补丁，并验证持久与临时沙箱、嵌套目标、挂载选项及异常输入。是否已部署只查部署方记录。 |

这里的“之前两个 Patch”是`P-001` Nova cache与`P-002` Browser私网防护；之后又增加了
`P-003` Podman复用。`P-004`常被口头称为 Patch，但它不修改 Hermes checkout。之后的
`P-005`与`P-006`分别补充 allowlist-only代理配置和嵌套 workspace挂载兼容性。

## 当前受管 Patch set

本仓库当前受管 source Patch set为`patches/hermes-v0.21.0-29112bef/`，只接受完整 commit
`29112bef099274229cadff79cdff7bf7b99c4b77`。其中包含`P-002`、`P-003`、`P-005`、
`P-006`的精确 diff和应用后文件 SHA-256。通用入口为：

```bash
deploy/minimal/apply-hermes-patches.sh apply
deploy/minimal/apply-hermes-patches.sh verify
deploy/minimal/apply-hermes-patches.sh restore
```

这里的清单描述可交付 source，不证明某个运行环境已经发布或应用同一归档；当前 deployed
revision、证据与回滚指针必须以部署方的私有记录为准。

本地或其他安装目录可用`HERMES_REPO`和`HERMES_PATCH_SET`覆盖默认路径。脚本先核对 commit；
随后只允许 clean apply、clean reverse-check（已应用）或 clean reverse（恢复）。任何部分应用、
未知源码状态或最终哈希不匹配都会失败，不做模糊搜索替换。

CloudFormation把同一 Patch set作为确定性归档保存在`HermesInstance.Metadata`。Gateway的
`ExecStartPre`先原子同步归档，再幂等执行`apply`，因此实例重启会验证而不是丢失 Patch。
这不表示未知 Hermes版本可以自动升级：更新到新 commit前必须先完成上游审查、生成新的版本化
Patch set、运行完整验收并发布对应模板。当前模板遇到 commit不匹配会拒绝启动 Gateway。

## 阶段一：升级前冻结证据

- [ ] 记录 Stack、实例 ID、Hermes版本和当前 commit。
- [ ] 创建可恢复的 EC2/EBS快照或确认最近备份可用。
- [ ] 在 Hermes checkout记录`git status --short`。
- [ ] 将以下精确 diff保存到 checkout之外，并记录 SHA-256：
  - `agent/bedrock_adapter.py`
  - `tools/browser_tool.py`
  - `tools/environments/docker.py`
  - `tests/tools/test_docker_environment.py`
- [ ] 复制所有`*.pre-*-fix.bak`到 checkout之外的升级归档目录。
- [ ] 记录当前 Gateway、Dashboard、Telegram、Viewer、Browser和 Podman验收基线。
- [ ] 复制`/home/hermes/.hermes/install-manifest/`，保存当前实际依赖版本与安装身份。
- [ ] 确认回滚目标 commit和上一版 CloudFormation `TemplateURL`。

不得只依赖 Hermes自动创建的 git stash。升级前证据必须位于
`/home/hermes/.hermes/hermes-agent`之外，避免 checkout重建或清理时一起丢失。

建议在实例上以`hermes`用户执行以下只读冻结命令，并将日期替换为实际升级批次：

```bash
PATCH_ARCHIVE_DIR=/home/hermes/.hermes/upgrade-evidence/2026-09-05
REPO=/home/hermes/.hermes/hermes-agent
install -d -m 0700 "$PATCH_ARCHIVE_DIR"
git -C "$REPO" rev-parse HEAD >"$PATCH_ARCHIVE_DIR/old-commit.txt"
git -C "$REPO" status --short >"$PATCH_ARCHIVE_DIR/git-status.txt"
git -C "$REPO" diff -- \
  agent/bedrock_adapter.py \
  tools/browser_tool.py \
  tools/environments/docker.py \
  tests/tools/test_docker_environment.py \
  >"$PATCH_ARCHIVE_DIR/local-patches.diff"
(
  cd "$REPO"
  find . -type f -name '*.pre-*-fix.bak' -print0 | \
    tar --null --files-from=- -czf "$PATCH_ARCHIVE_DIR/pre-fix-backups.tar.gz"
)
sha256sum \
  "$PATCH_ARCHIVE_DIR/old-commit.txt" \
  "$PATCH_ARCHIVE_DIR/git-status.txt" \
  "$PATCH_ARCHIVE_DIR/local-patches.diff" \
  "$PATCH_ARCHIVE_DIR/pre-fix-backups.tar.gz" \
  >"$PATCH_ARCHIVE_DIR/SHA256SUMS"
```

冻结目录本身必须进入实例快照或独立备份。`SHA256SUMS`生成后不要再修改同一批次文件；需要
补充证据时创建新批次目录。

## 阶段二：升级前清理本地源码改动

1. 停止 Gateway，避免升级期间继续处理 Telegram和工具调用。
2. 将冻结阶段保存的 diff与当前工作树再次比较；不一致时停止升级并人工审查。
3. 恢复`P-002`、`P-003`、`P-005`、`P-006`涉及文件的上游版本，使这些受管文件在升级前保持 clean；`P-001`应保持退役。
4. 再次检查`git status`；其他未知修改不得被顺手删除或混入补丁归档。
5. 执行 Hermes官方升级流程，并记录新版本、commit和迁移输出。
6. 从目标 commit重新计算`install.sh`、`uv.lock`和`package-lock.json` SHA-256，审查精确
   Agent Browser版本与 x86_64容器镜像 digest，并同步更新 CloudFormation参数。
7. 对目标 commit生成新的版本化 Patch set，并在隔离 checkout实际执行一次
   `verify → restore → apply → apply`，验证哈希、可回滚与幂等性。

这一阶段的目的，是避免`hermes update`把旧源码 Patch自动 stash后盲目套到新版本，引发冲突
或把已被上游修复的问题重新引入。

## 阶段三：逐项恢复或退役

### `P-001` Nova cache

- 保持退役，不重新应用。
- 确认有效配置仍为`openai-codex`，没有 Bedrock fallback，EC2 Role没有
  `bedrock:InvokeModel*`。
- 如果未来恢复 Bedrock/Nova，将其作为新的兼容性决策处理，不能直接复用旧 Patch。

### `P-002` Browser私网防护

- 阅读新版本对应代码与测试，判断本机 Chromium是否已经受到与云 Browser相同的 URL安全
  检查。
- 上游已修复：记录对应 commit/测试，删除本地 Patch。
- 上游未修复：将冻结的 diff人工移植到新版本，完成 Python编译和相关测试。
- 这是安全关键项；无法证明行为正确时保持 Gateway停止，而不是跳过。

### `P-003` Podman复用

- 检查复用探针是否仍使用 Docker专用的`{{.Label "hermes-egress"}}`。
- 上游已兼容 Podman：记录对应 commit/测试，删除本地 Patch。
- 上游未兼容：移植`{{.Labels}}`与双格式解析逻辑，并同步移植测试。
- 不自动删除升级前容器；只有确认容器空闲并单独授权后才执行清理。

### `P-004` Token Observer

- 发布包含目标插件版本的 CloudFormation模板。
- 重启 Gateway；`ExecStartPre`会同步插件，插件注册时会重新安装幂等 Runtime wrapper。
- 如果 Hermes内部函数签名变化，Agent仍可运行，但细分指标会降级；此时升级不能标记为完成，
  需要移植 adapter或明确接受降级。

### `P-005` Allowlist-only代理

- 检查新版本是否能在不发现、读取或生成 Provider Secret映射时建立默认拒绝代理。
- 上游已支持：记录对应 commit与负向测试，删除本地 Patch。
- 上游未支持：移植`--allowlist-only`路径，并验证它拒绝 Secret轮换参数、允许空映射且
  保留显式 host allowlist。

### `P-006` 嵌套 Workspace挂载

- 检查用户 volume的容器目标是否按字段解析，而不是用`:/workspace`子串判断。
- 上游已修复：记录对应 commit与持久/临时沙箱测试，删除本地 Patch。
- 上游未修复：移植精确目标解析与回归测试。目标恰好为`/workspace`时不得产生重复父
  挂载；`/workspace/...`嵌套目标和 source路径中的相似文本不得关闭父沙箱。

### 受管恢复器发布顺序

1. 先把新 Patch set和目标 commit同步进 CloudFormation Metadata并运行模板校验。
2. 发布内容寻址的 S3 `TemplateURL`，创建 Change Set。
3. 如果 Change Set包含 EC2 `Replacement=True`则停止；`Conditional`只有在根设备为 EBS、
   Stack Policy明确拒绝`Update:Replace/Update:Delete`且本次已创建快照时才可继续。
4. 执行后确认 Instance ID和根 Volume ID未变化，再重启 Gateway。
5. 从本次 boot日志确认恢复器输出`Applied`或`Already applied`和最终验证成功。

回滚到旧 Hermes commit时，必须同时回退到匹配旧 Patch set的上一版模板；否则当前
`ExecStartPre`会按设计拒绝在未知 commit上启动 Gateway。

## 阶段四：强制验收

- [ ] `git status --short`只包含本次明确保留的活跃源码 Patch，没有`P-001`。
- [ ] `P-002`：公网 URL成功；VPC私网 URL被阻止；`169.254.169.254`被阻止；公网跳转到
  私网/IMDS同样被阻止。
- [ ] `P-003`：至少三个独立 Hermes进程对同一 task/profile复用同一 Podman container ID；
  `network=none`、挂载和 egress标签仍正确；容器数量不随调用线性增长。
- [ ] `P-004`：真实 Agent执行成功；Viewer逐 Loop出现
  `base_system/context/skills/memory`等组件，Tool/MCP次数能归属到正确 Loop。
- [ ] `P-005`：allowlist-only配置不读取 Provider Secret映射，空映射可启动且非 allowlist
  目标保持拒绝。
- [ ] `P-006`：精确`/workspace`替换不重复挂载；嵌套`/workspace/...`在持久和临时
  模式都保留父沙箱。
- [ ] Gateway、Dashboard、Telegram、Viewer均健康。
- [ ] OAuth认证仍有效，模型 Provider为`openai-codex`，没有 Bedrock/fallback调用。
- [ ] CloudFormation Stack和实例状态正常，没有发生非预期替换。
- [ ] 受管 Patch恢复器在实例重启后完成幂等验证；目标文件 SHA-256与 Patch set一致。
- [ ] 新`install-manifest/identity.txt`与 Change Set中的 commit、安装器/锁文件哈希、浏览器
  版本和容器 digest一致；Python与 Node依赖清单已保存到私有验收记录。
- [ ] 将下面的验收记录追加到部署方的私有 deployment record。

任何一项失败，升级状态都是“未完成”。安全关键项失败时保持 Gateway停止；其他项目可以回滚
到旧 Hermes commit和上一版 CloudFormation模板后再恢复服务。

## 每次升级必须追加的记录

```text
Hermes upgrade acceptance
- Date:
- Operator:
- Stack / instance:
- Old version / commit:
- New version / commit:
- Installer / uv.lock / package-lock SHA-256:
- Agent Browser version / coding image digest:
- Installed dependency manifest:
- Snapshot / backup:
- Frozen diff SHA-256:
- P-001: retired / unexpectedly present
- P-002: upstream-fixed(commit) / locally-ported / failed
- P-003: upstream-fixed(commit) / locally-ported / failed
- P-004: auto-restored / adapter-ported / degraded / failed
- P-005: upstream-fixed(commit) / locally-ported / failed
- P-006: upstream-fixed(commit) / locally-ported / failed
- Browser security tests:
- Podman reuse test:
- Token Observer loop test:
- Allowlist-only proxy test:
- Nested workspace mount test:
- Gateway / Dashboard / Telegram / Viewer:
- Provider / fallback / IAM boundary:
- CloudFormation replacement check:
- Rollback performed:
- Final decision: accepted / rolled back / blocked
```
