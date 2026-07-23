#!/usr/bin/env python3
"""完全レポートの evidence/ を機械集約する。

モデルに「全部レポートに書いて」と頼むと必ず要約・省略が起きる。
「短縮ゼロ」を保証するため、証拠の収集はこのスクリプトが機械的に行う。

Usage: uv run python .claude/hooks/report_gen.py <report_dir_name> [--transcript <path>]
  例: uv run python .claude/hooks/report_gen.py 20260723-143022
  --transcript: セッション transcript ファイルのパス。指定時は
    evidence/transcript.jsonl にマスキング済みでコピーする。
生成先: docs/reports/<report_dir_name>/evidence/
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mask import mask  # noqa: E402


def run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return proc.stdout + proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"[report_gen] command failed: {cmd}: {e}"


def _copy_masked(src: str, dst: str) -> None:
    """runs/ 配下のファイルをマスキングしてからコピーする(evidence/はコミット対象のため)。"""
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    Path(dst).write_text(mask(text), encoding="utf-8")


def main():
    args = sys.argv[1:]
    transcript_arg = None
    if "--transcript" in args:
        idx = args.index("--transcript")
        try:
            transcript_arg = args[idx + 1]
        except IndexError:
            print(
                "Usage: report_gen.py <report_dir_name> [--transcript <path>]",
                file=sys.stderr,
            )
            sys.exit(1)
        del args[idx : idx + 2]

    if len(args) < 1:
        print(
            "Usage: report_gen.py <report_dir_name> [--transcript <path>]",
            file=sys.stderr,
        )
        sys.exit(1)

    report_dir = Path("docs/reports") / args[0]
    evidence = report_dir / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)

    stats: dict[str, object] = {"generated_at": datetime.now(timezone.utc).isoformat()}

    # 1. git 差分とコミット一覧(全文、省略なし。コミット済みリポジトリ内容の写しの
    #    ためマスク対象外 — パッチ形式の保全を優先)
    (evidence / "diff.patch").write_text(
        run(["git", "diff", "main...HEAD"]), encoding="utf-8"
    )
    (evidence / "commits.txt").write_text(
        run(["git", "log", "main..HEAD", "--stat"]), encoding="utf-8"
    )
    stats["changed_files"] = (
        run(["git", "diff", "--name-only", "main...HEAD"]).strip().count("\n") + 1
    )

    # 2. ツール実行ログとエージェントログ(当日分をコピー。書き込み時に既にマスク済み)
    for src_dir, name in [("logs/actions", "actions"), ("logs/agents", "agents")]:
        src = Path(src_dir)
        if src.exists():
            merged: list[str] = []
            for f in sorted(src.glob("*.jsonl")):
                merged.append(f.read_text(encoding="utf-8"))
            if merged:
                (evidence / f"{name}.jsonl").write_text(
                    "".join(merged), encoding="utf-8"
                )
                stats[f"{name}_entries"] = sum(m.count("\n") for m in merged)

    # 3. プログラム実行ログ(tee で保存された runs/。リポジトリ外由来テキストのため
    #    マスクを適用してからコピーする)
    runs_src = Path("logs/runs")
    if runs_src.exists() and any(runs_src.iterdir()):
        shutil.copytree(
            runs_src, evidence / "runs", dirs_exist_ok=True, copy_function=_copy_masked
        )
        stats["run_logs"] = len(list((evidence / "runs").glob("*")))

    # 4. 最終テスト出力(全文。素の `uv run` は pytest 未導入のため --with pytest で実行)
    (evidence / "test-output.txt").write_text(
        mask(
            run(
                [
                    "uv",
                    "run",
                    "--with",
                    "pytest",
                    "python",
                    "-m",
                    "pytest",
                    "tests/",
                    "-v",
                ]
            )
        ),
        encoding="utf-8",
    )

    # 5. transcript(公式セッション記録。リポジトリ外由来テキストのためマスクを適用)
    if transcript_arg:
        transcript_path = Path(transcript_arg)
        if transcript_path.exists():
            text = transcript_path.read_text(encoding="utf-8", errors="replace")
            (evidence / "transcript.jsonl").write_text(mask(text), encoding="utf-8")
            stats["transcript_lines"] = text.count("\n") + 1
        else:
            stats["transcript"] = f"not found: {transcript_arg}"

    # 6. 統計サマリ(report.md 執筆時の参照用)
    (evidence / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[report_gen] evidence generated: {evidence}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
