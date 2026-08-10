# 📱 codex-iMessage-notify

通过 iMessage 在 Mac 上启动独立的 Codex CLI 任务，并把最终回复发送回手机；也可以在 Codex Desktop/CLI 完成任务、等待选择或请求授权时收到通知。

> Run Codex from a self-to-self iMessage and receive complete task results or lifecycle notifications on your phone.

> [!IMPORTANT]
> 真实手机号、Apple ID、消息内容和本机路径只保存在本机。`config.env`、运行队列和读取水位线均被 Git 忽略。

## 功能

- 手机发送 `Codex <指令>` 或 `Codex 信息：<指令>`，Mac 后台启动独立的 `codex exec`。
- 把 Codex 的最终可见回复发送回 iMessage，不发送隐藏推理过程。
- Codex Desktop/CLI 的 `Stop` 与 `PermissionRequest` Hook 可发送完成、选择和授权提醒。
- 长回复优先按段落和行边界分片，保留空行与换行。
- 仅接受配置中的本人地址及一对一会话，发送端也拒绝非本人目标。
- 默认使用 `read-only` 沙箱执行手机指令。

## 工作原理

```text
iPhone / Apple Watch                    Mac
┌──────────────────────┐               ┌────────────────────────────┐
│ Codex 检查仓库状态    │ ── iMessage ─►│ poll.py 只读 Messages DB   │
└──────────────────────┘               │            │               │
             ▲                         │            ▼               │
             │                         │       codex exec            │
             │                         │            │               │
             └──── 完整结果/通知 ───────│ queue → send.sh → Messages │
                                       └────────────────────────────┘
```

远程指令与桌面通知是两条独立链路：

1. `codex-remote-daemon.sh` 轮询本人发给自己的 iMessage，执行新的 Codex CLI 会话并回传结果。
2. Codex Hook 把当前任务的可见最终回复写入本地队列，用户级 LaunchAgent 再调用 Messages 发送。

Hook 不会把 iMessage 回复注入现有 Codex Desktop 对话；手机发出的指令总是独立的 CLI 任务。

## 要求

