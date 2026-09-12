#!/usr/bin/env python3
"""検証つき解除: Red で記録されたテストコマンドを記録済みディレクトリで再実行し、
exit 0(緑)のときのみセンチネルを削除する。

「通ったことにして解除」という自己申告の抜け道を機械的に塞ぐため、赤のままの
解除は不可(R-011)。記録された実行ディレクトリ(`recorded_cwd`)で再実行する
理由は、相対パスを含むテストコマンドが別ディレクトリからの解除実行で
偽陽性/偽陰性になるのを防ぐため(設計判断表: 記録時の実行ディレクトリ)。

センチネルのスキーマ検証は tdd_gate.py と同じ規則を standalone で持つ
(`_common` を import できない自己完結の要件のため3本それぞれに再実装する)。
検証に失敗した場合(欠落・型不正・`recorded_cwd` が相対パス等)は、
テストコマンドを実行せずに非0終了しセンチネルを保持する(fail-closed)。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINTS_DIR = REPO_ROOT / ".claude" / "checkpoints"
SENTINEL_PATH = CHECKPOINTS_DIR / "tdd_red.json"

TEST_TIMEOUT_SECONDS = 600

# tdd_gate.py と同じ正規化規則(standalone: _common は import できない自己完結の
# 要件のため3本それぞれに再実装する。tdd_unlock.py 自身はパス比較を行わないが、
# 将来の照合追加に備えて3本で規則を揃える)
_CASE_INSENSITIVE_FS = os.name == "nt"


def _path_for_match(path: str) -> str:
    return path.lower() if _CASE_INSENSITIVE_FS else path


def _validate_sentinel(state: object) -> list[str] | None:
    """tdd_gate.py と同じ必須5キー・型・非空の検証(不正なら None)。"""
    if not isinstance(state, dict):
        return None
    for key in ("test_command", "recorded_cwd", "recorded_at", "log_path"):
        value = state.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
    test_files = state.get("test_files")
    if not isinstance(test_files, list) or not test_files:
        return None
    if not all(
        isinstance(f, str) and f.strip() and os.path.isabs(f) for f in test_files
    ):
        return None
    if not os.path.isabs(state["recorded_cwd"]):
        return None
    return test_files


def main() -> None:
    if not SENTINEL_PATH.exists():
        print(
            "[tdd_unlock] センチネルが見つかりません。"
            "tdd_red.py で Red を記録してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        raw_bytes = SENTINEL_PATH.read_bytes()
        state = json.loads(raw_bytes.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raw_bytes = None
        state = None

    if _validate_sentinel(state) is None:
        print(
            "[tdd_unlock] センチネルの形式が不正です(照合不能)。"
            "テストコマンドを実行せずに中断します。センチネルは保持します。"
            "tdd_red.py で再記録してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = state["test_command"]
    cwd = state["recorded_cwd"]
    if not os.path.isdir(cwd):
        print(
            f"[tdd_unlock] 記録された実行ディレクトリが存在しません: {cwd}\n"
            "テストコマンドを実行せずに中断します。センチネルは保持します。"
            "tdd_red.py で再記録してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as e:
        print(
            f"[tdd_unlock] テストコマンドを実行できませんでした: {e}\n"
            "センチネルは保持します。",
            file=sys.stderr,
        )
        sys.exit(1)

    if result.returncode != 0:
        print(
            "[tdd_unlock] テストはまだ赤(失敗)です。センチネルを保持します。\n"
            f"--- stdout ---\n{result.stdout[-2000:]}\n"
            f"--- stderr ---\n{result.stderr[-2000:]}\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # TOCTOU 対策(rename 方式): 照合とunlinkの間に別プロセスの tdd_red.py 再記録が
    # 割り込む窓を塞ぐため、まずセンチネルを os.replace で一時名へ原子的に退避してから
    # 実行前バイト列と照合する。一致すれば退避ファイルを削除(解除成功)。不一致なら
    # 退避ファイルを元の位置へ書き戻す(実行中に別プロセスが再記録した内容を消さない)。
    # ただし書き戻し先に既に新センチネルが存在する場合(退避後にさらに再記録された
    # 場合)は書き戻さず退避ファイルを破棄し、新しい記録を優先する。
    unlocking_path = SENTINEL_PATH.with_name(SENTINEL_PATH.name + ".unlocking")
    try:
        os.replace(str(SENTINEL_PATH), str(unlocking_path))
    except OSError as e:
        print(
            f"[tdd_unlock] テストは緑でしたが、センチネルの退避に失敗しました: {e}\n"
            "センチネルは保持します。",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        current_bytes = unlocking_path.read_bytes()
    except OSError as e:
        print(
            f"[tdd_unlock] テストは緑でしたが、退避したセンチネルの再読込に失敗しました: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    if current_bytes != raw_bytes:
        if SENTINEL_PATH.exists():
            try:
                unlocking_path.unlink()
            except OSError:
                pass  # 退避ファイルの削除に失敗しても新センチネルの優先は成立している
            print(
                "[tdd_unlock] テスト実行中に Red が再記録されました"
                "(センチネルの内容が変化しています)。退避後にさらに新しい記録が"
                "現れたため、退避した旧センチネルは破棄し新しい記録を優先します。",
                file=sys.stderr,
            )
            sys.exit(1)
        try:
            os.replace(str(unlocking_path), str(SENTINEL_PATH))
        except OSError as e:
            print(
                f"[tdd_unlock] テスト実行中に Red が再記録されましたが、"
                f"センチネルの書き戻しに失敗しました: {e}\n"
                f"退避先に残っています: {unlocking_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            "[tdd_unlock] テスト実行中に Red が再記録されました"
            "(センチネルの内容が変化しています)。センチネルは保持します。"
            "実行中に別プロセスが tdd_red.py を実行した可能性があります。",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        unlocking_path.unlink()
    except OSError as e:
        print(
            f"[tdd_unlock] テストは緑でしたが、退避したセンチネルの削除に失敗しました: {e}\n"
            f"退避先に残っています: {unlocking_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[tdd_unlock] テストが緑になったのでセンチネルを解除しました。")
    sys.exit(0)


if __name__ == "__main__":
    main()
