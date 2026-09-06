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
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = _ROOT / ".claude" / "hooks"
STATE_GATE_PATH = HOOKS_DIR / "state_gate.py"
STAGING_PATH = _ROOT / "_staging_skill_state.py"

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
    state_path.write_text('{"a": 1, "b": 1}', encoding="utf-8")

    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": STATE_REL_PATH,
            "old_string": ": 1",
            "new_string": ": 2",
        },
    }
    result = _run_gate(tmp_path, payload)

    assert result.returncode == 0


# ---------------------------------------------------------------------------
# PC-6: `.claude/state/` 配下でない・`.json` でないパス・他ブランチの状態ファイルは
# 内容を問わず通す
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file_path, content",
    [
        ("docs/notes.txt", "not json at all {{{"),
        (".claude/state/notes.md", "任意の本文"),
        (".claude/state/other-branch.json", "not json at all {{{"),
    ],
    ids=["non_state_path", "non_json_extension", "other_branch_state_file"],
)
def test_pc6_out_of_scope_path_allowed_regardless_of_content(
    tmp_path: Path, file_path: str, content: str
) -> None:
    _init_repo(tmp_path)
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
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


# ---------------------------------------------------------------------------
# PC-13: _staging_skill_state.py の冪等性(-k idempotent)
#
# `tests/test_data_protection_phase3.py::test_staging_idempotent_p3_apply_twice`
# (1031行目)・`tests/test_session_monitor.py::test_staging_idempotent_apply_twice`
# (442行目)の書式に倣う: 実リポジトリの保護ファイル(.claude/hooks/・
# .claude/settings.json)はガードで書き込めないため、--root で複製した一時
# ディレクトリに適用し、1回目・2回目の適用結果をバイト単位で比較する。
# ---------------------------------------------------------------------------

_STAGING_APPLY_TARGETS = (
    "_state_common.py",
    "state_gate.py",
    "record_session_state.py",
    "reinject_after_compact.py",
    "resume_session_state.py",
)

pytestmark_staging = pytest.mark.skipif(
    not STAGING_PATH.exists(),
    reason="_staging_skill_state.py が存在しない(gitignore対象。ユーザーの ! 実行待ち)",
)


def _base_env() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }


