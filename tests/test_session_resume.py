"""セッション上限からの自動再開の受け入れテスト。

対象: `.claude/plans/20260805-session-resume.md` の PC-1〜PC-13・PC-15
(PC-14・PC-16・PC-17 は Step 8 で git/python コマンドとして機械照合するため、
このファイルには含めない。postconditions 節が PC-15 も本ファイルの担当と
明記しているため、Step 1 実装手順表の「PC-1〜PC-13」表記に PC-15 を加えて扱う)。

`tests/test_plan_gate.py` の書式(`subprocess.run([sys.executable, <絶対パス>], ...)`
での CLI 起動、`_SUBPROCESS_TIMEOUT` 定数、`_load_module` は `tests/test_quality_gate.py`
の書式)に倣う。

Step 7(ユーザーによる `.claude/hooks/record_session_state.py` /
`resume_session_state.py` への適用)より前は、対象フックが存在しないため
`subprocess.run` が `FileNotFoundError` で失敗し全 FAIL になるのが正しい
状態(RED)。
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
RECORD_PATH = HOOKS_DIR / "record_session_state.py"
RESUME_PATH = HOOKS_DIR / "resume_session_state.py"
PLAN_GATE_PATH = HOOKS_DIR / "plan_gate.py"
REINJECT_PATH = HOOKS_DIR / "reinject_after_compact.py"

_SUBPROCESS_TIMEOUT = 15

# ローカル/CI のグローバル git 設定(commit.gpgsign 等)や対話プロンプトが
# フィクスチャ構築に影響しないよう遮断する(tests/test_quality_gate.py と同じ方式)
_GIT_ENV = os.environ.copy()
_GIT_ENV.update(
    {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
)


def _init_repo(tmp_path: Path, branch: str) -> None:
    """`tmp_path` に `git init -b <branch>` し、1コミットだけ作る。

    record フックは `git log` / `git status` を呼ぶため、コミット0件の
    unborn branch ではなく実コミットが1件ある状態を作る。
    """
    for args in (
        ["git", "init", "-q", "-b", branch],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(
            args,
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env=_GIT_ENV,
            timeout=_SUBPROCESS_TIMEOUT,
        )
    (tmp_path / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _write_transcript(tmp_path: Path, lines: list[str]) -> Path:
    """JSONL 行(既に json.dumps 済みの文字列)を1ファイルへ書き出す。"""
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run_record(
    tmp_path: Path, stdin_text: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """record_session_state.py を CLI として subprocess 起動する。"""
    env = _GIT_ENV.copy()
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(RECORD_PATH)],
        cwd=str(tmp_path),
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _run_resume(
    tmp_path: Path, stdin_text: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """resume_session_state.py を CLI として subprocess 起動する。"""
    env = _GIT_ENV.copy()
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(RESUME_PATH)],
        cwd=str(tmp_path),
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _state_path(tmp_path: Path) -> Path:
    return tmp_path / ".claude" / "checkpoints" / "session_state.md"


def _load_module(path: Path, name: str) -> ModuleType:
    """指定パスの `.py` をモジュールとして直接読み込む(PC-13 の関数比較用)。

    `tests/test_quality_gate.py` の `_load_quality_gate` と同じ方式
    (先に対象ディレクトリを sys.path に加えてから exec_module する)。
    """
    hooks_dir = str(path.parent)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# PC-1: 正常な Stop JSON で状態ファイルが生成される
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    ["最後の実発話です", None],
    ids=["string", "text_single"],
)
def test_pc01_normal_stop_creates_state(tmp_path: Path, content) -> None:
    """PC-1: 正常な Stop JSON(transcript_path あり)を stdin。

    5パターン中「文字列 content」「text ブロック1件」を扱う(入力の形が
    複数ある箇所の表)。
    """
    branch = "pipeline/20260805-foo"
    _init_repo(tmp_path, branch)
    if content is None:
        message_content = [{"type": "text", "text": "最後の実発話です"}]
    else:
        message_content = content
    transcript = _write_transcript(
        tmp_path,
        [
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": message_content},
                }
            )
        ],
    )
    stdin = json.dumps({"hook_event_name": "Stop", "transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    state_path = _state_path(tmp_path)
    assert state_path.exists()
    text = state_path.read_text(encoding="utf-8")
    assert f"## Git ブランチ: {branch}" in text
    assert "## git status --short" in text
    assert re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert "最後の実発話です" in text


# ---------------------------------------------------------------------------
# PC-2: stdin が空 / 不正 JSON / 必須キー欠落
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stdin_text",
    ["", "not json {{{", "{}"],
    ids=["empty", "invalid-json", "missing-keys"],
)
def test_pc02_bad_stdin_fails_open(tmp_path: Path, stdin_text: str) -> None:
    """PC-2: stdin が空・不正JSON・必須キー欠落のいずれでも exit 0・無出力・トレースバックなし。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    result = _run_record(tmp_path, stdin_text)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# PC-3: transcript_path が存在しない / 読めない / 壊れた行が混在
