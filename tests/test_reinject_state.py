"""SessionStart 注入フック(reinject_after_compact.py / resume_session_state.py)への
状態セクション注入の受け入れテスト。

対象: `.claude/plans/20260904-skill-state.md` の PC-8〜PC-10。
設計書: `docs/active/20260904-skill-state-spec.md` §4.5(状態スキーマ)。

書式は `tests/test_session_resume.py` に倣う。Step 5(`_staging_skill_state.py`
によるユーザー適用)より前は両フックに状態注入が実装されていないため、
本ファイルの全テストが FAIL するのが正しい状態(RED)。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
REINJECT_PATH = HOOKS_DIR / "reinject_after_compact.py"
RESUME_PATH = HOOKS_DIR / "resume_session_state.py"

_SUBPROCESS_TIMEOUT = 15
BRANCH = "pipeline/20260904-skill-state"
SLUG = "20260904-skill-state"
_STATE_HEADING = "## 現在の実行状態(検証済み・これを正とする)"
_CHECKPOINT_HEADING = "## 直前のチェックポイント"


def _init_repo(tmp_path: Path, branch: str = BRANCH) -> None:
    subprocess.run(
        ["git", "init", "-q", "-b", branch],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _valid_state() -> dict:
    return {
        "schema_version": 1,
        "branch": BRANCH,
        "task_summary": "テスト用の要約",
        "size": "S",
        "current_step": "6.2",
        "gates": {
            "spec_checklist": "READY",
            "plan_premortem": "PASS",
            "plan_approval": None,
            "evaluator": None,
            "final_gate": None,
        },
        "open_findings": [],
        "artifacts": {"plan": ".claude/plans/x.md", "design_doc": None, "report": None},
        "next_action": "Step 6 を続行する",
        "notes": "",
        "updated_at": "2026-09-04T10:00:00",
    }


def _write_state_file(tmp_path: Path, content: str) -> None:
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{SLUG}.json").write_text(content, encoding="utf-8")


def _run_hook(
    path: Path, tmp_path: Path, stdin_payload: dict
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(path)],
        cwd=str(tmp_path),
        input=json.dumps(stdin_payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# PC-8: compact 時、状態セクションが最優先(直前のチェックポイントより前)で出る
# ---------------------------------------------------------------------------


def test_compact_state_section_appears_before_checkpoint(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_state_file(tmp_path, json.dumps(_valid_state(), ensure_ascii=False))
    checkpoints_dir = tmp_path / ".claude" / "checkpoints"
    checkpoints_dir.mkdir(parents=True)
    (checkpoints_dir / "latest.md").write_text(
        "チェックポイント本文\n", encoding="utf-8"
    )

    result = _run_hook(REINJECT_PATH, tmp_path, {"source": "compact"})

    assert result.returncode == 0
    assert _STATE_HEADING in result.stdout
    assert _CHECKPOINT_HEADING in result.stdout
    assert "6.2" in result.stdout
    assert result.stdout.index(_STATE_HEADING) < result.stdout.index(
        _CHECKPOINT_HEADING
    )


def test_compact_state_section_included_without_checkpoint(tmp_path: Path) -> None:
    """PC-8: latest.md が無くても状態セクションだけは出る(既存回帰と両立)。"""
    _init_repo(tmp_path)
    _write_state_file(tmp_path, json.dumps(_valid_state(), ensure_ascii=False))

    result = _run_hook(REINJECT_PATH, tmp_path, {"source": "compact"})

    assert result.returncode == 0
    assert _STATE_HEADING in result.stdout


# ---------------------------------------------------------------------------
# PC-9: startup 時、状態ファイルがあれば同セクションを注入する
# ---------------------------------------------------------------------------


def test_startup_injects_state_section(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_state_file(tmp_path, json.dumps(_valid_state(), ensure_ascii=False))

    result = _run_hook(RESUME_PATH, tmp_path, {"source": "startup"})

    assert result.returncode == 0
    assert _STATE_HEADING in result.stdout
    assert "6.2" in result.stdout


# ---------------------------------------------------------------------------
# PC-10: 状態ファイルが壊れている/不在+計画ありは1行通知、両方不在は沈黙する
#
# ユーザー決定(2026-09-04, R-010 の解決): 状態ファイル「不在」を無条件で通知すると
# 非パイプラインセッションの起動時ノイズになり、かつ tests/test_session_resume.py の
# 既存「記録なしなら stdout 空」不変条件を壊す(そちらは本計画の変更対象外)。
# そのため不在時は同ブランチの計画ファイル(`.claude/plans/<slug>.md`)の有無で
# 3分岐する(設計書 §4 参照)。
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hook_path, source", [(REINJECT_PATH, "compact"), (RESUME_PATH, "startup")]
)
def test_broken_state_invalid_json_shows_notice_only(
    tmp_path: Path, hook_path: Path, source: str
) -> None:
    """状態ファイルが存在するが JSON 破損: 計画ファイルの有無に関わらず無条件で1行通知。"""
    _init_repo(tmp_path)
    _write_state_file(tmp_path, "not json at all {{{")

    result = _run_hook(hook_path, tmp_path, {"source": source})

    assert result.returncode == 0
    assert _STATE_HEADING not in result.stdout
    assert "状態ファイルが読めない" in result.stdout


@pytest.mark.parametrize(
    "hook_path, source", [(REINJECT_PATH, "compact"), (RESUME_PATH, "startup")]
)
def test_broken_missing_state_with_plan_shows_notice_only(
    tmp_path: Path, hook_path: Path, source: str
) -> None:
    """状態ファイル不在+同ブランチの計画ファイルあり(パイプラインが動いていた証拠): 1行通知。"""
    _init_repo(tmp_path)
    plans_dir = tmp_path / ".claude" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / f"{SLUG}.md").write_text("計画本文\n", encoding="utf-8")
    # 状態ファイルは作らない(missing)

    result = _run_hook(hook_path, tmp_path, {"source": source})

    assert result.returncode == 0
    assert _STATE_HEADING not in result.stdout
    assert "状態ファイルが読めない" in result.stdout


@pytest.mark.parametrize(
    "hook_path, source", [(REINJECT_PATH, "compact"), (RESUME_PATH, "startup")]
)
def test_broken_missing_state_and_missing_plan_stays_silent(
    tmp_path: Path, hook_path: Path, source: str
) -> None:
    """状態ファイル・計画ファイルとも不在(非パイプラインセッション): 状態セクションも通知も出さない。

    resume_session_state.py(startup)側は、この場合 stdout が完全に空になる
    既存の不変条件(tests/test_session_resume.py)を壊さないことも併せて確認する。
    """
    _init_repo(tmp_path)
    # 状態ファイル・計画ファイルともに作らない

    result = _run_hook(hook_path, tmp_path, {"source": source})

    assert result.returncode == 0
    assert _STATE_HEADING not in result.stdout
    assert "状態ファイルが読めない" not in result.stdout
    if source == "startup":
        assert result.stdout == ""


# ---------------------------------------------------------------------------
# 回帰: source が対象外のときは従来どおり(状態注入もされない)
# ---------------------------------------------------------------------------


def test_reinject_startup_source_unaffected(tmp_path: Path) -> None:
    """reinject_after_compact.py は source=startup では何もしない(既存回帰)。"""
    _init_repo(tmp_path)
    _write_state_file(tmp_path, json.dumps(_valid_state(), ensure_ascii=False))

    result = _run_hook(REINJECT_PATH, tmp_path, {"source": "startup"})

    assert result.returncode == 0
    assert result.stdout == ""
