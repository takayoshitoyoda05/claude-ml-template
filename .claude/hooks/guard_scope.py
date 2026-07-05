#!/usr/bin/env python3
"""PreToolUse: Edit/Write/NotebookEdit のスコープ外・大容量ファイル・
秘密情報を含む書き込みをブロックする。

- 環境変数 CLAUDE_WORK_SCOPE があればそのパス配下のみ許可
- なければカレントディレクトリ配下を許可
- .pth / checkpoints/ / outputs/ / runs/ 等の生成物は常にブロック
- .env / credentials.json / 秘密鍵ファイルは常にブロック
- .claude/hooks/ と settings 系(ガード自身)への書き込みは常にブロック
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
    PROTECTED_PATH_PATTERNS,
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
    file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
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

    # 末尾に "/" を足してから比較する。ディレクトリを末尾スラッシュなしで
    # 指定した場合でも PROTECTED_PATH_PATTERNS の "/.claude/hooks/" と
    # 一致させるため(ファイルパターンは元々末尾スラッシュなしなので影響しない)。
    if any(pat in norm + "/" for pat in PROTECTED_PATH_PATTERNS):
        print(
            f"[guard_scope] BLOCKED: フック/設定(ガード自身)への書き込みは禁止です: {file_path}\n"
            f"変更が必要な場合はユーザーが手動で編集してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    content = (
        tool_input.get("content", "")
        or tool_input.get("new_string", "")
        or tool_input.get("new_source", "")
    )
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

    # 前方一致の誤許可(scope=/work/proj で /work/proj-evil が通る)を防ぐため
    # 末尾スラッシュ付きで比較。Windows は大文字小文字を区別しないので揃える。
    allowed_norm = allowed_root.replace("\\", "/").rstrip("/") + "/"
    target_norm = norm + "/"
    if os.name == "nt":
        allowed_norm = allowed_norm.lower()
        target_norm = target_norm.lower()
    if not target_norm.startswith(allowed_norm):
        print(
            f"[guard_scope] BLOCKED: 作業スコープ({allowed_root})外への書き込みです: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
