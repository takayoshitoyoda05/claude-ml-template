"""研究データ保護 Phase 1(規約・台帳・権限検査)の受け入れテスト。

`tests/test_session_monitor.py` の様式に倣う(冒頭docstring・`_ROOT`定数・
subprocess起動・`pytest.mark.skipif`・tmp_path fixture)。

invariants.md への追記(データ三原則・持ち出し規制・機械検査の対応表)は
保護パスかつ HITL 対象のため、`_staging_data_protection_p1.py` を
ユーザーが `! uv run python _staging_data_protection_p1.py` で適用するまで
存在しない。適用済みかどうかは invariants.md 中に
`### 研究データ保護` 節があるかで判定し、無い間は invariants 依存の
3ケース(principles/egress/check_mapping)のみ個別に skip する。
staging スクリプト自体の冪等性テストは `_staging_data_protection_p1.py`
不在時に skip する。

doctor 実行系テストは `verify-installers.sh` の `place_installers` の前例
(作業ツリー版スクリプトの `TEMPLATE_REPO` を sed で `file://<リポジトリ
ルート>` に差し替えてサンドボックスで実行する)に倣う。root(euid 0)では
chmod による書き込み不可が再現できないため skip する。uv・git 不在時も
skip する。
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
INVARIANTS_PATH = _ROOT / ".claude" / "improvements" / "invariants.md"
STAGING_PATH = _ROOT / "_staging_data_protection_p1.py"
DATALOG_TEMPLATE_PATH = _ROOT / "templates" / "DATA_LOG.md.template"
DOCTOR_SH_PATH = _ROOT / "doctor.sh"
DOCTOR_PS1_PATH = _ROOT / "doctor.ps1"
HANDOFF_SKILL_PATH = _ROOT / ".claude" / "skills" / "handoff" / "SKILL.md"
PAPER_SKILL_PATH = _ROOT / ".claude" / "skills" / "paper-writing" / "SKILL.md"
README_PATH = _ROOT / "README.md"

_SUBPROCESS_TIMEOUT = 60

# 計画Step5の確定名(premortem MEDIUM反映)。doctor.sh/.ps1が出す警告マーカー
_MARKER_RAW_WRITABLE = "[DATA-RAW-WRITABLE]"
_MARKER_PROCESSED_READONLY = "[DATA-PROCESSED-READONLY]"
_MARKER_LOG_MISSING = "[DATA-LOG-MISSING]"
_ALL_MARKERS = (_MARKER_RAW_WRITABLE, _MARKER_PROCESSED_READONLY, _MARKER_LOG_MISSING)

# invariants.mdへの追記節見出し(計画Step4)。この見出しの有無で適用済みかを判定する
_DATA_PROTECTION_HEADING = "### 研究データ保護"

# handoff/paper-writing 両スキルに入る公開前チェックリスト7点(設計書3節の原文どおり)
REQUIRED_CHECKLIST_ITEMS = (
    "git 履歴",
    "notebook 出力",
    "テスト fixture",
    "ログ",
    "レポート・evidence",
    "MLflow",
    "exports 予定物",
)

REQUIRED_DATALOG_COLUMNS = (
    "データセット名",
    "入手元",
    "入手日",
    "ライセンス",
    "sha256",
    "前処理コマンド",
    "識別子列",
)


def _invariants_text() -> str:
    if not INVARIANTS_PATH.exists():
        return ""
    return INVARIANTS_PATH.read_text(encoding="utf-8")


def _extract_section(text: str, heading: str) -> str:
    """`heading`行から次の`##`/`###`見出し行までを抜き出す(無ければ空文字)。

    Args:
        text: 探索対象の全文。
        heading: 探す見出し行(完全一致)。

    Returns:
        見出し行を含むセクション本文。見出しが見つからなければ空文字。
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## ") or lines[j].startswith("### "):
            end = j
            break
    return "\n".join(lines[start:end])


pytestmark_invariants = pytest.mark.skipif(
    _DATA_PROTECTION_HEADING not in _invariants_text(),
    reason="_staging_data_protection_p1.py 未適用"
    "(invariants.md に### 研究データ保護節が無い)",
)


# --- R-001/R-002/R-003: invariants.md ---


@pytestmark_invariants
def test_invariants_principles() -> None:
    section = _extract_section(_invariants_text(), _DATA_PROTECTION_HEADING)
    assert section, "### 研究データ保護節が見つからない"
    # データ三原則: raw不可侵 / 前処理は必ずスクリプト / DATA_LOGが来歴の唯一の真実
    assert "raw" in section
    assert "不可侵" in section
    assert "スクリプト" in section
    assert "DATA_LOG" in section
    assert "唯一の" in section


