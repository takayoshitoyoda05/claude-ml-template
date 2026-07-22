#!/usr/bin/env python3
"""Stop フック: CLAUDE_CROSS_REVIEW=1 のとき、Codexクロスレビューを
完了していなければブロックする。"""

import os
import sys
import tempfile


def main():
    if os.environ.get("CLAUDE_CROSS_REVIEW", "") != "1":
        sys.exit(0)

    sentinel = os.path.join(tempfile.gettempdir(), ".claude-codex-review-done")
    if os.path.exists(sentinel):
        try:
            os.remove(sentinel)
        except OSError:
            pass
        sys.exit(0)

    print(
        "[codex_gate] Codex クロスレビューがまだ実行されていません。\n"
        "先に cross-review スキルを実行してください。\n"
        "  方法: 「クロスレビューして」または「@cross-review を実行して」\n"
        "  スキップしたい場合は CLAUDE_CROSS_REVIEW を 0 に変更してください。",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
