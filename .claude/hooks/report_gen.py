#!/usr/bin/env python3
"""完全レポートの evidence/ を機械集約する。

モデルに「全部レポートに書いて」と頼むと必ず要約・省略が起きる。
「短縮ゼロ」を保証するため、証拠の収集はこのスクリプトが機械的に行う。

Usage: uv run python .claude/hooks/report_gen.py <report_dir_name> [--transcript <path>] [--test-cmd <command>]
  例: uv run python .claude/hooks/report_gen.py 20260723-143022
  --transcript: セッション transcript ファイルのパス。指定時は
    evidence/transcript.jsonl にマスキング済みでコピーし、ファイル名から
    導出したセッションID(先頭8桁)で actions/agents ログも絞り込む。
  --test-cmd: 最終テストの実行コマンド(1引数の文字列。例:
    "uv run --with pytest python -m pytest tests/ projects/Deep_MIL/tests/ -v")。
    無指定時は既定の tests/ のみを実行する。作業スコープのテストが tests/ の
    外にある場合、既定のままでは evidence/test-output.txt に含まれないため、
    計画の検証コマンドをここで渡す。**単一コマンドのみ**: shlex.split して
    シェルを介さず実行するため、&& や | 等のシェル構文は使えない(任意の
    シェル実行の口を開けないための制約)。終了コードとタイムアウトの有無は
    stats.json に記録される。
生成先: docs/reports/<report_dir_name>/evidence/
"""

import json
import os
import shlex
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

USAGE = "Usage: report_gen.py <report_dir_name> [--transcript <path>] [--test-cmd <command>]"

# テストは既定 run() の120秒を超えうる(ML系の検証コマンドを想定)ため専用の上限
TEST_TIMEOUT_SECONDS = 1800


def run(cmd: list[str]) -> str:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        return proc.stdout + proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"[report_gen] command failed: {cmd}: {e}"


def _copy_masked(src: str, dst: str) -> None:
    """runs/ 配下のファイルをマスキングしてからコピーする。

    このテンプレートの .gitignore は docs/ ごと除外するため evidence/ は
    追跡されないが、配布先がこの除外を外せばコミット対象になりうる。
    いずれにせよローカルに平文を残さないためマスクは常に通す。
    """
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


def _usage_error() -> None:
    print(USAGE, file=sys.stderr)
    sys.exit(1)


def _pop_option(args: list[str], name: str) -> str | None:
    """args から `name <value>` の2要素を取り除き、値を返す(無ければ None)。"""
    if name not in args:
        return None
    idx = args.index(name)
    try:
        value = args[idx + 1]
    except IndexError:
        _usage_error()
    # 値の欠落で次のオプション名を値として飲み込む誤用を usage エラーにする
    if value.startswith("--"):
        _usage_error()
    del args[idx : idx + 2]
    return value


def _parse_args(argv: list[str]) -> tuple[str, str | None, str | None]:
    """コマンドライン引数から (report_dir_name, transcript_path, test_cmd) を取り出す。"""
    args = list(argv)
    transcript_arg = _pop_option(args, "--transcript")
    test_cmd_arg = _pop_option(args, "--test-cmd")

    # 位置引数はちょうど1つ。余分・未知の引数は黙って無視せずエラーにする
    # (誤記のまま誤ったディレクトリへ証跡を生成するのを防ぐ)
    if len(args) != 1 or args[0].startswith("--"):
        _usage_error()

    # report_dir_name は単一のディレクトリ名に限る。"../x" や絶対パスを許すと
    # 生成先が docs/reports/ の外に出て、既存ディレクトリを rmtree で消しうる
    name = args[0]
    if Path(name).name != name or name in {".", ".."}:
        _usage_error()

    return name, transcript_arg, test_cmd_arg


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
        # symlink はリポジトリ外(~/.ssh/id_rsa 等)を指しうる。runs/ と同じく
        # 追わない(logs/ 配下だけ素通りだと、そこが取り込みの抜け道になる)
        merged = [
            f.read_text(encoding="utf-8")
            for f in sorted(src.glob(pattern))
            if not f.is_symlink()
        ]
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


