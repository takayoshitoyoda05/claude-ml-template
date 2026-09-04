"""state_gate.py(PreToolUse: `.claude/state/<slug>.json` のスキーマ検証)の受け入れテスト。

対象: `.claude/plans/20260904-skill-state.md` の PC-1〜PC-7・PC-15。
設計書: `docs/active/20260904-skill-state-spec.md` §4.5(状態スキーマ)。

書式は `tests/test_session_resume.py`(`subprocess.run([sys.executable, <絶対パス>], ...)`・
`_SUBPROCESS_TIMEOUT`)に倣う。

Step 5(`_staging_skill_state.py` によるユーザー適用)より前は `.claude/hooks/state_gate.py`
が存在しないため `subprocess.run` が `FileNotFoundError` で失敗し全 FAIL になるのが
正しい状態(RED)。
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
STATE_GATE_PATH = HOOKS_DIR / "state_gate.py"

_SUBPROCESS_TIMEOUT = 15
BRANCH = "pipeline/20260904-skill-state"
SLUG = "20260904-skill-state"
STATE_REL_PATH = f".claude/state/{SLUG}.json"


def _init_repo(tmp_path: Path, branch: str = BRANCH) -> None:
    """`tmp_path` に `git init -b <branch>` する(コミットは不要。`git branch --show-current`
    は unborn branch でもブランチ名を返すことを実測済み)。"""
    subprocess.run(
        ["git", "init", "-q", "-b", branch],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _run_gate(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    """state_gate.py を CLI として subprocess 起動する。"""
    return subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(tmp_path),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _valid_state(**overrides: object) -> dict:
    state = {
        "schema_version": 1,
        "branch": BRANCH,
        "task_summary": "テスト用の要約",
        "size": "S",
        "current_step": "1",
        "gates": {
            "spec_checklist": None,
            "plan_premortem": None,
            "plan_approval": None,
            "evaluator": None,
            "final_gate": None,
        },
        "open_findings": [],
        "artifacts": {"plan": None, "design_doc": None, "report": None},
        "next_action": "初期状態を作成する",
        "notes": "",
        "updated_at": "2026-09-04T10:00:00",
    }
    state.update(overrides)
    return state


def _write_payload(state: dict) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {
            "file_path": STATE_REL_PATH,
            "content": json.dumps(state, ensure_ascii=False),
        },
    }


# ---------------------------------------------------------------------------
# PC-1: 正しい状態 JSON の Write は許可される(-k valid)
# ---------------------------------------------------------------------------


def test_valid_write_state_allowed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state()))

    assert result.returncode == 0
    assert "BLOCKED" not in result.stderr


def test_valid_edit_state_allowed(tmp_path: Path) -> None:
    """PC-1: Edit の適用結果がスキーマに準拠していれば許可される(-k valid)。"""
    _init_repo(tmp_path)
    state_path = tmp_path / STATE_REL_PATH
    state_path.parent.mkdir(parents=True)
    initial = _valid_state(current_step="1")
    state_path.write_text(json.dumps(initial, ensure_ascii=False), encoding="utf-8")

    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": STATE_REL_PATH,
            "old_string": '"current_step": "1"',
            "new_string": '"current_step": "2"',
        },
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 0
    assert "BLOCKED" not in result.stderr


@pytest.mark.parametrize(
    "gates_override",
    [
        {
            k: None
            for k in (
                "spec_checklist",
                "plan_premortem",
                "plan_approval",
                "evaluator",
                "final_gate",
            )
        },
        {
            "spec_checklist": "READY",
            "plan_premortem": "PASS",
            "plan_approval": "human",
            "evaluator": "PASS",
            "final_gate": "APPROVE",
        },
    ],
    ids=["all_null", "all_enum_set"],
)
def test_valid_gates_variations(tmp_path: Path, gates_override: dict) -> None:
    """PC-1 の入力バリエーション: gates が全て null / 全て enum 値。"""
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(gates=gates_override)))

    assert result.returncode == 0


@pytest.mark.parametrize(
    "open_findings",
    [[], ["1件目の懸念", "2件目の懸念"]],
    ids=["empty", "multiple"],
)
def test_valid_open_findings_variations(tmp_path: Path, open_findings: list) -> None:
    """PC-1 の入力バリエーション: open_findings が空リスト / 複数要素。"""
    _init_repo(tmp_path)
    result = _run_gate(
        tmp_path, _write_payload(_valid_state(open_findings=open_findings))
    )

    assert result.returncode == 0


@pytest.mark.parametrize(
    "artifacts",
    [
        {"plan": None, "design_doc": None, "report": None},
        {
            "plan": ".claude/plans/x.md",
            "design_doc": "docs/active/x.md",
            "report": "docs/reports/x/report.md",
        },
    ],
    ids=["all_null", "all_strings"],
)
def test_valid_artifacts_variations(tmp_path: Path, artifacts: dict) -> None:
    """PC-1 の入力バリエーション: artifacts の3キーが null / 文字列。"""
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(artifacts=artifacts)))

    assert result.returncode == 0


# ---------------------------------------------------------------------------
# PC-2: 必須キー欠落・型不一致・enum外はブロックされる(-k invalid)
# ---------------------------------------------------------------------------


def test_invalid_missing_required_key(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    state = _valid_state()
    del state["current_step"]
    result = _run_gate(tmp_path, _write_payload(state))

    assert result.returncode == 2
    assert "current_step" in result.stderr


def test_invalid_type_mismatch_current_step(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(current_step=6)))

    assert result.returncode == 2
    assert "current_step" in result.stderr


def test_invalid_enum_outside_evaluator(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    gates = _valid_state()["gates"]
    gates["evaluator"] = "OK"
    result = _run_gate(tmp_path, _write_payload(_valid_state(gates=gates)))

    assert result.returncode == 2
    assert "evaluator" in result.stderr


def test_invalid_open_findings_type_mismatch(tmp_path: Path) -> None:
    """PC-2 の入力バリエーション: open_findings の要素が文字列でない。"""
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(open_findings=[1, 2])))

    assert result.returncode == 2
    assert "open_findings" in result.stderr


def test_invalid_edit_result_blocked(tmp_path: Path) -> None:
    """PC-7: Edit 適用結果がスキーマ違反ならブロックする。"""
    _init_repo(tmp_path)
    state_path = tmp_path / STATE_REL_PATH
    state_path.parent.mkdir(parents=True)
    initial = _valid_state(size="S")
    state_path.write_text(json.dumps(initial, ensure_ascii=False), encoding="utf-8")

    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": STATE_REL_PATH,
            "old_string": '"size": "S"',
            "new_string": '"size": "XL"',
        },
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 2
    assert "size" in result.stderr


# ---------------------------------------------------------------------------
# PC-3: 未知キーはブロックされる(-k unknown_key)
# ---------------------------------------------------------------------------


def test_unknown_key_top_level(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    state = _valid_state()
    state["extra_field"] = "許されない"
    result = _run_gate(tmp_path, _write_payload(state))

    assert result.returncode == 2
    assert "extra_field" in result.stderr


def test_unknown_key_nested_artifacts(tmp_path: Path) -> None:
    """PC-3 の入力バリエーション: artifacts に未知のサブキーを追加(入れ子の未知キー)。"""
    _init_repo(tmp_path)
    artifacts = _valid_state()["artifacts"]
    artifacts["extra_artifact"] = "許されない"
    result = _run_gate(tmp_path, _write_payload(_valid_state(artifacts=artifacts)))

    assert result.returncode == 2
    assert "extra_artifact" in result.stderr


# ---------------------------------------------------------------------------
# PC-4: notes 500字上限(-k notes_limit)
# ---------------------------------------------------------------------------


def test_notes_limit_500_chars_allowed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(notes="a" * 500)))

    assert result.returncode == 0


def test_notes_limit_501_chars_blocked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(notes="a" * 501)))

    assert result.returncode == 2
    assert "notes" in result.stderr


# ---------------------------------------------------------------------------
# PC-5: 内部で予期せぬ例外が起きても fail-open(-k fail_open)
# ---------------------------------------------------------------------------


def test_fail_open_broken_stdin(tmp_path: Path) -> None:
    """PC-5: 壊れた stdin ペイロードでも exit 0・ブロックしない。"""
    _init_repo(tmp_path)
    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(tmp_path),
        input="not json {{{",
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr


def test_fail_open_edit_ambiguous_old_string(tmp_path: Path) -> None:
    """PC-7/PC-5系: old_string が一意に特定できない場合は fail-open(exit 0)。"""
    _init_repo(tmp_path)
    state_path = tmp_path / STATE_REL_PATH
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"x": 1, "x2": 1}', encoding="utf-8")

    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": STATE_REL_PATH,
            "old_string": '"x"',
            "new_string": '"y"',
        },
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 0


# ---------------------------------------------------------------------------
# PC-6: `.claude/state/` 配下でない・`.json` でないパスは内容を問わず通す
# ---------------------------------------------------------------------------


def test_pc6_non_state_path_allowed_regardless_of_content(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "docs/notes.txt", "content": "not json at all {{{"},
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 0


def test_pc6_non_json_extension_under_state_dir_allowed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": ".claude/state/notes.md", "content": "任意の本文"},
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 0


def test_pc6_other_branch_state_file_allowed(tmp_path: Path) -> None:
    """PC-6 の拡張: 現在ブランチと異なる slug の状態ファイルは対象外として通す。"""
    _init_repo(tmp_path)
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": ".claude/state/other-branch.json",
            "content": "not json at all {{{",
        },
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 0


# ---------------------------------------------------------------------------
# PC-15: slug 導出が plan_gate から import されている(正規表現複製禁止)
# ---------------------------------------------------------------------------


def test_pc15_slug_derivation_imported_not_duplicated() -> None:
    assert STATE_GATE_PATH.exists(), "state_gate.py が未適用(RED)"
    source = STATE_GATE_PATH.read_text(encoding="utf-8")
    assert "from plan_gate import _slug_from_branch" in source
    assert "-group-" not in source
