#!/usr/bin/env python3
"""Stop: CLAUDE_ENFORCE_EVAL=1 のときだけ評価コマンドを実行し、
失敗したら exit 2 で Claude に続行を促す。

評価コマンドは環境変数 CLAUDE_EVAL_CMD で指定する。

効率化: 前回PASS時のリポジトリ状態(HEAD + 作業ツリーの状態)を
.claude/checkpoints/last_eval_pass.txt に記録し、状態が変わっていなければ
評価コマンドの再実行をスキップする(Stopのたびに重いテストが二重に
走るのを防ぐ)。
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

MARKER = Path(".claude/checkpoints/last_eval_pass.txt")


def repo_state_signature(eval_cmd):
    """評価対象の状態を表すハッシュ。gitが使えなければ None(キャッシュ無効)。"""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception:
        return None
    if not head:
        return None
    raw = f"{eval_cmd}\n{head}\n{status}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
            eval_cmd, shell=True, capture_output=True, text=True, timeout=600
        )
    except Exception as e:
        print(f"[enforce_eval] 評価コマンド実行エラー: {e}", file=sys.stderr)
        sys.exit(0)  # 実行自体が失敗したら通す(環境問題を疑う)

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
