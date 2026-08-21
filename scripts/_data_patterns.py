"""データ識別子辞書(`data_patterns.json`)の読み込みと行スキャンの共有エンジン。

`scripts/data_dictionary.py` が生成し、`scripts/export_check.py` /
`scripts/data_scan.py` / `scripts/precommit_data_check.py` /
`scripts/history_scan.py` がここを import して使う(計画Step2〜6・ADR-0007)。
検知ロジックをここ1箇所に集約し、複数スクリプトへの写しによるドリフトを防ぐ。

スキーマ(``.claude/checkpoints/data_patterns.json``、Step1で固定):
``{"patterns": ["<正規表現文字列>", ...]}``

`.claude/hooks/_mask.py` は本モジュールを import せず、同じスキーマを
自己完結で読み込む(PC-26)。両ローダのパターン解釈が一致することは
テストで固定する。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import json
import re
import sys
from pathlib import Path

# ユーザー確定(2026-08-21): 辞書パターン数の上限。超過分は読み込み順で
# 切り捨てる(_mask.py は毎ツール実行で走るため、過剰な数の辞書パターンが
# ReDoS 相当の劣化を招くことを防ぐ)。
MAX_PATTERNS = 100


class Hit:
    """辞書パターンへの1件のヒット。

    Attributes:
        line_number: ヒットした行番号(1始まり)。
        line: ヒットした行の全文。
        pattern: マッチした `re.Pattern` の元の正規表現文字列。
    """

    def __init__(self, line_number: int, line: str, pattern: str) -> None:
        self.line_number = line_number
        self.line = line
        self.pattern = pattern


def load_patterns(path: str | Path) -> list[re.Pattern[str]]:
    """`data_patterns.json` を読み込みコンパイル済みパターンのリストを返す。

    壊れた JSON・想定外の型(配列でない `patterns`)・ファイル不在は
    いずれも例外を送出せず空リストを返す(fail-open)。個々のパターン文字列が
    `re.compile` に失敗した場合もそのパターンだけを無視する。上限
    `MAX_PATTERNS` を超える分は読み込み順で切り捨て、stderr に注記する。

    Args:
        path: `data_patterns.json` のパス。

    Returns:
        コンパイル済み `re.Pattern` のリスト。読み込み・解釈に失敗した場合は
        空リスト。
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
        payload = json.loads(raw)
        patterns = payload["patterns"]
        if not isinstance(patterns, list):
            return []
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return []

    if len(patterns) > MAX_PATTERNS:
        print(
            f"[_data_patterns] パターン数が上限({MAX_PATTERNS})を超えたため"
            f"{len(patterns) - MAX_PATTERNS}件を切り捨てた",
            file=sys.stderr,
        )
        patterns = patterns[:MAX_PATTERNS]

    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        try:
            compiled.append(re.compile(pattern))
        except re.error:
            continue
    return compiled


def scan_lines(lines: list[str], patterns: list[re.Pattern[str]]) -> list[Hit]:
    """行のリストを辞書パターンでスキャンし、ヒットを列挙する。

    Args:
        lines: スキャン対象の行(改行は含んでいても構わない)。
        patterns: `load_patterns` が返すコンパイル済みパターンのリスト。

    Returns:
        ヒットした `Hit` のリスト(出現順)。ヒット無しなら空リスト。
    """
    hits: list[Hit] = []
    for line_number, line in enumerate(lines, start=1):
        for pattern in patterns:
            if pattern.search(line):
                hits.append(Hit(line_number, line, pattern.pattern))
    return hits
