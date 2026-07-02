#!/usr/bin/env python3
"""PreToolUse: 危険な Bash コマンド・大容量ファイルの git add をブロックする。"""
import json
import re
import sys

# 危険コマンドのパターン
DANGER_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\$HOME",
    r"git\s+reset\s+--hard",
    r"git\s+push\s+.*--force",
    r"git\s+push\s+-f\b",
    r":\(\)\{.*\}:",  # fork bomb
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]

# git add で危険な拡張子
BLOCKED_ADD = [".pth", ".pt", ".ckpt", ".safetensors"]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    for pat in DANGER_PATTERNS:
        if re.search(pat, cmd):
            print(
                f"[guard_bash] BLOCKED: 危険なコマンドを検出しました: {cmd}\n"
                f"本当に必要な場合は Claude Code の外で手動実行してください。",
                file=sys.stderr,
            )
            sys.exit(2)

    # git add に大容量拡張子が含まれていないか
    if re.search(r"git\s+add", cmd):
        for ext in BLOCKED_ADD:
            if ext in cmd:
                print(
                    f"[guard_bash] BLOCKED: 大容量ファイル({ext})の git add は禁止です。"
                    f".gitignore に追加してください。",
                    file=sys.stderr,
                )
                sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