@pytestmark_invariants
def test_invariants_egress() -> None:
    section = _extract_section(_invariants_text(), _DATA_PROTECTION_HEADING)
    assert section, "### 研究データ保護節が見つからない"
    # 持ち出し規制: 外部に出してよいのは集計値・図・ハッシュのみ
    assert "集計値" in section
    assert "図" in section
    assert "ハッシュ" in section


@pytestmark_invariants
def test_invariants_check_mapping() -> None:
    section = _extract_section(_invariants_text(), _DATA_PROTECTION_HEADING)
    assert section, "### 研究データ保護節が見つからない"
    bullet_lines = [
        line for line in section.splitlines() if line.strip().startswith("- ")
    ]
    assert bullet_lines, "データ規律の箇条書きが見つからない"
    check_name_pattern = re.compile(r"\[DATA-[A-Z-]+\]|Phase\s*2")
    lines_without_check = [
        line for line in bullet_lines if not check_name_pattern.search(line)
    ]
    assert lines_without_check == [], (
        "機械検査名(doctorマーカーまたはPhase 2ゲート名)の無い規律がある: "
        f"{lines_without_check}"
    )


# --- R-004: DATA_LOG.md.template ---


def test_datalog_template_required_columns() -> None:
    assert DATALOG_TEMPLATE_PATH.exists(), f"{DATALOG_TEMPLATE_PATH} が存在しない"
    text = DATALOG_TEMPLATE_PATH.read_text(encoding="utf-8")
    for column in REQUIRED_DATALOG_COLUMNS:
        assert column in text, f"必須列 '{column}' が無い"


# --- R-005〜R-009: doctor.sh / doctor.ps1 ---

_missing_tool = shutil.which("uv") is None or shutil.which("git") is None
_is_root = hasattr(os, "geteuid") and os.geteuid() == 0

pytestmark_doctor = pytest.mark.skipif(
    _missing_tool or _is_root,
    reason="uv/git が無い、またはroot(euid 0)実行のためchmodの権限検査が再現できない",
)


def _place_doctor_sh(sandbox_dir: Path) -> Path:
    """作業ツリーのdoctor.shをコピーし、TEMPLATE_REPOをローカル参照へ差し替える。

    verify-installers.shのplace_installersと同じ前例(出荷物本体は書き換えず、
    テスト用コピーだけを差し替える)。

    Args:
        sandbox_dir: コピー先ディレクトリ。

    Returns:
        差し替え後のdoctor.shのパス。
    """
    text = DOCTOR_SH_PATH.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r"^TEMPLATE_REPO=.*$",
        f'TEMPLATE_REPO="file://{_ROOT}"',
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        pytest.fail(
            "doctor.shのTEMPLATE_REPO行の差し替えに失敗した(行の形式が変わった可能性)"
        )
    dest = sandbox_dir / "doctor.sh"
    dest.write_text(new_text, encoding="utf-8")
    dest.chmod(0o755)
    return dest


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    return project


def _run_doctor(sandbox_doctor: Path, project_dir: Path) -> subprocess.CompletedProcess:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    return subprocess.run(
        ["bash", str(sandbox_doctor)],
        capture_output=True,
        text=True,
        cwd=project_dir,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )


def _output(result: subprocess.CompletedProcess) -> str:
    return result.stdout + result.stderr


@pytestmark_doctor
def test_doctor_raw_writable(tmp_path: Path) -> None:
    sandbox_doctor = _place_doctor_sh(tmp_path)
    project = _make_project(tmp_path)
    (project / "data" / "raw").mkdir(parents=True)
    (project / "data" / "DATA_LOG.md").write_text("dummy", encoding="utf-8")

    result = _run_doctor(sandbox_doctor, project)
    output = _output(result)
    assert result.returncode == 0
    assert _MARKER_RAW_WRITABLE in output
    assert _MARKER_PROCESSED_READONLY not in output
    assert _MARKER_LOG_MISSING not in output


@pytestmark_doctor
def test_doctor_processed_readonly(tmp_path: Path) -> None:
    sandbox_doctor = _place_doctor_sh(tmp_path)
    project = _make_project(tmp_path)
    processed = project / "data" / "processed"
    processed.mkdir(parents=True)
    (project / "data" / "DATA_LOG.md").write_text("dummy", encoding="utf-8")
    processed.chmod(0o555)

    try:
        result = _run_doctor(sandbox_doctor, project)
    finally:
        processed.chmod(0o755)

    output = _output(result)
    assert result.returncode == 0
    assert _MARKER_PROCESSED_READONLY in output
    assert _MARKER_RAW_WRITABLE not in output
    assert _MARKER_LOG_MISSING not in output


