#!/usr/bin/env python3
"""Stop フック: CLAUDE_CROSS_REVIEW=1 のとき、Codexクロスレビューを
完了していなければブロックする。

センチネルはプロジェクト配下(.claude/checkpoints/codex_review_done.txt)に
置き、中身に「レビュー時点の HEAD ハッシュ」を要求する。
HEAD が一致する限りセンチネルは保持される(同じ HEAD に対する再レビューを
要求しない)。レビュー後にコミットが進む(HEAD が変わる)と不一致になり、
古いセンチネルを破棄した上で再レビューを要求する。
中身の照合はエージェント自身による偽装を完全には防げない(HEAD は
計算可能)が、cross-review スキルを経由せず偶然通過することはなくなる。
"""

import os
import subprocess
import sys

SENTINEL = os.path.join(".claude", "checkpoints", "codex_review_done.txt")


def current_head():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def main():
    if os.environ.get("CLAUDE_CROSS_REVIEW", "") != "1":
        sys.exit(0)

    recorded = None
    if os.path.exists(SENTINEL):
        try:
            # utf-8-sig: PowerShell の Out-File -Encoding utf8 が付ける BOM を許容
            with open(SENTINEL, encoding="utf-8-sig") as f:
                recorded = f.read().strip()
        except OSError:
            recorded = None

    head = current_head()
    if recorded and (head is None or recorded == head):
        # HEAD が変わっていなければレビュー済みのまま通過(センチネルは保持)。
        # git が使えない環境ではハッシュ照合を諦めてセンチネルの存在のみ見る。
        sys.exit(0)

    if recorded:
        # 古い HEAD のセンチネルは無効なので破棄してから再レビューを要求する
        try:
            os.remove(SENTINEL)
        except OSError:
            pass
        detail = (
            "[codex_gate] センチネルの HEAD が現在と一致しません"
            "(レビュー後にコミットが進んでいます)。\n"
        )
    else:
        detail = "[codex_gate] Codex クロスレビューがまだ実行されていません。\n"
    print(
        detail + "先に cross-review スキルを実行してください。\n"
        "  方法: 「クロスレビューして」または「@cross-review を実行して」\n"
        "  スキップしたい場合は CLAUDE_CROSS_REVIEW を 0 に変更してください。",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
