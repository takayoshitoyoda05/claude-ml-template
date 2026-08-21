#!/usr/bin/env python3
"""`data/DATA_LOG.md` の識別子列から `data_patterns.json` を半自動生成する。

識別子列の各セル値(カンマ区切りで複数指定可)を `re.compile` し、成功すれば
そのまま正規表現パターンとして、`re.error` なら `re.escape` してリテラル語
として `.claude/checkpoints/data_patterns.json` に格納する(両対応・R-011)。
出力は `scripts/_data_patterns.py` が固定するスキーマ
(``{"patterns": [str, ...]}``)に従う。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data_patterns import MAX_PATTERNS  # noqa: E402

_DATALOG_RELATIVE_PATH = Path("data") / "DATA_LOG.md"
_OUTPUT_RELATIVE_PATH = Path(".claude") / "checkpoints" / "data_patterns.json"

# 表の行(パイプ区切り・7列)にマッチする。区切り行(|---|---|...|)は
# セル内容が `-` のみで構成されるため、識別子列を re.compile すると
# 「1文字以上の任意文字の繰り返し」として解釈でき誤って混入しうる。
# 区切り行は別途フィルタで除外する。
_TABLE_ROW_PATTERN = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR_ROW_PATTERN = re.compile(r"^[\s|:-]+$")


def _extract_identifier_cells(datalog_text: str) -> list[str]:
    """DATA_LOG.md 本文の表から識別子列(最終列)のセル値を抽出する。

    Args:
        datalog_text: `data/DATA_LOG.md` の全文。

    Returns:
        識別子列のセル値(トリム済み・空セルは除外)のリスト。ヘッダ行・
        区切り行(`|---|---|`)は含まない。
    """
    rows = []
    header_seen = False
    for line in datalog_text.splitlines():
        match = _TABLE_ROW_PATTERN.match(line)
        if not match:
            continue
        if _SEPARATOR_ROW_PATTERN.match(match.group(1)):
            continue
        cells = [cell.strip() for cell in match.group(1).split("|")]
        if not header_seen:
            # 最初のテーブル行はヘッダ(列名)なので値として扱わない
            header_seen = True
            continue
        rows.append(cells)

    cells_out = []
    for cells in rows:
        if not cells:
            continue
        last_cell = cells[-1].strip()
        if not last_cell:
            continue
        for identifier in last_cell.split(","):
            identifier = identifier.strip()
            if identifier:
                cells_out.append(identifier)
    return cells_out


def build_patterns(identifiers: list[str]) -> list[str]:
    """識別子文字列を辞書パターン(正規表現文字列)のリストに変換する。

    Args:
        identifiers: DATA_LOG.md の識別子列から抽出したセル値のリスト。

    Returns:
        有効な正規表現はそのまま、無効な正規表現は `re.escape` 済みの
        リテラル語として並べたリスト。`MAX_PATTERNS` を超える分は
        読み込み順で切り捨てる。
    """
    patterns = []
    for identifier in identifiers:
        try:
            re.compile(identifier)
            patterns.append(identifier)
        except re.error:
            patterns.append(re.escape(identifier))

    if len(patterns) > MAX_PATTERNS:
        print(
            f"[data_dictionary] パターン数が上限({MAX_PATTERNS})を超えたため"
            f"{len(patterns) - MAX_PATTERNS}件を切り捨てた",
            file=sys.stderr,
        )
        patterns = patterns[:MAX_PATTERNS]
    return patterns


def main() -> int:
    """`data/DATA_LOG.md` を読み `data_patterns.json` を生成する。

    Returns:
        常に 0。`data/DATA_LOG.md` が存在しない場合は空の `patterns` を
        持つ JSON を出力する(識別子列が空のデータセット行と同様に扱う)。
    """
    root = Path.cwd()
    datalog_path = root / _DATALOG_RELATIVE_PATH
    identifiers = []
    if datalog_path.is_file():
        text = datalog_path.read_text(encoding="utf-8")
        identifiers = _extract_identifier_cells(text)

    patterns = build_patterns(identifiers)

    output_path = root / _OUTPUT_RELATIVE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"patterns": patterns}, ensure_ascii=False), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
