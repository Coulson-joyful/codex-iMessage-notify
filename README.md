# codex-iMessage-notify
这个小工具是为了人不在电脑前可以通过iMessage与codex进行交互，最初也是基于 cc 不太方便实现相关功能制作的，获取任务执行完成的消息以及向codex发送远程指令。

与chatgpt app的区别是他是以 iMessage 信息形式发送，手表或手机都能收到结果消息，直走流量，只要codex 网络正常，任务完成后会调用在这个小工具，只消耗流量不消耗 token。
思路来源是iphone、apple watch、MacBook基于苹果的生态，识别你自己id 的方式有手机号和邮箱，两个都可以代表自己。实现自己给自己发信息，不借助于其他第三方 app 就可以实现。
让 ai 再工作中你可以去打打游戏听听歌看看电视，任务完成或者遇到其他需要的选择时，再过来处理或者通过远程告诉 codex 下一步该如何做。比如蓝牙语音输入或者 iMessage 发送指令。

和现阶段的 chatgpt 功能其实有些重复了，不过它依然跑在我的 mac 上，有时候我的 iphone 没有 vpn 时也能及时提醒我任务完成了。

真实手机号、Apple ID、消息内容和本机路径留在本机。`config.env`、不要发送给 ai 请自行配置。
剩下的都是 AI 写的，本人文笔目前很烂。
## 能做什么

- 手机发送 `Codex <指令>` 或 `Codex 信息：<指令>`，Mac 后台启动独立的 `codex exec`。
- 把 Codex 的最终可见回复发送回 iMessage，不发送隐藏推理过程。
- Codex Desktop/CLI 的 `Stop` 与 `PermissionRequest` Hook 发送完整的可见最终结论、待选择项和授权提醒。
- 长回复优先按段落和行边界分片，保留空行与换行。
- 额度耗尽时，后台独立读取本机 Codex 错误日志并发送原因和处理建议，不依赖模型生成最终回复。同类错误按任务在 15 分钟内只提醒一次；没有任务身份的桌面错误使用 `Codex` 标题。
- 仅接受配置中的本人地址及一对一会话，发送端也拒绝非本人目标。
- 默认使用 `read-only` 沙箱执行手机指令。

## 两条链路，别混在一起

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
2. Codex Hook 把当前任务的完整可见结论、待选择项或授权状态写入本地队列，用户级 LaunchAgent 再调用 Messages 发送。

手机任务不是在续聊桌面上的对话。Hook 不会把手机回复塞回现有 Codex Desktop 会话；每条远程指令都会启动独立的 CLI 任务。授权提醒也只是提醒，要回到 Codex 的授权界面处理。

通知桥接器还会运行 `watch_limits.py`，只读 `~/.codex/logs_*.sqlite` 和最近两天的 macOS Codex 桌面日志。第一次启动只记住当前位置，不补发旧错误。之后读到的新额度错误会进入同一发送队列。只发送固定原因与建议，不转发错误堆栈、凭证或隐藏推理。预热请求额度不足也会提醒，但不会据此断言整个任务已停止。日志格式属于本机实现细节，升级后若格式变化需更新识别规则。Mac 和通知 LaunchAgent 都得开着；电脑关机或桥接器停止时，不会收到这类提醒。

### Claudian（Obsidian）

在 Claudian 中也一样：任务状态以 Obsidian 里的界面为准，iMessage 只提示“已完成”或“等待选择”。请使用 Claudian **2.1.3 或更高版本**；该版本加入了 Codex 首轮回复渲染和漏失完成事件的恢复处理，避免任务已完成却在界面中显示 `Interrupted`。

## 安装前

- macOS，且 Messages 已登录 iMessage。
- 已安装并登录 [Codex CLI](https://developers.openai.com/codex/cli)。
- Python 3。
- 读取进程拥有“完全磁盘访问权限”，发送进程拥有控制 Messages 的“自动化”权限。

## 安装

以下命令在仓库根目录执行。首次使用可以先克隆：

```bash
git clone git@github.com:Coulson-joyful/codex-iMessage-notify.git
cd codex-iMessage-notify
```

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

### 4. 给其他 Codex 项目也发通知

先启动通知桥接器：

```bash
cp engine/com.user.imsg-codex-notify.plist.example \
  ~/Library/LaunchAgents/com.user.imsg-codex-notify.plist
launchctl load -w ~/Library/LaunchAgents/com.user.imsg-codex-notify.plist
```

然后把 `hooks/codex-global.hooks.example.json` 复制或合并到 `~/.codex/hooks.json`，将 `__PATH_TO_REPO__` 替换为本仓库绝对路径。

不要直接覆盖已有的 `~/.codex/hooks.json`。如果文件已经存在，合并 `Stop` 和 `PermissionRequest` 两组配置，保留其他钩子。

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

## 权限和限制

- 只读打开 `~/Library/Messages/chat.db`。
- 只处理 `is_from_me=0`、发送方属于 `IMSG_HANDLES`、一对一且带指定前缀的消息。
- `send.sh` 只允许向配置中的本人地址发送。
- 手机任务默认是新的 `read-only` Codex 会话，不会继承当前 Desktop 会话。
- Hook 只读取 `last_assistant_message` 等用户可见字段，不发送隐藏思维链。
- 所有本机状态都位于被忽略的 `config.env` 和 `state/`。

本人发来的指令也不代表没有风险：提示词仍可能让工具访问不该访问的本地信息。除非清楚这些权限的影响，否则不要开启 `CODEX_REMOTE_APPROVE=1`，也不要改为 `danger-full-access`。

## 测试和排查问题

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

## 公开提交前检查一下

提交前可以用下面的命令检查本机配置、运行状态和个人信息有没有混进来。命中内容需要人工查看；示例邮箱、文档说明也可能被匹配，不能只凭命令退出码认定检查通过：

```bash
git status --short
git ls-files | grep -E '(^|/)(config\.env|state/|__pycache__/)' && exit 1 || true
git grep -nE '/Users/|[[:alnum:]._%+-]+@[[:alnum:].-]+\.[A-Za-z]{2,}'
```

示例中的 `you@example.com` 与 `+10000000000` 是占位符。

## License

[MIT](LICENSE)