def _populate_sandbox_hooks(hooks_dir: Path) -> None:
    """staging 適用対象(a)〜(e)が読む既存フックを、実リポジトリからサンドボックスへ複製する。"""
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "plan_gate.py",
        "record_session_state.py",
        "reinject_after_compact.py",
        "resume_session_state.py",
    ):
        (hooks_dir / name).write_text(
            (HOOKS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )


@pytestmark_staging
def test_staging_idempotent_apply_twice(tmp_path: Path) -> None:
    """PC-13/R-016: 同一 --root への2回連続適用で、適用先ファイル群がバイト単位で同一。"""
    root = tmp_path / "fake_root"
    hooks_dir = root / ".claude" / "hooks"
    _populate_sandbox_hooks(hooks_dir)

    settings_src = json.loads(
        (_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    (root / ".claude" / "settings.json").write_text(
        json.dumps(settings_src, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    env = _base_env()
    result1 = subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )
    assert result1.returncode == 0, result1.stdout + result1.stderr

    snapshot_paths = [root / ".claude" / "settings.json"] + [
        hooks_dir / name for name in _STAGING_APPLY_TARGETS
    ]
    for p in snapshot_paths:
        assert p.exists(), f"1回目の適用後に {p} が無い"
    snapshot = {p: p.read_bytes() for p in snapshot_paths}

    result2 = subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )
    assert result2.returncode == 0, result2.stdout + result2.stderr

    for p, before in snapshot.items():
        assert p.read_bytes() == before, f"{p} が2回目の適用で変化した(冪等でない)"

    settings_after = json.loads(
        (root / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    edit_matchers = [
        h
        for h in settings_after["hooks"]["PreToolUse"]
        if h.get("matcher") == "Edit|Write|NotebookEdit"
    ]
    assert len(edit_matchers) == 1, f"matcherが重複登録された: {edit_matchers}"
    state_gate_hooks = [
        h for h in edit_matchers[0]["hooks"] if "state_gate.py" in h.get("command", "")
    ]
    assert len(state_gate_hooks) == 1, (
        f"state_gateがhooks配列に重複登録されている: {state_gate_hooks}"
    )


# ---------------------------------------------------------------------------
# R-001/PC-1,PC-2: 型不一致(スキーマ期待型と不一致)は TypeError を投げず、
# 通常のスキーマ違反として exit 2・stderr にキー名・Traceback 非出力
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides, expected_key",
    [
        pytest.param({"size": ["S"]}, "size", id="size_is_list"),
        pytest.param(
            {
                "gates": {
                    "spec_checklist": None,
                    "plan_premortem": None,
                    "plan_approval": None,
                    "evaluator": {"v": "PASS"},
                    "final_gate": None,
                }
            },
            "evaluator",
            id="gates_evaluator_is_dict",
        ),
        pytest.param(
            {"open_findings": "not a list"}, "open_findings", id="open_findings_is_str"
        ),
        pytest.param(
            {"artifacts": {"plan": 123, "design_doc": None, "report": None}},
            "plan",
            id="artifacts_plan_is_number",
        ),
        pytest.param(
            {
                "size": ["S"],
                "gates": {
                    "spec_checklist": None,
                    "plan_premortem": None,
                    "plan_approval": None,
                    "evaluator": {"v": "PASS"},
                    "final_gate": None,
                },
            },
            "size",
            id="multiple_keys_simultaneously_invalid",
        ),
        pytest.param(
            {
                "artifacts": {"plan": ["a"], "design_doc": None, "report": None},
                "open_findings": [{"note": "問題"}],
            },
            "open_findings",
            id="nested_artifacts_plan_list_and_open_findings_element_dict",
        ),
    ],
)
def test_invalid_type_mismatch_variations(
    tmp_path: Path, overrides: dict, expected_key: str
) -> None:
    """R-001/PC-1,PC-2: size=list・gates値=dict等の型不一致でも TypeError を投げず
    通常のスキーマ違反としてブロックする(入れ子・複数キー同時不正を含む)。"""
    _init_repo(tmp_path)
    result = _run_gate(tmp_path, _write_payload(_valid_state(**overrides)))

    assert result.returncode == 2
    assert expected_key in result.stderr
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# R-002/PC-3,PC-4: state_gate の検証はペイロード cwd 基準で行われ、プロセス cwd と
# 異なっていても検証がスキップされない
# ---------------------------------------------------------------------------


def test_cwd_separation_violation_blocked(tmp_path: Path) -> None:
    """PC-3: プロセス cwd がリポジトリ外でも、ペイロード cwd 基準でスキーマ違反を検出する。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    payload = _write_payload(_valid_state(size=["S"]))
    payload["cwd"] = str(repo)

    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(elsewhere),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 2
    assert "size" in result.stderr


def test_cwd_separation_compliant_allowed(tmp_path: Path) -> None:
    """PC-4: cwd 分離下でもスキーマ準拠なら許可される(exit 0・BLOCKED 非出力)。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    payload = _write_payload(_valid_state())
    payload["cwd"] = str(repo)

    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(elsewhere),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 0
    assert "BLOCKED" not in result.stderr


def test_cwd_payload_subdirectory_violation_blocked(tmp_path: Path) -> None:
    """回帰(Codexクロスレビュー指摘): ペイロード cwd がリポジトリのサブディレクトリ
    (例: tests/)でも、リポジトリルート直下の状態ファイルへの絶対パス書き込みは検証
    がスキップされずスキーマ違反をブロックする。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    subdir = repo / "tests"
    subdir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    state_abs_path = str((repo / STATE_REL_PATH).resolve())
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": state_abs_path,
            "content": json.dumps(_valid_state(size=["S"]), ensure_ascii=False),
        },
        "cwd": str(subdir),
    }

    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(elsewhere),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 2
    assert "size" in result.stderr


def test_cwd_payload_subdirectory_compliant_allowed(tmp_path: Path) -> None:
    """同構成でスキーマ準拠なら許可される(exit 0・BLOCKED 非出力)。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    subdir = repo / "tests"
    subdir.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    state_abs_path = str((repo / STATE_REL_PATH).resolve())
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": state_abs_path,
            "content": json.dumps(_valid_state(), ensure_ascii=False),
        },
        "cwd": str(subdir),
    }

    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(elsewhere),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 0
    assert "BLOCKED" not in result.stderr


def test_cwd_symlink_violation_blocked(tmp_path: Path) -> None:
    """回帰(Codexクロスレビュー指摘): cwd/file_path がシンボリックリンク経由でも
    リンク先の実リポジトリ基準で検証がスキップされずスキーマ違反をブロックする。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    alias = tmp_path / "repo-alias"
    alias.symlink_to(repo, target_is_directory=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    state_abs_path = str(alias / STATE_REL_PATH)
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": state_abs_path,
            "content": json.dumps(_valid_state(size=["S"]), ensure_ascii=False),
        },
        "cwd": str(alias),
    }

    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(elsewhere),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 2
    assert "size" in result.stderr


def test_cwd_symlink_compliant_allowed(tmp_path: Path) -> None:
    """同構成でスキーマ準拠なら許可される(exit 0・BLOCKED 非出力)。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    alias = tmp_path / "repo-alias"
    alias.symlink_to(repo, target_is_directory=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    state_abs_path = str(alias / STATE_REL_PATH)
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": state_abs_path,
            "content": json.dumps(_valid_state(), ensure_ascii=False),
        },
        "cwd": str(alias),
    }

    result = subprocess.run(
        [sys.executable, str(STATE_GATE_PATH)],
        cwd=str(elsewhere),
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )

    assert result.returncode == 0
    assert "BLOCKED" not in result.stderr


def test_state_dir_symlink_violation_blocked(tmp_path: Path) -> None:
    """回帰(Codexクロスレビュー指摘・3件目): `.claude/state` ディレクトリ自体が
    シンボリックリンクでも、対象パス判定の早期returnが誤って対象外にせず
    スキーマ違反をブロックする。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    real_state_dir = tmp_path / "real-state"
    real_state_dir.mkdir()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "state").symlink_to(real_state_dir, target_is_directory=True)

    result = _run_gate(repo, _write_payload(_valid_state(size=["S"])))

    assert result.returncode == 2
    assert "size" in result.stderr


def test_state_dir_symlink_compliant_allowed(tmp_path: Path) -> None:
    """同構成でスキーマ準拠なら許可される(exit 0・BLOCKED 非出力)。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    real_state_dir = tmp_path / "real-state"
    real_state_dir.mkdir()
    (repo / ".claude").mkdir()
    (repo / ".claude" / "state").symlink_to(real_state_dir, target_is_directory=True)

    result = _run_gate(repo, _write_payload(_valid_state()))

    assert result.returncode == 0
    assert "BLOCKED" not in result.stderr
