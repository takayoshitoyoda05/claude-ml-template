#!/usr/bin/env python3
"""Stop: CLAUDE_ENFORCE_EVAL=1 のときだけ評価コマンドを実行し、
失敗したら exit 2 で Claude に続行を促す。

評価コマンドは環境変数 CLAUDE_EVAL_CMD で指定する。

効率化: 前回PASS時のリポジトリ状態(HEAD + 作業ツリーの状態)を
.claude/checkpoints/last_eval_pass.txt に記録し、状態が変わっていなければ
評価コマンドの再実行をスキップする(Stopのたびに重いテストが二重に
走るのを防ぐ)。状態ハッシュは _common.repo_state_signature を
spec_gate.py と共用する。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from _common import repo_state_signature

MARKER = Path(".claude/checkpoints/last_eval_pass.txt")


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # 無限ループ防止: すでに stop hook 由来なら通す
    if data.get("stop_hook_active"):
        sys.exit(0)

    # 評価強制フラグが立っていなければ何もしない
    if os.environ.get("CLAUDE_ENFORCE_EVAL", "") != "1":
        sys.exit(0)

    eval_cmd = os.environ.get("CLAUDE_EVAL_CMD", "").strip()
    if not eval_cmd:
        sys.exit(0)

    sig = repo_state_signature(eval_cmd)
    if sig and MARKER.exists():
        try:
            if MARKER.read_text(encoding="utf-8").strip() == sig:
                sys.exit(0)  # 前回PASSから状態が変わっていない
        except Exception:
            pass

    try:
        result = subprocess.run(
            eval_cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600
        )
    except subprocess.TimeoutExpired:
        # 時間切れは環境の不調ではなく「評価が完了していない」状態。ここで通すと
        # 「評価が通った」と「評価が終わらなかった」を区別できなくなるのでブロックする
        print(
            "[enforce_eval] 評価コマンドが制限時間(600秒)内に終わりませんでした。\n"
            "評価が完了していないため完了にできません。コマンドの見直しか、"
            "対象を絞った評価を検討してください。",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:
        # fork 失敗・メモリ不足など、ユーザーが手を出せない環境側の問題。
        # ここで止めると作業不能になるので通すが、黙って通さず必ず知らせる
        # (コマンドの綴り間違いは shell=True では例外にならず returncode 127 で
        #  返るため、下の returncode 検査でブロックされる)
        print(
            f"[enforce_eval] 警告: 評価コマンドを実行できませんでした({e})。\n"
            f"環境側の問題とみなして完了を許可しますが、評価は行われていません。",
            file=sys.stderr,
        )
        sys.exit(0)

    if result.returncode != 0:
        tail = (result.stdout + result.stderr)[-1500:]
        print(
            f"[enforce_eval] 評価が失敗しています。修正してから完了してください。\n"
            f"--- 評価出力(末尾) ---\n{tail}",
            file=sys.stderr,
        )
        sys.exit(2)

    if sig:
        try:
            MARKER.parent.mkdir(parents=True, exist_ok=True)
            MARKER.write_text(sig, encoding="utf-8")
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
