#!/usr/bin/env python3
"""PreToolUse: Edit/Write のスコープ外・大容量ファイル・秘密情報を含む
書き込みをブロックする。

- 環境変数 CLAUDE_WORK_SCOPE があればそのパス配下のみ許可
- なければカレントディレクトリ配下を許可
- .pth / checkpoints/ / outputs/ / runs/ 等の生成物は常にブロック
- .env / credentials.json / 秘密鍵ファイルは常にブロック
- 書き込み内容にAPIキーらしき文字列が含まれる場合もブロック
"""
import json
import os
import re
import sys

from _common import (
    ARTIFACT_DIR_PATTERNS,
    ARTIFACT_EXTENSIONS,
    BLOCKED_EXTENSIONS,
    BLOCKED_FILENAMES,
    SECRET_CONTENT_PATTERNS,
)


def contains_secret(text):
    for pat in SECRET_CONTENT_PATTERNS:
        if re.search(pat, text):
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    abs_path = os.path.abspath(file_path)
    norm = abs_path.replace("\\", "/")
    basename = os.path.basename(norm)
    _, ext = os.path.splitext(basename)

    if basename in BLOCKED_FILENAMES or ext.lower() in BLOCKED_EXTENSIONS:
        print(
            f"[guard_scope] BLOCKED: 秘密情報ファイルの可能性がある書き込みです: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    if content and contains_secret(content):
        print(
            f"[guard_scope] BLOCKED: 書き込み内容に秘密情報らしき文字列が含まれています: {file_path}\n"
            f"APIキーや秘密鍵は環境変数や .gitignore 対象の設定ファイルで管理してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    if ext.lower() in ARTIFACT_EXTENSIONS or any(
        pat in norm for pat in ARTIFACT_DIR_PATTERNS
    ):
        print(
            f"[guard_scope] BLOCKED: 生成物/大容量ファイルへの書き込みは禁止です: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    if scope:
        allowed_root = os.path.abspath(scope)
    else:
        allowed_root = os.path.abspath(os.getcwd())

    allowed_norm = allowed_root.replace("\\", "/")
    if not norm.startswith(allowed_norm):
        print(
            f"[guard_scope] BLOCKED: 作業スコープ({allowed_root})外への書き込みです: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
