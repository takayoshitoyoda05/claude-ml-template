#!/usr/bin/env python3
"""ステージ差分のみを対象に、辞書ヒット/大型バイナリ/ipynb outputs を検知する。

`scripts/githooks/pre-commit`(薄いシェル)から呼ばれる(R-018/R-019)。
ステージされていない変更(working tree のみの変更)は検査対象外とし、
`git show :<path>` でインデックス上の内容のみを見る。サイズ閾値超の
バイナリは中身を読まず `git cat-file -s` のサイズのみで即判定する
(通常コミットで1秒以内という非機能要件のため)。
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data_patterns import load_patterns, scan_lines  # noqa: E402

_PATTERNS_RELATIVE_PATH = Path(".claude") / "checkpoints" / "data_patterns.json"
# 既定 5MB(設計書 6章)。超過した新規バイナリは中身を読まずに検知する。
_SIZE_THRESHOLD_BYTES = 5 * 1024 * 1024


def _staged_files() -> list[str]:
    """ステージされたファイルパス(削除を除く)を一覧する。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _staged_binary_paths() -> set[str]:
    """`git diff --numstat` でバイナリと判定されたステージ済みパスの集合を返す。"""
    result = subprocess.run(
        ["git", "diff", "--cached", "--numstat"],
        capture_output=True,
        text=True,
        check=True,
    )
    binary_paths = set()
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == "-" and parts[1] == "-":
            binary_paths.add(parts[2])
    return binary_paths


def _staged_size(path: str) -> int | None:
    """インデックス上のブロブサイズを返す(中身は読まない)。"""
    result = subprocess.run(
        ["git", "cat-file", "-s", f":{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def _staged_content(path: str) -> str | None:
    """インデックス上のテキスト内容を返す(デコードできなければ None)。"""
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _check_ipynb_outputs(path: str, text: str) -> str | None:
    """`.ipynb` の outputs が非空のセルがあれば理由文字列を返す。"""
    try:
        notebook = json.loads(text)
    except ValueError:
        return None
    for cell in notebook.get("cells", []):
        if cell.get("outputs"):
            return f"{path}: outputs が非空のセルがある(nbstripout等で消してから)"
    return None


def main() -> int:
    """ステージ差分を検査し、問題があれば理由を報告して非0で終了する。

    Returns:
        検知が無ければ 0。1件でもあれば理由を標準出力に列挙して 1。
    """
    try:
        staged = _staged_files()
        binary_paths = _staged_binary_paths()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"git の実行に失敗した: {exc}", file=sys.stderr)
        return 1

    patterns = load_patterns(Path.cwd() / _PATTERNS_RELATIVE_PATH)

    reasons = []
    for path in staged:
        if path in binary_paths:
            size = _staged_size(path)
            if size is not None and size > _SIZE_THRESHOLD_BYTES:
                reasons.append(
                    f"{path}: サイズ超過のバイナリ({size} bytes > "
                    f"{_SIZE_THRESHOLD_BYTES} bytes)"
                )
            continue

        text = _staged_content(path)
        if text is None:
            continue

        if path.endswith(".ipynb"):
            reason = _check_ipynb_outputs(path, text)
            if reason:
                reasons.append(reason)
            continue

        if patterns:
            for hit in scan_lines(text.splitlines(), patterns):
                reasons.append(f"{path}:{hit.line_number}: {hit.line}")

    if reasons:
        for reason in reasons:
            print(reason)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
