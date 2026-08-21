#!/usr/bin/env python3
"""git 履歴全体を辞書パターンとサイズ閾値でスキャンする(手動実行・R-022)。

過去にコミットされ、その後削除されたファイルであっても履歴に残り続ける。
`data_patterns.json` に一致する内容を追加したコミットと、サイズ閾値を
超える大きなオブジェクトを列挙する。BFG / git-filter-repo による除去手順は
README に記載する(このスクリプトは検知のみで除去は行わない)。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data_patterns import load_patterns, scan_lines  # noqa: E402

_PATTERNS_RELATIVE_PATH = Path(".claude") / "checkpoints" / "data_patterns.json"
# 既定 5MB(precommit_data_check.py と同じ閾値。設計書 6章)。
_SIZE_THRESHOLD_BYTES = 5 * 1024 * 1024


def _all_commit_shas() -> list[str]:
    """全ブランチ・全参照の到達可能なコミットSHAを列挙する。"""
    result = subprocess.run(
        ["git", "rev-list", "--all"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _scan_commit_patch(sha: str, patterns: list[re.Pattern[str]]) -> list[str]:
    """1コミットの追加行(パッチの `+` 行)を辞書パターンでスキャンする。"""
    result = subprocess.run(
        ["git", "show", "--no-color", "--pretty=format:", sha],
        capture_output=True,
    )
    try:
        text = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return []

    added_lines = [
        line[1:]
        for line in text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    hits = scan_lines(added_lines, patterns)
    return [f"{sha}: {hit.line_number}: {hit.line}" for hit in hits]


def _large_objects() -> list[str]:
    """サイズ閾値を超える履歴中のオブジェクトを列挙する(中身は読まない)。"""
    rev_list = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        capture_output=True,
        text=True,
        check=True,
    )
    batch_input = "\n".join(
        line.split(" ", 1)[0] for line in rev_list.stdout.splitlines() if line
    )
    batch = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
        input=batch_input,
        capture_output=True,
        text=True,
    )
    reports = []
    for line in batch.stdout.splitlines():
        parts = line.split(" ")
        if len(parts) != 3:
            continue
        oid, otype, size_str = parts
        if otype != "blob":
            continue
        try:
            size = int(size_str)
        except ValueError:
            continue
        if size > _SIZE_THRESHOLD_BYTES:
            reports.append(f"{oid}: サイズ超過のオブジェクト({size} bytes)")
    return reports


def main() -> int:
    """git 履歴全体を辞書ヒット・サイズ超過オブジェクトについてスキャンする。

    Returns:
        検知が無ければ 0。1件でもあれば該当コミット/オブジェクトを
        標準出力に列挙して 1。
    """
    try:
        shas = _all_commit_shas()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"git の実行に失敗した: {exc}", file=sys.stderr)
        return 1

    patterns = load_patterns(Path.cwd() / _PATTERNS_RELATIVE_PATH)

    reports = []
    if patterns:
        for sha in shas:
            reports.extend(_scan_commit_patch(sha, patterns))

    try:
        reports.extend(_large_objects())
    except (OSError, subprocess.CalledProcessError):
        pass

    if reports:
        for report in reports:
            print(report)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