- macOS，且 Messages 已登录 iMessage。
- 已安装并登录 [Codex CLI](https://developers.openai.com/codex/cli)。
- Python 3。
- 读取进程拥有“完全磁盘访问权限”，发送进程拥有控制 Messages 的“自动化”权限。

## 安装

### 1. 配置本人地址

```bash
cp config.env.example config.env
```

编辑 `config.env`：

```bash
IMSG_HANDLES="you@example.com,+10000000000"
IMSG_REPLY_TO="you@example.com"
IMSG_NOTIFY_TO="+10000000000"
```

`IMSG_HANDLES` 应列出你的全部 iMessage 身份。真实值不要提交到 Git。

### 2. 验证 Messages 权限

```bash
sqlite3 ~/Library/Messages/chat.db "SELECT 1"
python3 bin/poll.py --init
bin/send.sh "iMessage send test"
```

如果数据库命令出现 `authorization denied`，请在“系统设置 → 隐私与安全性 → 完全磁盘访问权限”中授权真正运行 `poll.py` 的 Python 或终端进程，并重启该进程。

首次运行 `send.sh` 时，macOS 会请求控制 Messages 的权限。

### 3. 启动手机远程指令

把 `engine/com.user.imsg-codex-remote.plist.example` 中的 `__PATH_TO_REPO__` 替换为仓库绝对路径，然后执行：

```bash
cp engine/com.user.imsg-codex-remote.plist.example \
  ~/Library/LaunchAgents/com.user.imsg-codex-remote.plist
launchctl load -w ~/Library/LaunchAgents/com.user.imsg-codex-remote.plist
```

现在可以在手机上给自己发送：

```text
Codex 检查当前仓库状态并给出简短结论
```

### 4. 启用所有 Codex 任务的完成通知

先启动通知桥接器：

```bash
cp engine/com.user.imsg-codex-notify.plist.example \
  ~/Library/LaunchAgents/com.user.imsg-codex-notify.plist
launchctl load -w ~/Library/LaunchAgents/com.user.imsg-codex-notify.plist
```

然后把 `hooks/codex-global.hooks.example.json` 复制或合并到 `~/.codex/hooks.json`，将 `__PATH_TO_REPO__` 替换为本仓库绝对路径。

> [!WARNING]
> 不要直接覆盖已有的 `~/.codex/hooks.json`。如文件已存在，请合并 `Stop` 和 `PermissionRequest` 两组配置。

最后在 Codex 中打开 `/hooks`，检查命令路径并明确设为可信。仅 `enabled=true` 不够；未信任的 Hook 不会运行。脚本或路径变化后，Codex 会要求重新审核。

仓库内的 `.codex/hooks.json` 只用于本项目；用户级 `~/.codex/hooks.json` 才会覆盖其他 Codex 项目。

## 配置

| 变量 | 默认值 | 用途 |
|---|---:|---|
| `IMSG_HANDLES` | 空 | 允许收发的本人 iMessage 地址列表 |
| `IMSG_REPLY_TO` | 空 | 默认回复地址 |
| `IMSG_NOTIFY_TO` | 空 | 完成通知目标，通常设为自己的手机号 |
| `IMSG_COMMAND_PREFIXES` | `Codex ,Codex 信息：` | 可触发远程任务的前缀 |
| `IMSG_POLL_INTERVAL` | `15` | Messages 轮询间隔，单位秒 |
| `IMSG_CHUNK_SIZE` | `1200` | 远程回复单条字符上限 |
| `IMSG_MAX_CHUNKS` | `10` | 远程回复最大分片数 |
| `IMSG_CODEX_CHUNK_SIZE` | `1200` | Desktop 通知单条字符上限 |
| `IMSG_CODEX_MAX_CHUNKS` | `20` | Desktop 通知最大分片数 |
| `CODEX_WORKDIR` | 仓库根目录 | 手机任务的工作目录 |
| `CODEX_REMOTE_SANDBOX` | `read-only` | 手机任务的 Codex 沙箱 |
| `CODEX_REMOTE_APPROVE` | `0` | 是否启用自动审批；不建议开启 |

## 安全设计

- 只读打开 `~/Library/Messages/chat.db`。
- 只处理 `is_from_me=0`、发送方属于 `IMSG_HANDLES`、一对一且带指定前缀的消息。
- `send.sh` 只允许向配置中的本人地址发送。
- 手机任务默认是新的 `read-only` Codex 会话，不会继承当前 Desktop 会话。
- Hook 只读取 `last_assistant_message` 等用户可见字段，不发送隐藏思维链。
- 所有本机状态都位于被忽略的 `config.env` 和 `state/`。

手机远程执行仍然具有风险：提示词可能诱导工具访问本地信息。除非完全理解影响，否则不要开启 `CODEX_REMOTE_APPROVE=1`，也不要改为 `danger-full-access`。

## 测试与排障

```bash
python3 -m unittest discover -s tests -v
bash -n bin/send.sh engine/*.sh
python3 -m py_compile bin/*.py hooks/*.py
```

日志：

- `/tmp/imsg-codex-remote.out.log`
- `/tmp/imsg-codex-remote.err.log`
- `/tmp/imsg-codex-notify.out.log`
- `/tmp/imsg-codex-notify.err.log`

常见问题：

- 手工测试能发送、任务结束不发送：打开 `/hooks`，确认 `Stop` Hook 为 `trusted`。
- Mac 收到但手机不提醒：把 `IMSG_NOTIFY_TO` 设置为自己的手机号会话。
- 修改 Hook 后停止运行：定义哈希已变化，需要在 `/hooks` 重新审核。
- 队列存在 `.msg` 文件：检查通知 LaunchAgent、Messages 自动化权限和错误日志。

## 隐私检查

发布前可运行：

```bash
git status --short
git ls-files | grep -E '(^|/)(config\.env|state/|__pycache__/)' && exit 1 || true
git grep -nE '/Users/|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[A-Za-z]{2,}'
```

示例中的 `you@example.com` 与 `+10000000000` 是占位符。

## License

[MIT](LICENSE)