def _write_test_output(
    evidence: Path, stats: dict[str, object], test_cmd_arg: str | None
) -> None:
    """最終テスト出力(全文。素の `uv run` は pytest 未導入のため --with pytest で実行)。

    --test-cmd 指定時はそのコマンドを使う(作業スコープのテストが既定の tests/ の
    外にある場合、既定のままでは evidence から漏れるため)。シェルを介さないため
    シェル構文(&& 等)は不可。使ったコマンド・終了コード・タイムアウトの有無を
    stats に記録する(テスト失敗でも evidence 生成は続行する — 失敗の事実を
    そのまま証跡に残すのが目的で、合否判定は evaluator の責務のため)。
    """
    if test_cmd_arg:
        try:
            cmd = shlex.split(test_cmd_arg)
        except ValueError:
            # 閉じていない引用符など。壊れたコマンドで空の証跡を作らない
            _usage_error()
        # シェルを介さないため、シェル演算子は先頭コマンドの引数に化けて
        # 「検証したつもり」の証跡になる。黙って劣化させず明示的に拒否する
        if any(
            tok in {"&&", "||", "|", ";", "&", ">", ">>", "<", "2>&1"} for tok in cmd
        ):
            _usage_error()
    else:
        cmd = [
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
    # 引数境界を監査で再現できるよう配列のまま記録する(" ".join は引用符を失う)
    stats["test_cmd"] = cmd
    stats["test_timed_out"] = False
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT_SECONDS,
        )
        output = proc.stdout + proc.stderr
        stats["test_exit_code"] = proc.returncode
    except subprocess.TimeoutExpired as e:
        # 途中までの出力も証跡として残す(bytes で返ることがあるため復号する)
        partial = ""
        for stream in (e.stdout, e.stderr):
            if isinstance(stream, bytes):
                partial += stream.decode("utf-8", errors="replace")
            elif stream:
                partial += stream
        output = partial + f"\n[report_gen] test command timed out: {cmd}: {e}"
        stats["test_exit_code"] = None
        stats["test_timed_out"] = True
        stats["test_error"] = str(e)
    except (OSError, UnicodeError) as e:
        output = f"[report_gen] test command failed: {cmd}: {e}"
        stats["test_exit_code"] = None
        stats["test_error"] = str(e)
    (evidence / "test-output.txt").write_text(mask(output), encoding="utf-8")


def _write_transcript_evidence(
    evidence: Path, stats: dict[str, object], transcript_arg: str | None
) -> None:
    """公式セッション記録(transcript)をマスキングしてコピーする。"""
    if not transcript_arg:
        return
    transcript_path = Path(transcript_arg)
    # transcript は Claude Code が書く .jsonl 。拡張子を固定して、認証情報
    # ファイル等の任意のパスを evidence/ に複製できないようにする
    if transcript_path.suffix != ".jsonl":
        stats["transcript"] = f"refused (not a .jsonl file): {transcript_arg}"
        return
    if transcript_path.is_symlink():
        stats["transcript"] = f"refused (symlink): {transcript_arg}"
        return
    if transcript_path.exists():
        text = transcript_path.read_text(encoding="utf-8", errors="replace")
        (evidence / "transcript.jsonl").write_text(mask(text), encoding="utf-8")
        stats["transcript_lines"] = len(text.splitlines())
    else:
        stats["transcript"] = f"not found: {transcript_arg}"


def main():
    report_dir_name, transcript_arg, test_cmd_arg = _parse_args(sys.argv[1:])

    report_dir = Path("docs/reports") / report_dir_name
    evidence = report_dir / "evidence"
    # report_dir が docs/reports/ 外への symlink だと、下の rmtree が外部の
    # evidence/ を消しうる。解決後パスが配下に留まることを確認してから消す
    if report_dir.exists() and not report_dir.resolve().is_relative_to(
        Path("docs/reports").resolve()
    ):
        print(
            f"[report_gen] refuse: {report_dir} resolves outside docs/reports/",
            file=sys.stderr,
        )
        sys.exit(1)
    # 機械生成物なので、前回実行の残留を防ぐため毎回作り直す
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True, exist_ok=True)

    stats: dict[str, object] = {"generated_at": datetime.now(timezone.utc).isoformat()}

    _write_git_evidence(evidence, stats)
    _write_tool_logs(evidence, stats, transcript_arg)
    _write_runs_evidence(evidence, stats)
    _write_test_output(evidence, stats, test_cmd_arg)
    _write_transcript_evidence(evidence, stats, transcript_arg)

    (evidence / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[report_gen] evidence generated: {evidence}")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
