"""record_session_state.py(Stop)の鮮度警告(state ファイル)受け入れテスト。

対象: `.claude/plans/20260904-skill-state.md` の PC-11。
設計書: `docs/active/20260904-skill-state-spec.md` R-011
(`updated_at` が30分より古いなら警告、30分以内では警告なし。
ちょうど30分は「より古い」に該当しないため警告なし: premortem LOW反映)。

naive(`2026-09-04T10:00:00`)/ aware(`+09:00` 付き)の両形式を検査する。
片方だけだと naive/aware 比較で `TypeError` になり、fail-open に飲まれて
警告が永久に出ない事故を検出できない。

書式は `tests/test_session_resume.py` に倣う。Step 5(`_staging_skill_state.py`
によるユーザー適用)より前は鮮度警告が未実装のため FAIL するのが正しい状態(RED)。
"""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
RECORD_PATH = HOOKS_DIR / "record_session_state.py"

_SUBPROCESS_TIMEOUT = 15
BRANCH = "pipeline/20260904-skill-state"
SLUG = "20260904-skill-state"
_AWARE_TZ = timezone(timedelta(hours=9))


def _init_repo(tmp_path: Path, branch: str = BRANCH) -> None:
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
            timeout=_SUBPROCESS_TIMEOUT,
        )
    (tmp_path / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def _iso_minutes_ago(minutes: float, aware: bool) -> str:
    if aware:
        dt = datetime.now(_AWARE_TZ) - timedelta(minutes=minutes)
    else:
        dt = datetime.now() - timedelta(minutes=minutes)
    return dt.isoformat()


def _write_state_file(tmp_path: Path, updated_at: str) -> None:
    state_dir = tmp_path / ".claude" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{SLUG}.json").write_text(
        json.dumps({"updated_at": updated_at}, ensure_ascii=False), encoding="utf-8"
    )


def _load_module(path: Path, name: str) -> ModuleType:
    """指定パスの `.py` をモジュールとして直接読み込む(境界テストで `datetime` を
    差し替えるための直接呼び出し用。`tests/test_session_resume.py` の
    `_load_module` と同じ方式)。
    """
    hooks_dir = str(path.parent)
    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_record(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    stdin = json.dumps({"transcript_path": ""})
    return subprocess.run(
        [sys.executable, str(RECORD_PATH)],
        cwd=str(tmp_path),
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )


@pytest.mark.parametrize("aware", [False, True], ids=["naive", "aware"])
def test_freshness_31_minutes_warns(tmp_path: Path, aware: bool) -> None:
    _init_repo(tmp_path)
    _write_state_file(tmp_path, _iso_minutes_ago(31, aware))

    result = _run_record(tmp_path)

    assert result.returncode == 0
    assert "systemMessage" in result.stdout
    assert "30分" in result.stdout or "30分" in result.stderr


@pytest.mark.parametrize("aware", [False, True], ids=["naive", "aware"])
def test_freshness_29_minutes_no_warning(tmp_path: Path, aware: bool) -> None:
    _init_repo(tmp_path)
    _write_state_file(tmp_path, _iso_minutes_ago(29, aware))

    result = _run_record(tmp_path)

    assert result.returncode == 0
    assert "systemMessage" not in result.stdout


def test_freshness_exactly_30_minutes_no_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """境界: ちょうど30分は「30分より古い」に該当しないため警告なし(premortem LOW反映)。

    サブプロセス経由の実時計では、テストが `updated_at` を組み立ててから
    フックが `datetime.now()` を評価するまでの実行遅延ぶん、実際の経過時間が
    常にちょうど30分をわずかに超えてしまい、この境界(30分ちょうどは警告なし)を
    検証できない(常に「31分」側に倒れて誤って FAIL する設計ミス)。
    そのため record_session_state モジュールを直接ロードし、モジュール内の
    `datetime` を固定時刻のダミーに差し替えて、経過時間をちょうど30.0分に固定する。
    """
    monkeypatch.chdir(tmp_path)
    # ブランチは _freshness_warning に直接渡すため git 初期化は不要
    record = _load_module(RECORD_PATH, "record_session_state")

    fixed_now = datetime(2026, 9, 4, 11, 0, 0)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now.astimezone(tz) if tz is not None else fixed_now

    record.datetime = _FrozenDatetime
    _write_state_file(tmp_path, (fixed_now - timedelta(minutes=30)).isoformat())

    assert record._freshness_warning(BRANCH) is None


def test_freshness_no_state_file_no_warning(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # 状態ファイルを作らない

    result = _run_record(tmp_path)

    assert result.returncode == 0
    assert "systemMessage" not in result.stdout
