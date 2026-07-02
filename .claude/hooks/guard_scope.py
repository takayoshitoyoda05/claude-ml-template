#!/usr/bin/env python3
"""PreToolUse: Edit/Write のスコープ外・大容量ファイルへの書き込みをブロックする。

- 環境変数 CLAUDE_WORK_SCOPE があればそのパス配下のみ許可
- なければカレントディレクトリ配下を許可
- .pth / checkpoints/ / outputs/ / runs/ 等の生成物は常にブロック
"""
import json
import os
import sys

# 常にブロックする対象(生成物・大容量)
BLOCKED_PATTERNS = [
    ".pth", ".pt", ".ckpt", ".safetensors",
    "/checkpoints/", "/outputs/", "/runs/", "/.venv/",
    "/_trash_candidates/",
]


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 解析できなければ通す(fail open)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    abs_path = os.path.abspath(file_path)
    norm = abs_path.replace("\\", "/")

    # 1. 生成物・大容量への書き込みは常にブロック
    for pat in BLOCKED_PATTERNS:
        if pat in norm:
            print(
                f"[guard_scope] BLOCKED: 生成物/大容量ファイルへの書き込みは禁止です: {file_path}",
                file=sys.stderr,
            )
            sys.exit(2)

    # 2. スコープ判定
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