# ---------------------------------------------------------------------------


def test_pc03a_missing_transcript_path(tmp_path: Path) -> None:
    """PC-3: transcript_path が存在しないパスなら会話セクションは「(取得不可)」。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    stdin = json.dumps({"transcript_path": str(tmp_path / "does-not-exist.jsonl")})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert "(取得不可)" in text


def test_pc03b_unreadable_bytes_transcript(tmp_path: Path) -> None:
    """PC-3: transcript が不正なバイト列でも exit 0・「(取得不可)」相当の記載。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_bytes(b"\xff\xfe\x00\x01 invalid bytes, not json \xff")
    stdin = json.dumps({"transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert "(取得不可)" in text


def test_pc03c_broken_lines_mixed_still_completes(tmp_path: Path) -> None:
    """PC-3: 壊れた行・空行が混在していても、解釈できた行だけで記録が完成する。

    5パターン中「壊れた行の混在」を扱う(入力の形が複数ある箇所の表)。
    """
    _init_repo(tmp_path, "pipeline/20260805-foo")
    transcript = _write_transcript(
        tmp_path,
        [
            "not json at all {{{",
            "",
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": "壊れた行の後の実発話"},
                }
            ),
            "{broken again",
        ],
    )
    stdin = json.dumps({"transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert "壊れた行の後の実発話" in text


# ---------------------------------------------------------------------------
# PC-4: 同一リポジトリで2回実行しても状態ファイルは1つだけ
# ---------------------------------------------------------------------------


def test_pc04_repeated_run_keeps_single_file(tmp_path: Path) -> None:
    """PC-4: 2回実行(間に1秒以上)しても session_state* は1ファイルのみ、記録時刻は変わる。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    stdin = json.dumps({"transcript_path": ""})

    result1 = _run_record(tmp_path, stdin)
    assert result1.returncode == 0
    content1 = _state_path(tmp_path).read_text(encoding="utf-8")

    time.sleep(1.1)

    result2 = _run_record(tmp_path, stdin)
    assert result2.returncode == 0
    content2 = _state_path(tmp_path).read_text(encoding="utf-8")

    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    state_files = sorted(p.name for p in checkpoints_dir.glob("session_state*"))
    assert state_files == ["session_state.md"]
    assert content1 != content2


# ---------------------------------------------------------------------------
# PC-5: 秘密情報らしき文字列がマスキングされる
# ---------------------------------------------------------------------------


def test_pc05a_secret_in_plain_string_is_masked(tmp_path: Path) -> None:
    """PC-5: sk- で始まる40文字級のキー様文字列は原文字列が残らず [MASKED] になる。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    secret = "sk-" + "a" * 40
    transcript = _write_transcript(
        tmp_path,
        [
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": f"APIキーは {secret} です"},
                }
            )
        ],
    )
    stdin = json.dumps({"transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert secret not in text
    assert "[MASKED]" in text


def test_pc05b_mixed_text_and_tool_use_only_text_masked(tmp_path: Path) -> None:
    """PC-5: text + tool_use が混在する content は text 部分のみ採用し、そこもマスキングする。

    5パターン中「text + tool_use の複数ブロック(入れ子)」を扱う。tool_use 側の
    値は採用自体されないため、そこに置いた別の秘密情報らしき文字列は一切出力に
    現れないことも併せて確認する。
    """
    _init_repo(tmp_path, "pipeline/20260805-foo")
    text_secret = "sk-" + "b" * 40
    tool_use_secret = "sk-" + "c" * 40
    transcript = _write_transcript(
        tmp_path,
        [
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"キーは {text_secret} です"},
                            {
                                "type": "tool_use",
                                "name": "Bash",
                                "input": {"command": f"echo {tool_use_secret}"},
                            },
                        ],
                    },
                }
            )
        ],
    )
    stdin = json.dumps({"transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert text_secret not in text
    assert tool_use_secret not in text
    assert "[MASKED]" in text


def test_pc05c_tool_result_only_falls_back_to_earlier_utterance(tmp_path: Path) -> None:
    """PC-5: tool_result のみの行は採用せず、その手前の実発話(マスキング済み)を採る。

    5パターン中「tool_result のみ」を扱う。
    """
    _init_repo(tmp_path, "pipeline/20260805-foo")
    secret = "sk-" + "d" * 40
    transcript = _write_transcript(
        tmp_path,
        [
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": f"これが最後の実発話です {secret}",
                    },
                }
            ),
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "toolu_1",
                                "content": "ツール出力",
                            }
                        ],
                    },
                }
            ),
        ],
    )
    stdin = json.dumps({"transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert secret not in text
    assert "[MASKED]" in text
    assert "これが最後の実発話です" in text


def test_pc05d_secret_straddling_truncation_boundary_is_masked(tmp_path: Path) -> None:
    """PC-5: sk- キーが会話の切り詰め境界(`_MAX_CONVERSATION_CHARS`)をまたいでも断片が平文で残らない。

    切り詰め→マスクの順序だと、境界をまたぐ秘密情報パターンは前半だけが
    切り出され正規表現にマッチしないため、その断片が平文のまま状態ファイルに
    残る(HIGH指摘)。マスク→切り詰めの順序であれば、切り詰め前に全文が
    `[MASKED]` に置換されるためこの断片は現れない。
    """
    _init_repo(tmp_path, "pipeline/20260805-foo")
    record = _load_module(RECORD_PATH, "record_session_state")
    max_chars = record._MAX_CONVERSATION_CHARS
    secret = "sk-" + "e" * 40
    # 境界の手前に secret の先頭20文字(`sk-` + 17文字)が来るよう padding を
    # 敷き詰める。境界後に残り23文字が続くため、切り詰め→マスクの順序では
    # 前半20文字がパターン({20,})に届かず素通りする
    padding = "x" * (max_chars - 20)
    content = padding + secret
    transcript = _write_transcript(
        tmp_path,
        [
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": content},
                }
            )
        ],
    )
    stdin = json.dumps({"transcript_path": str(transcript)})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    # sk- に続く先頭10文字以上(境界の手前に残る断片)が平文で現れないことを検査する
    leaked_fragment = secret[:13]
    assert leaked_fragment not in text
    assert "[MASKED]" in text


