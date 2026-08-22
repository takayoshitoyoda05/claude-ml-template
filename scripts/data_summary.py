#!/usr/bin/env python3
"""引数の data/ 配下ファイルの統計量だけを出す窓口(R-010, R-011)。

`CLAUDE_DATA_NO_READ` で Read/Bash の生読みを遮断しても、統計量だけを見たい
場面は残る。csv/tsv/json/jsonl を標準ライブラリのみで読み、行数・列数・
列名と型・欠損数・数値列の min/max/mean/std・sha256 先頭12桁を出力する。

**個票の値を出力する経路を一切持たない**: ユニーク値一覧・サンプル行・
例外メッセージへの行内容の埋め込みはいずれも禁止。読み込みに失敗した行は
ファイル名と行番号だけを報告する(値そのものは出さない)。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

_READ_EXCEPTIONS = (OSError, UnicodeError, ValueError, KeyError, csv.Error)

_NUMERIC_TYPES = ("int", "float")


def _infer_type(values: list[str | None]) -> str:
    """列の値(欠損は None)から型名(int/float/str)を推定する。

    Args:
        values: 列のセル値。欠損は None。

    Returns:
        全非欠損値が整数表現なら "int"、数値表現(小数含む)なら "float"、
        それ以外(非欠損値が1つも無い場合を含む)は "str"。
    """
    non_missing = [v for v in values if v is not None and v != ""]
    if not non_missing:
        return "str"
    is_int = True
    is_float = True
    for v in non_missing:
        try:
            int(v)
        except (ValueError, TypeError):
            is_int = False
        try:
            float(v)
        except (ValueError, TypeError):
            is_float = False
    if is_int:
        return "int"
    if is_float:
        return "float"
    return "str"


def _stats(values: list[str | None]) -> dict[str, float]:
    """数値列の min/max/mean/std を返す(欠損は除外)。

    Args:
        values: 列のセル値。欠損は None。

    Returns:
        `min` / `max` / `mean` / `std` を持つ辞書。非欠損値が無ければ全て 0.0。
    """
    nums = [float(v) for v in values if v is not None and v != ""]
    if not nums:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}
    mean = sum(nums) / len(nums)
    variance = sum((n - mean) ** 2 for n in nums) / len(nums)
    return {"min": min(nums), "max": max(nums), "mean": mean, "std": variance**0.5}


def _read_delimited(path: Path, delimiter: str) -> tuple[list[str], dict[str, list]]:
    """csv/tsv を読み、列名と列ごとの値(None=欠損)を返す。"""
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        columns = reader.fieldnames or []
        data: dict[str, list] = {col: [] for col in columns}
        for row in reader:
            for col in columns:
                cell = row.get(col)
                data[col].append(cell if cell not in (None, "") else None)
    return columns, data


def _read_json_records(path: Path) -> tuple[list[str], dict[str, list]]:
    """json(レコード配列)を読み、列名と列ごとの値(None=欠損)を返す。"""
    records = json.loads(path.read_text(encoding="utf-8"))
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)
    data: dict[str, list] = {col: [] for col in columns}
    for record in records:
        for col in columns:
            value = record.get(col)
            data[col].append(None if value is None else str(value))
    return columns, data


def _read_jsonl(path: Path) -> tuple[list[str], dict[str, list]]:
    """jsonl(1行1レコード)を読み、列名と列ごとの値(None=欠損)を返す。"""
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)
    data: dict[str, list] = {col: [] for col in columns}
    for record in records:
        for col in columns:
            value = record.get(col)
            data[col].append(None if value is None else str(value))
    return columns, data


def _load(path: Path) -> tuple[list[str], dict[str, list], int]:
    """拡張子に応じて読み込み、列名・列ごとの値・行数を返す。

    Args:
        path: 対象ファイル。

    Raises:
        ValueError: 拡張子が csv/tsv/json/jsonl のいずれでもない場合。
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        columns, data = _read_delimited(path, ",")
    elif suffix == ".tsv":
        columns, data = _read_delimited(path, "\t")
    elif suffix == ".json":
        columns, data = _read_json_records(path)
    elif suffix == ".jsonl":
        columns, data = _read_jsonl(path)
    else:
        raise ValueError(f"未対応の拡張子: {suffix}")
    n_rows = len(data[columns[0]]) if columns else 0
    return columns, data, n_rows


def summarize(path: Path) -> str:
    """ファイルを読み、統計量のみを含む表示用テキストを組み立てる。

    Args:
        path: data/ 配下の csv/tsv/json/jsonl ファイル。

    Returns:
        行数・列数・列ごとの型/欠損数/(数値列のみ)min/max/mean/std・
        ファイル全体の sha256 先頭12桁を含むテキスト。個票の値は含まない。
    """
    columns, data, n_rows = _load(path)
    lines = [
        f"行数: {n_rows}",
        f"列数: {len(columns)}",
        "",
    ]
    for col in columns:
        values = data[col]
        col_type = _infer_type(values)
        missing = sum(1 for v in values if v is None)
        line = f"- {col}: type={col_type}, 欠損数={missing}"
        if col_type in _NUMERIC_TYPES:
            stats = _stats(values)
            line += (
                f", min={stats['min']}, max={stats['max']}, "
                f"mean={stats['mean']}, std={stats['std']}"
            )
        lines.append(line)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    lines.append("")
    lines.append(f"sha256(先頭12桁): {digest}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """コマンドライン引数のファイルを要約して標準出力に表示する。

    Args:
        argv: `[対象ファイルパス]`(省略時は `sys.argv[1:]`)。

    Returns:
        正常終了は 0。引数不足・読み込み失敗・未対応拡張子は 1
        (エラーメッセージにファイル名と行番号のみを含み、行内容は含めない)。
    """
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("使い方: data_summary.py <ファイルパス>", file=sys.stderr)
        return 1

    path = Path(argv[0])
    try:
        print(summarize(path))
    except json.JSONDecodeError as exc:
        # 個票の値を漏らさないため、行番号だけを報告する(行内容は含めない)。
        print(f"{path}:{exc.lineno} の JSON 解析に失敗した", file=sys.stderr)
        return 1
    except _READ_EXCEPTIONS as exc:
        # 個票の値を漏らさないため、例外メッセージにファイル名だけを含める
        # (行内容そのものは埋め込まない)。
        print(f"{path} の読み込みに失敗した: {type(exc).__name__}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