@pytestmark_doctor
def test_doctor_datalog_missing(tmp_path: Path) -> None:
    sandbox_doctor = _place_doctor_sh(tmp_path)
    project = _make_project(tmp_path)
    (project / "data").mkdir(parents=True)

    result = _run_doctor(sandbox_doctor, project)
    output = _output(result)
    assert result.returncode == 0
    assert _MARKER_LOG_MISSING in output
    assert _MARKER_RAW_WRITABLE not in output
    assert _MARKER_PROCESSED_READONLY not in output


@pytestmark_doctor
def test_doctor_no_data_dir(tmp_path: Path) -> None:
    sandbox_doctor = _place_doctor_sh(tmp_path)
    project = _make_project(tmp_path)

    result = _run_doctor(sandbox_doctor, project)
    output = _output(result)
    assert result.returncode == 0
    for marker in _ALL_MARKERS:
        assert marker not in output


@pytestmark_doctor
def test_doctor_all_markers_simultaneously(tmp_path: Path) -> None:
    # raw書き込み可 + processed書き込み不可 + DATA_LOG無し を同時に満たす
    # 組み合わせで3マーカーとも取りこぼさないことを検証する(検証方法表の要求)
    sandbox_doctor = _place_doctor_sh(tmp_path)
    project = _make_project(tmp_path)
    (project / "data" / "raw").mkdir(parents=True)
    processed = project / "data" / "processed"
    processed.mkdir(parents=True)
    processed.chmod(0o555)

    try:
        result = _run_doctor(sandbox_doctor, project)
    finally:
        processed.chmod(0o755)

    output = _output(result)
    assert result.returncode == 0
    for marker in _ALL_MARKERS:
        assert marker in output


def test_doctor_parity() -> None:
    # consistency.mdの標準形: 一意集合のdiffで1対1対応を機械検証する
    sh_markers = set(
        re.findall(r"\[DATA-[A-Z-]+\]", DOCTOR_SH_PATH.read_text(encoding="utf-8"))
    )
    ps1_markers = set(
        re.findall(r"\[DATA-[A-Z-]+\]", DOCTOR_PS1_PATH.read_text(encoding="utf-8"))
    )
    assert sh_markers == ps1_markers
    assert len(sh_markers) >= 3
    assert set(_ALL_MARKERS) <= sh_markers


# --- R-010/R-011: handoff / paper-writing チェックリスト ---


def test_handoff_checklist_seven_items() -> None:
    text = HANDOFF_SKILL_PATH.read_text(encoding="utf-8")
    for item in REQUIRED_CHECKLIST_ITEMS:
        assert item in text, f"handoffチェックリストに '{item}' が無い"


def test_paper_checklist_matches_handoff() -> None:
    handoff_text = HANDOFF_SKILL_PATH.read_text(encoding="utf-8")
    paper_text = PAPER_SKILL_PATH.read_text(encoding="utf-8")
    for item in REQUIRED_CHECKLIST_ITEMS:
        assert item in handoff_text, f"handoffチェックリストに '{item}' が無い"
        assert item in paper_text, f"paper-writingチェックリストに '{item}' が無い"


# --- R-012: README.md ---


def test_readme_data_convention() -> None:
    text = README_PATH.read_text(encoding="utf-8")
    for word in ("data/raw", "data/processed", "synthetic", "exports"):
        assert word in text, f"README.mdに '{word}' が無い"
    for step in ("chmod +w", "DATA_LOG", "chmod -w"):
        assert step in text, f"README.mdのraw更新手順に '{step}' が無い"


# --- R-013: _staging_data_protection_p1.py の冪等性 ---

pytestmark_staging = pytest.mark.skipif(
    not STAGING_PATH.exists(),
    reason="_staging_data_protection_p1.py が存在しない(未作成 or 既に削除済み)",
)


@pytestmark_staging
def test_staging_idempotent_apply_twice(tmp_path: Path) -> None:
    # 保護パス(.claude/improvements/invariants.md)は実リポジトリでは書けないため
    # --root で複製した一時ディレクトリに適用する(test_session_monitorの前例と同じ)
    root = tmp_path / "fake_root"
    improvements_dir = root / ".claude" / "improvements"
    improvements_dir.mkdir(parents=True)
    invariants_copy = improvements_dir / "invariants.md"
    invariants_copy.write_text(_invariants_text(), encoding="utf-8")

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
    }
    result1 = subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )
    assert result1.returncode == 0
    snapshot = invariants_copy.read_bytes()

    result2 = subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )
    assert result2.returncode == 0
    assert invariants_copy.read_bytes() == snapshot
    assert "SKIP" in (result2.stdout + result2.stderr)
