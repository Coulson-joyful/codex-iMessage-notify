# codex-iMessage-notify

Use iMessage with Codex on a Mac, without allowing Codex Desktop itself to control Messages.

There are two separate modes:

1. **Remote CLI tasks** — send yourself `Codex <prompt>`; a user LaunchAgent runs a new, independent `codex exec` session and returns its final message to iMessage.
2. **Desktop notifications** — Codex Desktop hooks queue “completed”, “needs a decision”, and “needs approval” messages; a user LaunchAgent sends the queued notification through Messages.

The second mode does **not** continue an existing Codex Desktop chat from iMessage. Codex Desktop has no documented iMessage inbound-chat interface. Use the first mode for phone-originated, independent tasks.

## Security model

- `poll.py` only accepts received, 1:1 self-to-self Messages with the `cc ` prefix.
- `send.sh` refuses any recipient not listed in `IMSG_HANDLES`.
- `config.env` and notification queues are Git-ignored.
- Long remote replies are split by characters into numbered iMessage parts;
  `IMSG_CHUNK_SIZE` and `IMSG_MAX_CHUNKS` cap delivery.
- Remote Codex uses `read-only` by default. Change `CODEX_REMOTE_SANDBOX` only deliberately; leave `CODEX_REMOTE_APPROVE=0` unless you accept automatic approval for phone-originated work.

## Setup

```bash
cp config.env.example config.env
# Fill your own iMessage handles in config.env.
python3 bin/poll.py --init
bin/send.sh "iMessage send test"
```

Messages automation must be granted to the logged-in user process that runs the LaunchAgents. The bridge deliberately owns this permission; Codex Desktop does not.

The receiver also needs macOS **Full Disk Access** to read Messages' local
database. This project automatically reuses Xcode's Python when available (the
interpreter used by the working `cc` receiver on this Mac). Otherwise set
`IMSG_PYTHON_BIN` to the exact Python executable that has been granted access.

The remote daemon resolves Codex automatically from `/opt/homebrew/bin/codex` or
`/usr/local/bin/codex` and adds those locations to its LaunchAgent PATH (the
Homebrew launcher also needs `node` there). Set `CODEX_BIN` to an absolute path
in `config.env` if your installation uses another location.

### Start remote CLI tasks

Replace `__PATH_TO_REPO__` in `engine/com.user.imsg-codex-remote.plist.example`, then:

```bash
cp engine/com.user.imsg-codex-remote.plist.example ~/Library/LaunchAgents/com.user.imsg-codex-remote.plist
launchctl load -w ~/Library/LaunchAgents/com.user.imsg-codex-remote.plist
```

Now send yourself: `Codex summarize the current git status`.

### Start Desktop reminders

Replace `__PATH_TO_REPO__` in `engine/com.user.imsg-codex-notify.plist.example`, then:

```bash
cp engine/com.user.imsg-codex-notify.plist.example ~/Library/LaunchAgents/com.user.imsg-codex-notify.plist
launchctl load -w ~/Library/LaunchAgents/com.user.imsg-codex-notify.plist
```

Open this project in Codex and use `/hooks` to review and trust `.codex/hooks.json`. The `Stop` hook queues final conclusions (and detects a final question); `PermissionRequest` queues approval reminders. iMessage cannot approve a Codex request.

Logs: `/tmp/imsg-codex-remote.err.log` and `/tmp/imsg-codex-notify.err.log`.
