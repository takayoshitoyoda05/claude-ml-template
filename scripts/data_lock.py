#!/usr/bin/env python3
"""`data/`(`data/exports/` を除く)の sha256・サイズを記録・照合する。

`--update` は `data/data.lock`(JSON)に現在の `data/` の内容を記録する。
`--check` は記録済みの `data/data.lock` と現在の `data/` を照合し、
不一致(改変・削除・新規追加)があれば列挙して非0で終了する(R-001〜R-003)。
どちらも正常完了時に `data.lock digest: <12桁>` を標準出力へ表示する。これは
`data/data.lock` ファイル内容の sha256 先頭12桁で、EXPERIMENT_LOG の
「使用データ」欄に転記する値の出所となる。
`data/exports/` は正規の外部提供経路であり内容が変わり続けるため、
lock の走査対象から除外する(除外し忘れると `--check` が恒常的に
不一致になり警告が無視されるようになる)。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

_LOCK_RELATIVE_PATH = Path("data") / "data.lock"
_DATA_DIR_NAME = "data"
_EXPORTS_DIR_NAME = "exports"


def _iter_data_files(data_dir: Path) -> list[Path]:
    """`data/` 配下の走査対象ファイルを列挙する(`exports/` を除く)。

    Args:
        data_dir: `data/` ディレクトリのパス。

    Returns:
        `exports/` 配下と lock ファイル自身を除く、`data/` 配下の全ファイルの
        パス(ソート済み)。
    """
    exports_dir = data_dir / _EXPORTS_DIR_NAME
    lock_path = data_dir / "data.lock"
    files = []
    for path in data_dir.rglob("*"):
        if not path.is_file():
            continue
        if path == lock_path:
            continue
        try:
            path.relative_to(exports_dir)
            continue
        except ValueError:
            pass
        files.append(path)
    return sorted(files)


def _sha256_of(path: Path) -> str:
    """ファイルの SHA-256 16進文字列を返す。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _print_lock_digest(lock_path: Path) -> None:
    """`data.lock` 全体の sha256 先頭12桁を `data.lock digest: <12桁>` 形式で表示する。

    EXPERIMENT_LOG.md.template / evaluator.md が記入を規約化している
    「data.lock のハッシュ先頭12桁」の算出手段がこれまで存在しなかったため、
    正常完了時にこの値を提示する。
    """
    print(f"data.lock digest: {_sha256_of(lock_path)[:12]}")


def _relative_key(data_dir: Path, path: Path) -> str:
    """lock のキーとして使う `data/` 相対パス(POSIX区切り)を返す。"""
    return path.relative_to(data_dir).as_posix()


def update(root: Path) -> int:
    """`data/` の現状を `data/data.lock` に記録する。

    Args:
        root: プロジェクトルート。

    Returns:
        常に 0。
    """
    data_dir = root / _DATA_DIR_NAME
    files = {}
    if data_dir.is_dir():
        for path in _iter_data_files(data_dir):
            key = _relative_key(data_dir, path)
            files[key] = {"sha256": _sha256_of(path), "size": path.stat().st_size}

    payload = {"algorithm": "sha256", "files": files}
    lock_path = root / _LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _print_lock_digest(lock_path)
    return 0


def check(root: Path) -> int:
    """`data/data.lock` と現在の `data/` を照合する。

    Args:
        root: プロジェクトルート。

    Returns:
        不一致(改変・削除・新規追加)が無ければ 0。不一致ファイルのパスを
        標準出力に列挙し、あれば 1。`data/data.lock` が読めない場合も 1。
    """
    lock_path = root / _LOCK_RELATIVE_PATH
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        recorded = payload["files"]
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        print(f"data/data.lock を読み込めない: {exc}", file=sys.stderr)
        return 1

    data_dir = root / _DATA_DIR_NAME
    current = {}
    if data_dir.is_dir():
        for path in _iter_data_files(data_dir):
            key = _relative_key(data_dir, path)
            current[key] = {"sha256": _sha256_of(path), "size": path.stat().st_size}

    mismatched = []
    for key in sorted(set(recorded) | set(current)):
        if recorded.get(key) != current.get(key):
            mismatched.append(key)

    if mismatched:
        for key in mismatched:
            print(key)
        return 1
    _print_lock_digest(lock_path)
    return 0


def main(argv: list[str] | None = None) -> int:
    """コマンドライン引数を解釈し `--update` / `--check` を実行する。

    Args:
        argv: コマンドライン引数(省略時は `sys.argv[1:]`)。

    Returns:
        `update` / `check` の終了コード。
    """
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--update", action="store_true", help="data.lock を更新する")
    group.add_argument("--check", action="store_true", help="data.lock と照合する")
    args = parser.parse_args(argv)

    root = Path.cwd()
    if args.update:
        return update(root)
    return check(root)


if __name__ == "__main__":
    sys.exit(main())
