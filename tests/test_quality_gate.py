"""quality_gate.py の受け入れテスト(P-3: diff カバレッジゲート)。

対象: `.claude/hooks/quality_gate.py` に Step 6 で追加する `_diff_coverage_min()` /
`_check_diff_coverage()`。`tests/test_plan_gate.py` の書式(`subprocess.run(
[sys.executable, <絶対パス>], ...)` での CLI 起動、`_SUBPROCESS_TIMEOUT` 定数)に倣う。

Step 6(`.claude/hooks/quality_gate.py` への実装追加)より前は、`_diff_coverage_min`
が未定義のため閾値パーステストが全件 FAIL するのが正しい状態(RED)。
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

QUALITY_GATE_PATH = (
    Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "quality_gate.py"
)
_SUBPROCESS_TIMEOUT = 30

# ローカル/CI のグローバル git 設定(commit.gpgsign 等)や対話プロンプトが
# フィクスチャ構築に影響しないよう遮断する(test_env_fingerprint.py と同じ方式)
_GIT_ENV = os.environ.copy()
_GIT_ENV.update(
    {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    }
)


def _load_quality_gate() -> ModuleType:
    """quality_gate.py をモジュールとして直接読み込む(`_diff_coverage_min` を単体で呼ぶため)。

    quality_gate.py は `from _common import repo_state_signature` を持つため、
    先に `.claude/hooks/` を sys.path に加えてから exec_module する。
    """
    hooks_dir = str(QUALITY_GATE_PATH.parent)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location("quality_gate", QUALITY_GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", 80),
        ("80", 80),
        ("0", 80),
        ("1e2", 80),
        ("101", 80),
        ("abc", 80),
        (" 75 ", 75),
    ],
    ids=[
        "empty",
        "80",
        "0-out-of-range",
        "1e2-exponent",
        "101-out-of-range",
        "abc",
        "padded-75",
    ],
)
def test_diff_coverage_min_parses_or_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch, value: str, expected: int
) -> None:
    """CLAUDE_DIFF_COVERAGE_MIN を1〜100の整数として読み、読めなければ既定80を返す。

    読めない値で緩めない(fail-safe側に倒す)ことの回帰防止。`1e2` から `1` を
    拾う誤読(python-style.md の行末固定ルール違反)が起きていないかも兼ねて確認する。
    """
    module = _load_quality_gate()
    monkeypatch.setenv("CLAUDE_DIFF_COVERAGE_MIN", value)
    assert module._diff_coverage_min() == expected


def _init_repo_with_main_commit(tmp_path: Path) -> None:
    """`main` ブランチに空コミットを1つ持つ一時 git リポジトリを作る。

    `git rev-parse --verify main` が解決できる状態にしないと、diff-cover 呼び出し
    前の「比較先ブランチが無い」スキップ経路しか通らず、ツール未導入のスキップ
    経路(本来テストしたい経路)を検証できない。
    """
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test User",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=_GIT_ENV,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _run_quality_gate(
    tmp_path: Path, extra_env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """一時 git リポジトリを CLAUDE_WORK_SCOPE に向けて quality_gate.py を CLI 起動する。

    リポジトリ本体を対象にすると既存コードの lint 結果でテストが揺れるため、
    空の一時ディレクトリ + git リポジトリを検査対象にする。セッションが
    CLAUDE_QUALITY_GATE 等を既に注入していても素の状態から検証できるよう、
    まず該当キーを外してから extra_env で明示的に指定する。
    """
    _init_repo_with_main_commit(tmp_path)
    env = os.environ.copy()
    for key in (
        "CLAUDE_QUALITY_GATE",
        "CLAUDE_DIFF_COVERAGE",
        "CLAUDE_DIFF_COVERAGE_MIN",
    ):
        env.pop(key, None)
    env["CLAUDE_WORK_SCOPE"] = str(tmp_path)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(QUALITY_GATE_PATH)],
        cwd=str(tmp_path),
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def test_quality_gate_flag_unset_passes(tmp_path: Path) -> None:
    """CLAUDE_QUALITY_GATE 未設定なら exit 0(diff カバレッジ検査も呼ばれない)。"""
    result = _run_quality_gate(tmp_path, {})
    assert result.returncode == 0


def test_diff_coverage_flag_unset_skips_coverage_check(tmp_path: Path) -> None:
    """CLAUDE_QUALITY_GATE=1 かつ CLAUDE_DIFF_COVERAGE 未設定なら exit 0(カバレッジ検査を呼ばない)。"""
    result = _run_quality_gate(tmp_path, {"CLAUDE_QUALITY_GATE": "1"})
    assert result.returncode == 0


def test_diff_coverage_enabled_but_tools_missing_skips(tmp_path: Path) -> None:
    """CLAUDE_QUALITY_GATE=1 かつ CLAUDE_DIFF_COVERAGE=1 でもツール未導入なら exit 0(スキップ)。

    この開発環境には pytest-cov / diff-cover が未導入であることを前提にした
    経路テスト(検証済みの前提は計画の「未確認の仮定」欄を参照)。
    """
    result = _run_quality_gate(
        tmp_path, {"CLAUDE_QUALITY_GATE": "1", "CLAUDE_DIFF_COVERAGE": "1"}
    )
    assert result.returncode == 0


def test_multiple_failures_all_appear_in_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """failures が2件以上のとき、全件のメッセージが出力に含まれる。

    1件だけ表示して他を落とす実装を防ぐための回帰テスト。ruff/mypy がこの
    開発環境に無くても再現できるよう、共通の `run()` をコマンド種別ごとの
    固定応答へ差し替える(quality_gate.py 自体は変更しない)。
    """
    module = _load_quality_gate()

    def fake_run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
        if "ruff" in cmd:
            return 1, "", "E501 line too long"
        if "radon" in cmd:
            return 0, "", ""
        if "mypy" in cmd:
            return 1, "", "error: Incompatible types"
        return 0, "", ""

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setenv("CLAUDE_QUALITY_GATE", "1")
    monkeypatch.delenv("CLAUDE_DIFF_COVERAGE", raising=False)
    monkeypatch.setenv("CLAUDE_WORK_SCOPE", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "[ruff check]" in captured.err
    assert "[mypy]" in captured.err
