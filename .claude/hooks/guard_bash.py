#!/usr/bin/env python3
"""PreToolUse: 危険な Bash コマンド・大容量/秘密情報ファイルの git add・
リダイレクト/tee による秘密情報ファイル/フック設定への書き込み・
コミットメッセージ規約をチェックする。

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
    PROTECTED_PATH_PATTERNS,
    SECRET_CONTENT_PATTERNS,
)

DANGER_PATTERNS = [
    r"git\s+reset\s+--hard",
    r"git\s+push\s+.*--force",
    r"git\s+push\s+-f\b",
    r"git\s+push\s+\S+\s+\+\S+",  # 強制pushの別記法(+refspec)
    r":\(\)\{.*\}:",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
]

BLOCKED_ADD_EXT = sorted(ARTIFACT_EXTENSIONS | BLOCKED_EXTENSIONS)


def is_dangerous_rm(cmd):
    """再帰かつ強制の rm が絶対パス・~・$HOME を対象にしていたら True。

    -rf / -fr / -r -f のような表記ゆれをフラグ解析で吸収する。
    """
    for m in re.finditer(r"\brm\s+([^|;&]+)", cmd):
        args = m.group(1).split()
        flags = "".join(a.lstrip("-") for a in args if a.startswith("-")).lower()
        targets = [a.strip("\"'") for a in args if not a.startswith("-")]
        if "r" in flags and "f" in flags:
            for t in targets:
                if t.startswith(("/", "~", "$HOME")):
                    return True
    return False


def write_targets(cmd):
    """リダイレクト(> / >>)と tee の書き込み先を列挙する。"""
    targets = re.findall(r">{1,2}\s*(\S+)", cmd)
    targets += re.findall(r"\btee\s+(?:-[a-zA-Z]+\s+)*(\S+)", cmd)
    return [t.strip("\"'") for t in targets]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = data.get("tool_input", {}).get("command", "")
    if not cmd:
        sys.exit(0)

    if is_dangerous_rm(cmd) or any(re.search(p, cmd) for p in DANGER_PATTERNS):
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

    # リダイレクト/tee で秘密情報ファイルやフック設定へ直接書き込むのをブロック
    # (guard_scope は Edit/Write しか監視しないため、Bash側の穴を塞ぐ)
    for target in write_targets(cmd):
        norm = target.replace("\\", "/")
        base = os.path.basename(norm)
        _, ext = os.path.splitext(base)
        if base in BLOCKED_FILENAMES or ext.lower() in BLOCKED_EXTENSIONS:
            print(
                f"[guard_bash] BLOCKED: 秘密情報ファイル({base})への書き込みは禁止です。",
                file=sys.stderr,
            )
            sys.exit(2)
        abs_norm = os.path.abspath(target).replace("\\", "/")
        if any(pat in abs_norm for pat in PROTECTED_PATH_PATTERNS):
            print(
                f"[guard_bash] BLOCKED: フック/設定({target})への書き込みは禁止です。"
                f"変更が必要な場合はユーザーが手動で編集してください。",
                file=sys.stderr,
            )
            sys.exit(2)

    if re.search(r"git\s+add\b", cmd):
        # 一括ステージは生成物混入の主経路なのでパス限定を促す
        if re.search(r"git\s+add\s+(?:-[A-Za-z]*A[A-Za-z]*|--all|\*|\.(?:/)?(?:\s|$))", cmd):
            print(
                "[guard_bash] BLOCKED: git add の一括ステージ(. / -A / --all / *)は"
                "禁止です。対象パスを明示してください(例: git add src/train.py)。",
                file=sys.stderr,
            )
            sys.exit(2)
        for ext in BLOCKED_ADD_EXT:
            if re.search(re.escape(ext) + r"(?=[\s\"']|$)", cmd):
                print(
                    f"[guard_bash] BLOCKED: 大容量/秘密情報ファイル({ext})の git add は禁止です。"
                    f".gitignore に追加してください。",
                    file=sys.stderr,
                )
                sys.exit(2)
        for name in BLOCKED_FILENAMES:
            if re.search(r"(?:^|[\s/\"'])" + re.escape(name) + r"(?=[\s\"']|$)", cmd):
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
