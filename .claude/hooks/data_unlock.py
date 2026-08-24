#!/usr/bin/env python3
"""ユーザー `!` 実行専用: data/ 読み取り遮断を一時的に解除する。

`.claude/spec/data_unlock.txt`(CLAUDE_SPEC_DIR配下)に UTC epoch秒(整数1行)で
有効期限を書く。data_read_gate.py / data_gate.py がこの記録を読み、期限内なら
NO_READ実効時の読み取り遮断を一時的に解除する。

エージェントの Bash/PowerShell ツール経由の実行・複製は guard_bash.py が
ブロックする(spec_approve.py と同じ「ユーザー `!` 実行専用」の運用)。

`--minutes` は既定30分・上限240分。範囲外(241以上・0以下)はエラーで
非0終了し、既存の記録は書き換えない。
"""

import argparse
import sys
import time
from pathlib import Path

from _common import resolve_spec_dir

DEFAULT_MINUTES = 30
MAX_MINUTES = 240


def main() -> None:
    parser = argparse.ArgumentParser(
        description="data/ 読み取り遮断を一時解除する(ユーザー `!` 実行専用)"
    )
    parser.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)
    args = parser.parse_args()

    if args.minutes <= 0 or args.minutes > MAX_MINUTES:
        print(
            f"[data_unlock] ERROR: --minutes は 1〜{MAX_MINUTES} の範囲で指定して"
            f"ください(指定値: {args.minutes})。",
            file=sys.stderr,
        )
        sys.exit(1)

    spec_dir = Path(resolve_spec_dir())
    spec_dir.mkdir(parents=True, exist_ok=True)
    unlock_file = spec_dir / "data_unlock.txt"
    expiry = int(time.time()) + args.minutes * 60
    unlock_file.write_text(f"{expiry}\n", encoding="utf-8")
    print(f"[data_unlock] data/ の読み取り遮断を {args.minutes} 分間解除しました。")
    sys.exit(0)


if __name__ == "__main__":
    main()
