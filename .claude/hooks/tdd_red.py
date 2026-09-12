#!/usr/bin/env python3
"""Red 記録: 指定テストコマンドを実行し、失敗(非0)を確認してセンチネルを書き込む。

`.claude/checkpoints/tdd_red.json` に記録する(必須キー: test_command /
test_files / recorded_cwd / recorded_at / log_path)。既に緑のコマンドや
`--files` 未指定ではセンチネルを作らず非0終了する(R-003・R-004)。

センチネル・失敗ログ・blocks ログのパスは、このスクリプト自身の配置から
求めたリポジトリルート基準で解決する(`Path(__file__).resolve().parents[2]`)。
起動ディレクトリ(サブディレクトリからの起動を含む)によらず同一のセンチネルを
参照するため(設計判断表: センチネル・ログのパス解決)。

`--rearm` はセンチネルを削除して Red やり直しに入る(rearm イベントを
`.claude/checkpoints/tdd_gate_blocks.log` に記録する。正規のテスト修正経路)。

CLAUDE_TDD_GATE=0(既定)の間は tdd_gate.py 自体が常に素通りするため、本
スクリプトの記録はゲートの有効化(CLAUDE_TDD_GATE=1)を伴わない限り実害はない。
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINTS_DIR = REPO_ROOT / ".claude" / "checkpoints"
SENTINEL_PATH = CHECKPOINTS_DIR / "tdd_red.json"
BLOCKS_LOG_PATH = CHECKPOINTS_DIR / "tdd_gate_blocks.log"
FAILURE_LOG_PATH = CHECKPOINTS_DIR / "tdd_red_last.log"

TEST_TIMEOUT_SECONDS = 600

# tdd_gate.py と同じ正規化規則(standalone: _common は import できない自己完結の
# 要件のため3本それぞれに再実装する。tdd_red.py 自身はパス比較を行わないが、
# 将来の照合追加に備えて3本で規則を揃える)
_CASE_INSENSITIVE_FS = os.name == "nt"


def _path_for_match(path: str) -> str:
    return path.lower() if _CASE_INSENSITIVE_FS else path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_blocks_log(event: str, target: str, reason: str) -> None:
    try:
        CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(BLOCKS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{_utcnow_iso()} {event} {target} {reason}\n")
    except OSError:
        pass  # ログできなくても本処理は継続する(記録漏れのみの影響)


def _rearm() -> int:
    if not SENTINEL_PATH.exists():
        print("[tdd_red] センチネルが存在しないため --rearm できません。", file=sys.stderr)
        return 1
    try:
        SENTINEL_PATH.unlink()
    except OSError as e:
        print(f"[tdd_red] センチネルの削除に失敗しました: {e}", file=sys.stderr)
        return 1
    _append_blocks_log("rearm", str(SENTINEL_PATH), "Red やり直しのためセンチネルを削除")
    print("[tdd_red] センチネルを削除しました。テストを修正して Red からやり直してください。")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cmd", help="失敗を確認するテストコマンド")
    parser.add_argument("--files", nargs="+", help="記録するテストファイル(1件以上)")
    parser.add_argument(
        "--rearm", action="store_true", help="センチネルを削除して Red やり直しに入る"
    )
    args = parser.parse_args()

    if args.rearm:
        sys.exit(_rearm())

    if not args.cmd or not args.files:
        print("[tdd_red] --cmd と --files(1件以上)の指定が必要です。", file=sys.stderr)
        sys.exit(1)

    cwd = os.getcwd()
    try:
        result = subprocess.run(
            args.cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as e:
        print(f"[tdd_red] テストコマンドを実行できませんでした: {e}", file=sys.stderr)
        sys.exit(1)

    if result.returncode == 0:
        print(
            "[tdd_red] テストコマンドは既に緑です。Red を記録できません"
            "(先に失敗する状態にしてから実行してください)。",
            file=sys.stderr,
        )
        sys.exit(1)

    recorded_cwd = os.path.realpath(cwd)
    resolved_files = [os.path.realpath(os.path.join(cwd, f)) for f in args.files]
    recorded_at = _utcnow_iso()

    try:
        CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        FAILURE_LOG_PATH.write_text(
            f"$ {args.cmd}\n(cwd={recorded_cwd})\n\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n",
            encoding="utf-8",
        )
        sentinel = {
            "test_command": args.cmd,
            "test_files": resolved_files,
            "recorded_cwd": recorded_cwd,
            "recorded_at": recorded_at,
            "log_path": str(FAILURE_LOG_PATH),
        }
        SENTINEL_PATH.write_text(
            json.dumps(sentinel, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError as e:
        print(f"[tdd_red] センチネル/失敗ログの書き込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"[tdd_red] Red を記録しました({len(resolved_files)} 件のテストファイル)。"
        f"失敗ログ: {FAILURE_LOG_PATH}"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