# ---------------------------------------------------------------------------
# PC-6: 対応する計画ファイルと実装手順表が記録される
# ---------------------------------------------------------------------------


def test_pc06_plan_path_and_table_recorded(tmp_path: Path) -> None:
    """PC-6: worktree ブランチの `-group-A` を除いた slug で計画を特定し、手順表を記録する。"""
    branch = "pipeline/20260805-foo-group-A"
    _init_repo(tmp_path, branch)
    plans_dir = tmp_path / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    plan_text = (
        "計画本文\n\n| # | 内容 |\n|---|---|\n| 1 | ステップ1 |\n| 2 | ステップ2 |\n"
    )
    (plans_dir / "20260805-foo.md").write_text(plan_text, encoding="utf-8")
    stdin = json.dumps({"transcript_path": ""})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert "20260805-foo.md" in text
    assert "| 1 | ステップ1 |" in text


# ---------------------------------------------------------------------------
# PC-7: transcript の全読みをしない(ソース検査 + 大容量ファイルでの速度)
# ---------------------------------------------------------------------------


def test_pc07a_source_contains_seek() -> None:
    """PC-7(a): ソースに `.seek(` が含まれる(末尾シーク設計の直接検査)。"""
    assert RECORD_PATH.exists(), "record_session_state.py が未適用(RED)"
    source = RECORD_PATH.read_text(encoding="utf-8")
    assert ".seek(" in source


