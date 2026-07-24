#!/usr/bin/env python3
"""完全レポートの evidence/ を機械集約する。

モデルに「全部レポートに書いて」と頼むと必ず要約・省略が起きる。
「短縮ゼロ」を保証するため、証拠の収集はこのスクリプトが機械的に行う。

Usage: uv run python .claude/hooks/report_gen.py <report_dir_name> [--transcript <path>]
  例: uv run python .claude/hooks/report_gen.py 20260723-143022
  --transcript: セッション transcript ファイルのパス。指定時は
    evidence/transcript.jsonl にマスキング済みでコピーし、ファイル名から
    導出したセッションID(先頭8桁)で actions/agents ログも絞り込む。
生成先: docs/reports/<report_dir_name>/evidence/
"""

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mask import mask  # noqa: E402

MAX_COPY_BYTES = (
    10 * 1024 * 1024
)  # 1ファイルの上限(action_logのMAX_FIELDクリップ方針と整合)


def run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return proc.stdout + proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"[report_gen] command failed: {cmd}: {e}"


def _copy_masked(src: str, dst: str) -> None:
    """runs/ 配下のファイルをマスキングしてからコピーする(evidence/はコミット対象のため)。"""
    raw = Path(src).read_bytes()
    if len(raw) > MAX_COPY_BYTES:
        text = raw[:MAX_COPY_BYTES].decode("utf-8", errors="replace")
        text += f"\n...[clipped {len(raw) - MAX_COPY_BYTES} bytes]"
    else:
        text = raw.decode("utf-8", errors="replace")
    Path(dst).write_text(mask(text), encoding="utf-8")


def _make_symlink_ignorer(skipped: list[str]) -> Callable[[str, list[str]], set[str]]:
    """symlink をコピー対象から除外する copytree の ignore コールバックを返す。

    symlink はリポジトリ外(作業スコープ外)を指しうるため、そのまま
    追うと evidence/ にスコープ外の内容が混入する。名前は skipped に集める。
    """

    def _ignore(directory: str, names: list[str]) -> set[str]:
        found = {n for n in names if os.path.islink(os.path.join(directory, n))}
        skipped.extend(os.path.join(directory, n) for n in found)
        return found

    return _ignore


def _parse_args(argv: list[str]) -> tuple[str, str | None]:
    """コマンドライン引数から (report_dir_name, transcript_path) を取り出す。"""
    args = list(argv)
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

    return args[0], transcript_arg


def _write_git_evidence(evidence: Path, stats: dict[str, object]) -> None:
    """git 差分とコミット一覧(全文、省略なし。コミット済みリポジトリ内容の写しの
    ためマスク対象外 — パッチ形式の保全を優先)。"""
    (evidence / "diff.patch").write_text(
        run(["git", "diff", "main...HEAD"]), encoding="utf-8"
    )
    (evidence / "commits.txt").write_text(
        run(["git", "log", "main..HEAD", "--stat"]), encoding="utf-8"
    )
    diff_names = run(["git", "diff", "--name-only", "main...HEAD"]).strip()
    stats["changed_files"] = len(diff_names.splitlines()) if diff_names else 0


def _write_tool_logs(
    evidence: Path, stats: dict[str, object], transcript_arg: str | None
) -> None:
    """このセッション分のツール実行ログとエージェントログを集約する。

    --transcript のファイル名(<session-id>.jsonl)からセッションを絞り込む。
    無指定の場合は全件結合し、絞り込んでいないことを stats に明記する。
    """
    session8 = Path(transcript_arg).stem[:8] if transcript_arg else None
    stats["session_filter"] = session8 if session8 else "none(all files)"
    pattern = f"*-{session8}.jsonl" if session8 else "*.jsonl"
    for src_dir, name in [("logs/actions", "actions"), ("logs/agents", "agents")]:
        src = Path(src_dir)
        if not src.exists():
            continue
        merged = [f.read_text(encoding="utf-8") for f in sorted(src.glob(pattern))]
        if merged:
            (evidence / f"{name}.jsonl").write_text("".join(merged), encoding="utf-8")
            stats[f"{name}_entries"] = sum(m.count("\n") for m in merged)


def _write_runs_evidence(evidence: Path, stats: dict[str, object]) -> None:
    """tee で保存された runs/ をマスキングしてコピーする(symlink は除外)。"""
    runs_src = Path("logs/runs")
    if not (runs_src.exists() and any(runs_src.iterdir())):
        return
    skipped_symlinks: list[str] = []
    shutil.copytree(
        runs_src,
        evidence / "runs",
        dirs_exist_ok=True,
        copy_function=_copy_masked,
        ignore=_make_symlink_ignorer(skipped_symlinks),
    )
    stats["run_logs"] = len(list((evidence / "runs").glob("*")))
    if skipped_symlinks:
        stats["skipped_symlinks"] = skipped_symlinks


def _write_test_output(evidence: Path) -> None:
    """最終テスト出力(全文。素の `uv run` は pytest 未導入のため --with pytest で実行)。"""
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


def _write_transcript_evidence(
    evidence: Path, stats: dict[str, object], transcript_arg: str | None
) -> None:
    """公式セッション記録(transcript)をマスキングしてコピーする。"""
    if not transcript_arg:
        return
    transcript_path = Path(transcript_arg)
    if transcript_path.exists():
        text = transcript_path.read_text(encoding="utf-8", errors="replace")
        (evidence / "transcript.jsonl").write_text(mask(text), encoding="utf-8")
        stats["transcript_lines"] = len(text.splitlines())
    else:
        stats["transcript"] = f"not found: {transcript_arg}"


def main():
    report_dir_name, transcript_arg = _parse_args(sys.argv[1:])

    report_dir = Path("docs/reports") / report_dir_name
    evidence = report_dir / "evidence"
    # 機械生成物なので、前回実行の残留を防ぐため毎回作り直す
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True, exist_ok=True)

    stats: dict[str, object] = {"generated_at": datetime.now(timezone.utc).isoformat()}

    _write_git_evidence(evidence, stats)
    _write_tool_logs(evidence, stats, transcript_arg)
    _write_runs_evidence(evidence, stats)
    _write_test_output(evidence)
    _write_transcript_evidence(evidence, stats, transcript_arg)

    (evidence / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[report_gen] evidence generated: {evidence}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
