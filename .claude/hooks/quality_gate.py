#!/usr/bin/env python3
"""Stop フック: CLAUDE_QUALITY_GATE=1 のとき、作業スコープの Python コードに
機械的品質チェック(複雑度・lint・型)を実行し、閾値超過ならブロックする。

チェック内容:
1. ruff check  — lint 違反ゼロ
2. radon cc    — 循環的複雑度 C 以上(11+)の関数ゼロ
3. mypy        — 型エラーゼロ(mypy がインストールされている場合のみ)

ツールが見つからない場合、そのチェックはスキップする(uv 環境に無ければ強制しない)。
欠落判定は uv の実際のエラー文言(Failed to spawn / No module named 等)で行う。

効率化: 前回PASS時のリポジトリ状態を .claude/checkpoints/last_quality_pass.txt に
記録し、状態が変わっていなければ再実行をスキップする(enforce_eval.py と同じ
_common.repo_state_signature を使う。Stopのたびに全スコープの静的解析が
二重に走るのを防ぐ)。
"""

import os
import subprocess
import sys
from pathlib import Path

from _common import repo_state_signature

MARKER = Path(".claude/checkpoints/last_quality_pass.txt")

# uv / シェルがツール欠落時に出す文言(小文字比較)。これらを含む失敗は
# 「ツール未導入」としてスキップし、品質違反として扱わない
TOOL_MISSING_PATTERNS = (
    "failed to spawn",
    "no module named",
    "command not found",
    "executable not found",
)


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """コマンドを実行し (returncode, stdout, stderr) を返す。実行自体の失敗は (-1, ...)。

    stdout と stderr を分けて返すのは、radon の判定(レポートは stdout に出る)に
    uv の進捗メッセージ等の stderr ノイズが混入して誤ブロックするのを防ぐため。
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", ""
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def tool_missing(out: str) -> bool:
    low = out.lower()
    return any(p in low for p in TOOL_MISSING_PATTERNS)


def main():
    if os.environ.get("CLAUDE_QUALITY_GATE", "") != "1":
        sys.exit(0)

    scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip() or "."

    sig = repo_state_signature(f"quality_gate {scope}")
    if sig and MARKER.exists():
        try:
            if MARKER.read_text(encoding="utf-8").strip() == sig:
                sys.exit(0)  # 前回PASSから状態が変わっていない
        except Exception:
            pass

    failures: list[str] = []

    # 1. ruff check
    code, out, err = run(["uv", "run", "ruff", "check", scope])
    combined = (out + "\n" + err).strip()
    if code > 0 and not tool_missing(combined):
        failures.append(f"[ruff check] lint違反があります:\n{combined[:2000]}")

    # 2. radon cc(複雑度 C 以上の関数を検出。-n C は C 以上のみ表示。
    #    radon 未導入なら uv が非ゼロ終了するので code == 0 の条件で自然にスキップ。
    #    判定は stdout のみ(uv が stderr に出す進捗等で誤発火しないため)
    code, out, err = run(["uv", "run", "radon", "cc", scope, "-n", "C", "-s"])
    if code == 0 and out and not tool_missing(out):
        failures.append(
            f"[radon cc] 循環的複雑度が C(11)以上の関数があります。\n"
            f"分割・早期リターン・条件の切り出しで複雑度を下げてください:\n{out[:2000]}"
        )

    # 3. mypy(インストールされている場合のみ)
    code, out, err = run(["uv", "run", "mypy", scope, "--no-error-summary"])
    combined = (out + "\n" + err).strip()
    if code > 0 and combined and not tool_missing(combined):
        failures.append(f"[mypy] 型エラーがあります:\n{combined[:2000]}")

    if failures:
        print(
            "[quality_gate] 機械的品質チェックに失敗しました。\n\n"
            + "\n\n".join(failures)
            + "\n\n修正してから完了してください。"
            "スキップしたい場合は CLAUDE_QUALITY_GATE を 0 に変更してください。",
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
