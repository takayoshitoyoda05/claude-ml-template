#!/usr/bin/env python3
"""stdin または引数ファイルをデータ識別子辞書でスキャンする(R-016)。

cross-review スキルが codex へ diff を送る前の検疫に使う。検知エンジンは
`export_check.py` と共有する(`_data_patterns.py`)。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data_patterns import load_patterns, scan_lines  # noqa: E402

_PATTERNS_RELATIVE_PATH = Path(".claude") / "checkpoints" / "data_patterns.json"


def main(argv: list[str] | None = None) -> int:
    """引数のファイル、または無指定なら stdin をスキャンする。

    Args:
        argv: スキャン対象ファイルのパス(省略時は stdin から読む)。

    Returns:
        ヒットが1件も無ければ 0。1件でもあれば該当行を標準出力に列挙して 1。
    """
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        try:
            lines = Path(argv[0]).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            print(f"読み込みに失敗した: {exc}", file=sys.stderr)
            return 0
    else:
        try:
            lines = sys.stdin.read().splitlines()
        except UnicodeError:
            return 0

    root = Path.cwd()
    patterns = load_patterns(root / _PATTERNS_RELATIVE_PATH)
    if not patterns:
        return 0

    found = False
    for hit in scan_lines(lines, patterns):
        found = True
        print(f"{hit.line_number}: {hit.line}")

    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
