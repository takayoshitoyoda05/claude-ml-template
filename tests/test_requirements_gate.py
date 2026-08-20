"""requirements_gate.py の受け入れテスト。

`tests/test_plan_gate.py` に倣い、フックを import せず subprocess で CLI 起動する
(実運用の PreToolUse フックと同じ経路で検証するため)。

フック本体はユーザーが `! uv run python _staging_requirements_gate.py` で
適用するまで存在しないため、未適用の間は全ケースを skip する。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = _ROOT / ".claude" / "hooks" / "requirements_gate.py"
_SUBPROCESS_TIMEOUT = 30

pytestmark = pytest.mark.skipif(
    not HOOK_PATH.exists(),
    reason="_staging_requirements_gate.py 未適用(ユーザーの ! 実行待ち)",
)

_VALID_DESIGN = (
    "# ダミー設計書\n\n"
    "## 受け入れ条件\n"
    "| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |\n"
    "|---|---|---|---|---|---|\n"
    "| R-001 | ダミー要件 | true | exit 0 | auto | |\n"
)
# 列数不足でテーブルとして不正(AcceptanceTableError になる)
_BROKEN_DESIGN = (
    "# 壊れた設計書\n\n## 受け入れ条件\n| ID | 要件 |\n|---|---|\n| R-001 | ダミー |\n"
)
_PLAN_PAYLOAD = {"tool_input": {"file_path": ".claude/plans/20260820-test.md"}}


def _run(
    payload_text: str, gate: str, req_docs: str, cwd: Path
) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "PYTHONPATH": str(_ROOT / ".claude" / "hooks"),
        "CLAUDE_REQUIREMENTS_GATE": gate,
        "CLAUDE_REQ_DOCS": req_docs,
    }
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )


@pytest.fixture()
def empty_docs(tmp_path: Path) -> Path:
    d = tmp_path / "docs_empty"
    d.mkdir()
    return d


@pytest.fixture()
def valid_docs(tmp_path: Path) -> Path:
    d = tmp_path / "docs_valid"
    d.mkdir()
    (d / "spec.md").write_text(_VALID_DESIGN, encoding="utf-8")
    return d


def test_gate_off_passes(tmp_path: Path, empty_docs: Path) -> None:
    result = _run(json.dumps(_PLAN_PAYLOAD), "0", str(empty_docs), tmp_path)
    assert result.returncode == 0


def test_non_plan_path_passes(tmp_path: Path, empty_docs: Path) -> None:
    payload = {"tool_input": {"file_path": "src/train.py"}}
    result = _run(json.dumps(payload), "1", str(empty_docs), tmp_path)
    assert result.returncode == 0


def test_plan_without_design_blocked(tmp_path: Path, empty_docs: Path) -> None:
    result = _run(json.dumps(_PLAN_PAYLOAD), "1", str(empty_docs), tmp_path)
    assert result.returncode == 2
    assert "requirements_gate" in result.stderr


def test_plan_with_valid_design_passes(tmp_path: Path, valid_docs: Path) -> None:
    result = _run(json.dumps(_PLAN_PAYLOAD), "1", str(valid_docs), tmp_path)
    assert result.returncode == 0


def test_broken_table_only_blocked(tmp_path: Path) -> None:
    d = tmp_path / "docs_broken"
    d.mkdir()
    (d / "spec.md").write_text(_BROKEN_DESIGN, encoding="utf-8")
    result = _run(json.dumps(_PLAN_PAYLOAD), "1", str(d), tmp_path)
    assert result.returncode == 2


def test_multiple_dirs_second_hit_passes(
    tmp_path: Path, empty_docs: Path, valid_docs: Path
) -> None:
    req_docs = os.pathsep.join([str(empty_docs), str(valid_docs)])
    result = _run(json.dumps(_PLAN_PAYLOAD), "1", req_docs, tmp_path)
    assert result.returncode == 0


def test_windows_path_separator_blocked(tmp_path: Path, empty_docs: Path) -> None:
    payload = {"tool_input": {"file_path": ".claude\\plans\\20260820-test.md"}}
    result = _run(json.dumps(payload), "1", str(empty_docs), tmp_path)
    assert result.returncode == 2


def test_malformed_stdin_fails_open(tmp_path: Path, empty_docs: Path) -> None:
    result = _run("これはJSONではない", "1", str(empty_docs), tmp_path)
    assert result.returncode == 0
