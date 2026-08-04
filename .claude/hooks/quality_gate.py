#!/usr/bin/env python3
"""Stop フック: CLAUDE_QUALITY_GATE=1 のとき、作業スコープの Python コードに
機械的品質チェック(複雑度・lint・型)を実行し、閾値超過ならブロックする。

チェック内容:
1. ruff check  — lint 違反ゼロ
2. radon cc    — 循環的複雑度 C 以上(11+)の関数ゼロ
3. mypy        — 型エラーゼロ(mypy がインストールされている場合のみ)
4. diff-cover  — 変更行カバレッジが閾値以上(CLAUDE_DIFF_COVERAGE=1 のときのみ)

ツールが見つからない場合、そのチェックはスキップする(uv 環境に無ければ強制しない)。
欠落判定は uv の実際のエラー文言(Failed to spawn / No module named 等)を
**stderr のみ**から探して行う。stdout を混ぜると、ruff が診断に添えるソース
スニペット経由で検査対象のコード自身が判定を左右できてしまう
(例: コードに "command not found" と書くだけで lint 違反が全件スキップされる)。

効率化: 前回PASS時のリポジトリ状態を .claude/checkpoints/last_quality_pass.txt に
記録し、状態が変わっていなければ再実行をスキップする(enforce_eval.py と同じ
_common.repo_state_signature を使う。Stopのたびに全スコープの静的解析が
二重に走るのを防ぐ)。
"""

import os
import re
import subprocess
import sys
import tempfile
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
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", ""
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def tool_missing(stderr: str) -> bool:
    """ツール未導入を示すエラーかどうかを stderr だけから判定する。

    stdout を渡してはならない。lint/型チェックの出力には検査対象のソースが
    含まれるため、コード側の文字列でゲートを黙らせられてしまう。
    """
    low = stderr.lower()
    return any(p in low for p in TOOL_MISSING_PATTERNS)


def _diff_coverage_min() -> int:
    """CLAUDE_DIFF_COVERAGE_MIN を1〜100の整数として読む。読めなければ既定80。

    行末を固定した正規表現で読む(`1e3` から `1` だけを拾う誤読を防ぐため。
    python-style.md の規約)。範囲外(0 や 101 以上)も既定にフォールバックする
    (読めない値で緩めない fail-safe側の判断)。
    """
    raw = os.environ.get("CLAUDE_DIFF_COVERAGE_MIN", "").strip()
    if not re.fullmatch(r"[0-9]+", raw):
        return 80
    value = int(raw)
    if not (1 <= value <= 100):
        return 80
    return value


def _check_diff_coverage(scope: str) -> list[str]:
    """変更行カバレッジが閾値未満なら違反メッセージを返す(opt-in)。

    main に直接書くと radon の複雑度 C 閾値を自分で踏むため、plan_gate の
    _validate_goal_ranges と同じ理由でヘルパーに分離する。
    """
    if os.environ.get("CLAUDE_DIFF_COVERAGE", "") != "1":
        return []

    # main ブランチが解決できない環境で diff-cover を「違反」と誤判定しないよう、
    # 比較先ブランチの有無を先に確認してからスキップする
    code, _, _ = run(["git", "rev-parse", "--verify", "main"], timeout=5)
    if code != 0:
        return []

    xml_fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(xml_fd)
    try:
        code, out, err = run(
            [
                "uv",
                "run",
                "pytest",
                scope,
                f"--cov={scope}",
                f"--cov-report=xml:{xml_path}",
                "-q",
            ],
            timeout=600,  # 既定120秒ではカバレッジ付き実行が高確率でタイムアウトする
        )
        # run() 自体が失敗(ツール不在)/タイムアウトのいずれもスキップ扱い
        # (誤ブロック防止。テスト自体の失敗はここではブロックしない —
        # enforce_eval / evaluator の責務。二重ブロックは差し戻しの原因を曖昧にする)
        if code == -1 or tool_missing(err):
            return []

        threshold = _diff_coverage_min()
        code, out, err = run(
            [
                "uv",
                "run",
                "diff-cover",
                xml_path,
                "--compare-branch=main",
                f"--fail-under={threshold}",
            ]
        )
        if tool_missing(err):
            return []
        if code != 0:
            combined = (out + "\n" + err).strip()
            return [
                f"[diff-cover] 変更行カバレッジが{threshold}%未満です:\n{combined[:2000]}"
            ]
        return []
    finally:
        try:
            os.remove(xml_path)
        except OSError:
            pass


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
    if code > 0 and not tool_missing(err):
        failures.append(f"[ruff check] lint違反があります:\n{combined[:2000]}")

    # 2. radon cc(複雑度 C 以上の関数を検出。-n C は C 以上のみ表示。
    #    radon 未導入なら uv が非ゼロ終了するので code == 0 の条件で自然にスキップ。
    #    判定は stdout のみ(uv が stderr に出す進捗等で誤発火しないため)
    code, out, err = run(["uv", "run", "radon", "cc", scope, "-n", "C", "-s"])
    if code == 0 and out and not tool_missing(err):
        failures.append(
            f"[radon cc] 循環的複雑度が C(11)以上の関数があります。\n"
            f"分割・早期リターン・条件の切り出しで複雑度を下げてください:\n{out[:2000]}"
        )

    # 3. mypy(インストールされている場合のみ)
    code, out, err = run(["uv", "run", "mypy", scope, "--no-error-summary"])
    combined = (out + "\n" + err).strip()
    if code > 0 and combined and not tool_missing(err):
        failures.append(f"[mypy] 型エラーがあります:\n{combined[:2000]}")

    # 4. diff-cover(変更行カバレッジ。CLAUDE_DIFF_COVERAGE=1 のときのみ)
    failures.extend(_check_diff_coverage(scope))

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
