#!/usr/bin/env python3
"""Read self-to-self `cc ` commands from Messages' local chat database."""
import os, pathlib, sqlite3, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = os.path.expanduser("~/Library/Messages/chat.db")

def config():
    result = {}
    try:
        for line in (ROOT / "config.env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return result

CONF = config()
HANDLES = [x.strip() for x in CONF.get("IMSG_HANDLES", "").split(",") if x.strip()]
COMMAND_PREFIXES = sorted(
    [prefix.strip() for prefix in CONF.get("IMSG_COMMAND_PREFIXES", "Codex ,Codex 信息：").split(",") if prefix.strip()],
    key=len,
    reverse=True,
)
STATE = ROOT / "state" / "last_rowid"

def body_text(blob):
    if not blob or b"NSString" not in blob:
        return ""
    try:
        rest = blob.split(b"NSString", 1)[1]
        marker = rest.find(b"\x2b")
        if marker < 0:
            return ""
        rest = rest[marker + 1:]
        first = rest[0]
        if first == 0x81:
            size, rest = int.from_bytes(rest[1:3], "little"), rest[3:]
        elif first == 0x82:
            size, rest = int.from_bytes(rest[1:5], "little"), rest[5:]
        else:
            size, rest = first, rest[1:]
        return rest[:size].decode("utf-8", "replace").strip()
    except Exception:
        return ""

def main():
    if not HANDLES:
        sys.exit("IMSG_HANDLES is empty; configure config.env first.")
    init = len(sys.argv) > 1 and sys.argv[1] == "--init"
    strict = CONF.get("IMSG_STRICT_SELF", "1") == "1"
    placeholders = ",".join("?" for _ in HANDLES)
    strict_sql = "" if not strict else f"""
      AND m.destination_caller_id IN ({placeholders}) AND c.style = 45
      AND (SELECT COUNT(*) FROM chat_handle_join x WHERE x.chat_id = c.ROWID) = 1"""
    sql = f"""SELECT DISTINCT m.ROWID,h.id,m.text,m.attributedBody
      FROM message m JOIN handle h ON h.ROWID=m.handle_id
      JOIN chat_message_join j ON j.message_id=m.ROWID JOIN chat c ON c.ROWID=j.chat_id
      WHERE m.is_from_me=0 AND h.id IN ({placeholders}) {strict_sql} AND m.ROWID>?
      ORDER BY m.ROWID"""
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as con:
        current = con.execute("SELECT COALESCE(MAX(ROWID),0) FROM message").fetchone()[0]
        if init or not STATE.exists():
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(str(current))
            return
        last = int(STATE.read_text().strip())
        params = (*HANDLES, *HANDLES, last) if strict else (*HANDLES, last)
        rows = con.execute(sql, params).fetchall()
    required = CONF.get("IMSG_REQUIRE_CC", "1") == "1"
    for _, handle, text, blob in rows:
        message = (text or "").strip() or body_text(blob)
        command = next((message[len(prefix):].strip() for prefix in COMMAND_PREFIXES
                        if message.lower().startswith(prefix.lower())), None)
        if command is None and not required:
            command = message
        if command:
            print(f"{handle}\t{command}")
    if current > last:
        STATE.write_text(str(current))

if __name__ == "__main__":
    main()
