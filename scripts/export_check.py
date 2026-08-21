#!/usr/bin/env python3
"""`data/exports/` 配下をデータ識別子辞書でスキャンする(R-015)。

`data/exports/` は外部送信の正規経路(data_gate の遮断対象外)だが、
識別子辞書に一致する値をうっかり集計値と一緒に置いてしまうことを防ぐため、
export 前にこのスクリプトで検疫する。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data_patterns import load_patterns, scan_lines  # noqa: E402

_EXPORTS_RELATIVE_PATH = Path("data") / "exports"
_PATTERNS_RELATIVE_PATH = Path(".claude") / "checkpoints" / "data_patterns.json"


def main() -> int:
    """`data/exports/` 配下の全ファイルを辞書スキャンする。

    Returns:
        ヒットが1件も無ければ 0。1件でもあれば該当ファイル・行番号・
        行内容を標準出力に列挙して 1。`data/exports/` が存在しない場合は
        検査対象が無いため 0。
    """
    root = Path.cwd()
    exports_dir = root / _EXPORTS_RELATIVE_PATH
    if not exports_dir.is_dir():
        return 0

    patterns = load_patterns(root / _PATTERNS_RELATIVE_PATH)
    if not patterns:
        return 0

    found = False
    for path in sorted(exports_dir.rglob("*")):
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for hit in scan_lines(lines, patterns):
            found = True
            print(f"{path}:{hit.line_number}: {hit.line}")

    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