def test_pc07b_large_transcript_is_fast(tmp_path: Path) -> None:
    """PC-7(b): 20MB のダミー transcript でも exit 0 かつ実行時間5秒未満(退行検知)。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    transcript = tmp_path / "transcript.jsonl"
    line = (
        json.dumps({"type": "user", "message": {"role": "user", "content": "x" * 500}})
        + "\n"
    )
    reps = (20 * 1024 * 1024) // len(line.encode("utf-8")) + 1
    with open(transcript, "w", encoding="utf-8") as f:
        for _ in range(reps):
            f.write(line)
    stdin = json.dumps({"transcript_path": str(transcript)})

    start = time.monotonic()
    result = _run_record(tmp_path, stdin)
    elapsed = time.monotonic() - start

    assert result.returncode == 0
    assert elapsed < 5.0


# ---------------------------------------------------------------------------
# PC-8/PC-9: 起動時注入(startup で注入、compact では何もしない)
# ---------------------------------------------------------------------------


def test_pc08_startup_injects_state_and_resume_instructions(tmp_path: Path) -> None:
    """PC-8: source=startup・同一ブランチ・現在mtimeなら状態本文+再開指示を出力。"""
    branch = "pipeline/20260805-foo"
    _init_repo(tmp_path, branch)
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    state_content = f"# セッション状態記録\n\n## Git ブランチ: {branch}\n\n本文\n"
    (checkpoints_dir / "session_state.md").write_text(state_content, encoding="utf-8")

    stdin = json.dumps({"source": "startup"})
    result = _run_resume(tmp_path, stdin)

    assert result.returncode == 0
    assert "本文" in result.stdout
    assert "自動" in result.stdout
    assert "確認" in result.stdout


def test_pc09_compact_source_outputs_nothing(tmp_path: Path) -> None:
    """PC-9: source=compact では stdout 空・exit 0(既存 reinject との二重注入なし)。"""
    branch = "pipeline/20260805-foo"
    _init_repo(tmp_path, branch)
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    (checkpoints_dir / "session_state.md").write_text(
        f"## Git ブランチ: {branch}\n", encoding="utf-8"
    )

    stdin = json.dumps({"source": "compact"})
    result = _run_resume(tmp_path, stdin)

    assert result.returncode == 0
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# PC-10: 状態ファイルが無い/空/不正UTF-8でも起動を妨げない
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("setup", ["missing", "empty", "invalid-utf8"])
def test_pc10_broken_state_produces_no_output(tmp_path: Path, setup: str) -> None:
    """PC-10: 状態ファイルなし/空/不正UTF-8のいずれでも stdout 空・exit 0・トレースバックなし。"""
    branch = "pipeline/20260805-foo"
    _init_repo(tmp_path, branch)
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    state_path = checkpoints_dir / "session_state.md"
    if setup == "empty":
        state_path.write_text("", encoding="utf-8")
    elif setup == "invalid-utf8":
        state_path.write_bytes(b"\xff\xfe invalid utf-8 \xff")
    # "missing" はファイルを作らない

    stdin = json.dumps({"source": "startup"})
    result = _run_resume(tmp_path, stdin)

    assert result.returncode == 0
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# PC-11: ブランチ不一致 / 72時間超の記録は注入しない
# ---------------------------------------------------------------------------


def test_pc11a_branch_mismatch_produces_no_output(tmp_path: Path) -> None:
    """PC-11: 記録されたブランチが現在ブランチと不一致なら stdout 空・exit 0。"""
    _init_repo(tmp_path, "pipeline/20260805-foo")
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    (checkpoints_dir / "session_state.md").write_text(
        "## Git ブランチ: pipeline/other-branch\n", encoding="utf-8"
    )

    stdin = json.dumps({"source": "startup"})
    result = _run_resume(tmp_path, stdin)

    assert result.returncode == 0
    assert result.stdout == ""


def test_pc11b_stale_mtime_produces_no_output(tmp_path: Path) -> None:
    """PC-11: 記録の mtime が73時間前なら stdout 空・exit 0。"""
    branch = "pipeline/20260805-foo"
    _init_repo(tmp_path, branch)
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    state_path = checkpoints_dir / "session_state.md"
    state_path.write_text(f"## Git ブランチ: {branch}\n", encoding="utf-8")
    stale_time = time.time() - 73 * 3600
    os.utime(state_path, (stale_time, stale_time))

    stdin = json.dumps({"source": "startup"})
    result = _run_resume(tmp_path, stdin)

    assert result.returncode == 0
    assert result.stdout == ""


# ---------------------------------------------------------------------------
# PC-12: 既存 reinject_after_compact.py の回帰確認
# ---------------------------------------------------------------------------


def test_pc12_existing_reinject_after_compact_unaffected(tmp_path: Path) -> None:
    """PC-12: source=compact + latest.md ありなら従来どおり latest.md 本文を出力(回帰)。"""
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    (checkpoints_dir / "latest.md").write_text(
        "チェックポイント本文\n", encoding="utf-8"
    )

    stdin = json.dumps({"source": "compact"})
    result = subprocess.run(
        [sys.executable, str(REINJECT_PATH)],
        cwd=str(tmp_path),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 0
    assert "チェックポイント本文" in result.stdout


# ---------------------------------------------------------------------------
# PC-13: slug 導出が plan_gate._slug_from_branch() と一致する
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "branch",
    ["pipeline/20260805-foo", "pipeline/20260805-foo-group-A", "foo"],
)
def test_pc13_slug_derivation_matches_plan_gate(branch: str) -> None:
    """PC-13: record 側の slug 導出が plan_gate._slug_from_branch() と同じ文字列を返す。"""
    plan_gate = _load_module(PLAN_GATE_PATH, "plan_gate")
    record = _load_module(RECORD_PATH, "record_session_state")

    assert record._slug_from_branch(branch) == plan_gate._slug_from_branch(branch)


# ---------------------------------------------------------------------------
# PC-15: あいまい候補は解決せず「該当なし」、直接一致のみ記録する
# ---------------------------------------------------------------------------


def test_pc15a_no_direct_match_reports_not_found(tmp_path: Path) -> None:
    """PC-15: 直接一致 `foo.md` が無い場合、日付つき候補があっても「該当なし」と記録する。"""
    _init_repo(tmp_path, "pipeline/foo")
    plans_dir = tmp_path / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "20260805-foo.md").write_text("計画\n", encoding="utf-8")

    stdin = json.dumps({"transcript_path": ""})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert "該当なし" in text
    assert "20260805-foo.md" not in text


def test_pc15b_two_dated_candidates_still_not_found(tmp_path: Path) -> None:
    """PC-15: 日付つき候補が2件でも glob フォールバックはせず「該当なし」と記録する。"""
    _init_repo(tmp_path, "pipeline/foo")
    plans_dir = tmp_path / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "20260805-foo.md").write_text("計画A\n", encoding="utf-8")
    (plans_dir / "20260806-foo.md").write_text("計画B\n", encoding="utf-8")

    stdin = json.dumps({"transcript_path": ""})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert "該当なし" in text
    assert "20260805-foo.md" not in text
    assert "20260806-foo.md" not in text


def test_pc15c_direct_match_is_recorded(tmp_path: Path) -> None:
    """PC-15: 直接一致 `.claude/plans/foo.md` があればそのパスを記録する。"""
    _init_repo(tmp_path, "pipeline/foo")
    plans_dir = tmp_path / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "foo.md").write_text("計画\n", encoding="utf-8")

    stdin = json.dumps({"transcript_path": ""})
    result = _run_record(tmp_path, stdin)

    assert result.returncode == 0
    text = _state_path(tmp_path).read_text(encoding="utf-8")
    assert ".claude/plans/foo.md" in text
