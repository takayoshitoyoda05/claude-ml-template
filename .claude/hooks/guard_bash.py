#!/usr/bin/env python3
"""PreToolUse: 危険な Bash コマンド・大容量/秘密情報ファイルの git add・
リダイレクトによる秘密情報ファイルへの書き込み・コミットメッセージ規約を
チェックする。

コミットメッセージ規約(ステップ番号必須)は CLAUDE_COMMIT_STEP_RULE=1 の
ときのみ有効(ml-pipeline実行時を想定。通常の手動コミットを妨げないため)。
"""
import json
import os
import re
import sys

from _common import (
    ARTIFACT_EXTENSIONS,
    BLOCKED_EXTENSIONS,
    BLOCKED_FILENAMES,
    SECRET_CONTENT_PATTERNS,
)

DANGER_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+~",
    r"rm\s+-rf\s+\$HOME",
    r"git\s+reset\s+--hard",
    r"git\s+push\s+.*--force",
    r"git\s+push\s+-f\b",
    r":\(\)\{.*\}:",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]

BLOCKED_ADD_EXT = sorted(ARTIFACT_EXTENSIONS | BLOCKED_EXTENSIONS)


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

    for pat in SECRET_CONTENT_PATTERNS:
        if re.search(pat, cmd):
            print(
                "[guard_bash] BLOCKED: コマンドに秘密情報らしき文字列が含まれています。",
                file=sys.stderr,
            )
            sys.exit(2)

    # リダイレクト(> / >>)で秘密情報ファイルへ直接書き込むのをブロック
    # (guard_scope は Edit/Write しか監視しないため、Bash側の穴を塞ぐ)
    for target in re.findall(r">{1,2}\s*(\S+)", cmd):
        target = target.strip("\"'")
        base = os.path.basename(target.replace("\\", "/"))
        _, ext = os.path.splitext(base)
        if base in BLOCKED_FILENAMES or ext.lower() in BLOCKED_EXTENSIONS:
            print(
                f"[guard_bash] BLOCKED: 秘密情報ファイル({base})へのリダイレクト書き込みは禁止です。",
                file=sys.stderr,
            )
            sys.exit(2)

    if re.search(r"git\s+add", cmd):
        for ext in BLOCKED_ADD_EXT:
            if ext in cmd:
                print(
                    f"[guard_bash] BLOCKED: 大容量/秘密情報ファイル({ext})の git add は禁止です。"
                    f".gitignore に追加してください。",
                    file=sys.stderr,
                )
                sys.exit(2)
        for name in BLOCKED_FILENAMES:
            if name in cmd:
                print(
                    f"[guard_bash] BLOCKED: 秘密情報ファイル({name})の git add は禁止です。",
                    file=sys.stderr,
                )
                sys.exit(2)

    if os.environ.get("CLAUDE_COMMIT_STEP_RULE", "") == "1" and re.search(
        r"git\s+commit", cmd
    ):
        m = re.search(r"-m\s+[\"']([^\"']*)[\"']", cmd)
        if m and not re.search(r"\d", m.group(1)):
            print(
                f"[guard_bash] BLOCKED: コミットメッセージに計画のステップ番号(数字)が"
                f"含まれていません: {m.group(1)}\n"
                f"例: 'Step 2: fix interpolation formula'",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
