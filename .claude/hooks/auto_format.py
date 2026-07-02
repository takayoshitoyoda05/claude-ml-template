#!/usr/bin/env python3
"""PostToolUse: .py ファイル編集後に ruff format を自動実行する(あれば)。"""
import json
import shutil
import subprocess
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py"):
        sys.exit(0)

    # ruff が無ければ何もしない(fail open)
    if shutil.which("ruff") is None:
        sys.exit(0)

    try:
        subprocess.run(
            ["ruff", "format", file_path],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass  # 整形失敗は握りつぶす(コードは既に書かれている)

    sys.exit(0)


if __name__ == "__main__":
    main()
