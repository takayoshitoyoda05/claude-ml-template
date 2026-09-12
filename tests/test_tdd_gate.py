"""tdd テスト改変ゲート(CLAUDE_TDD_GATE)の受け入れテスト。

対象: `.claude/plans/20260911-tdd-gate.md` の PC-1〜PC-30。
設計書: `docs/active/tdd-gate-spec.md`(R-001〜R-021)。
ADR: `docs/adr/0006-tdd-gate-design.md`。

フックの取得は2経路(設計判断表・実装手順 Step 1):
  (1) `_staging_tdd_gate.py`(gitignore 対象)があれば `--root` でサンドボックスへ適用
  (2) 無ければ追跡済みの `.claude/hooks/tdd_*.py` をサンドボックスへ写す
どちらも無ければ skip ではなく FAIL する(PC-28。クリーン clone での偽陰性防止)。
`sandbox` フィクスチャは2経路を `["staging", "tracked"]` でパラメトライズし、
利用できない経路だけを個別に skip する(PC-27: 両経路で同じ結果になることを
共有テストの実行そのもので担保する)。

書式は `tests/test_codex_gate.py`(`--root` サンドボックス適用 + subprocess 検証)・
`tests/test_state_gate.py`(`sys.executable` + `_SUBPROCESS_TIMEOUT` + cwd 指定 CLI 起動)
に倣う。

Step 1 時点では PC-16(template/README)・PC-17(SKILL.md)・PC-30(CI workflow)は
並列実装の他グループ(B・C・D)が担当するファイルを検査するため、本ファイル単体では
FAIL(RED)のままになる(計画の検証方法表に明記済み)。PC-18(verify-hooks マーカー
1対1対応)は Step 5(本グループ)で GREEN になる。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING_PATH = REPO_ROOT / "_staging_tdd_gate.py"
TRACKED_HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

_SUBPROCESS_TIMEOUT = 30

# staging も追跡済みフックも無い環境(クリーン checkout かつ未適用)では、
# 本ファイルの大半のテストは実行不能になる。skip にすると「全件 skip で
# 失敗0」という偽陰性が起きるため、そういう環境が実在することを示す
# 番人テスト(PC-28)を別途置く。
pytestmark_staging = pytest.mark.skipif(
    not STAGING_PATH.exists(),
    reason="_staging_tdd_gate.py が無い環境(クリーン checkout / CI)ではスキップ",
)


# --------------------------------------------------------------------------
# フック取得(2経路)
# --------------------------------------------------------------------------


def _obtain_hooks_dir(dest: Path, staging_path: Path, tracked_hooks_dir: Path) -> Path:
    """2経路でフックをサンドボックスに用意し、`.claude/hooks/` を返す。

    どちらの経路も使えなければ skip ではなく FAIL する(PC-28)。
    """
    dest.mkdir(parents=True, exist_ok=True)
    hooks_dir = dest / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (dest / ".claude" / "checkpoints").mkdir(parents=True, exist_ok=True)

    if staging_path.exists():
        result = subprocess.run(
            [sys.executable, str(staging_path), "--root", str(dest), "--hooks-only"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        return hooks_dir

    tracked_gate = tracked_hooks_dir / "tdd_gate.py"
    if tracked_gate.exists():
        for name in ("tdd_red.py", "tdd_gate.py", "tdd_unlock.py"):
            shutil.copy(tracked_hooks_dir / name, hooks_dir / name)
        return hooks_dir

    pytest.fail(
        "tdd_gate.py が _staging_tdd_gate.py にも追跡済み .claude/hooks/ にも"
        "見つかりません(クリーン環境での偽陰性防止の番人。PC-28)。"
    )


def test_pc28_guardian_fails_when_neither_source_available(tmp_path: Path) -> None:
    """PC-28: staging も追跡済み tdd_gate.py も無ければ skip ではなく FAIL する。"""
    with pytest.raises(pytest.fail.Exception):
        _obtain_hooks_dir(
            tmp_path / "dest",
            staging_path=tmp_path / "no_staging.py",
            tracked_hooks_dir=tmp_path / "no_hooks_dir",
        )


def test_pc28_guardian_real_checkout_has_at_least_one_source() -> None:
    """PC-28(実環境番人): 実チェックアウトの STAGING_PATH / TRACKED_HOOKS_DIR の

    少なくとも一方が存在することを検査する。偽パスだけを検査する上のテストでは
    クリーン checkout(staging 退避)で全 skip が起きる偽陰性を検知できないため、
    実パスを直接検査する(レビュー指摘: PC-28 番人の無効化)。
    """
    if not (STAGING_PATH.exists() or (TRACKED_HOOKS_DIR / "tdd_gate.py").exists()):
        pytest.fail(
            "_staging_tdd_gate.py も追跡済み .claude/hooks/tdd_gate.py も"
            "見つかりません(実チェックアウトでの偽陰性防止の番人。PC-28)。"
        )


def _seed_repo_files(root: Path) -> None:
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "tests" / "test_x.py").write_text(
        "def test_x():\n    assert False\n", encoding="utf-8"
    )
    (root / "tests" / "test_y.py").write_text(
        "def test_y():\n    assert True\n", encoding="utf-8"
    )
    (root / "src" / "train.py").write_text("x = 1\n", encoding="utf-8")


@pytest.fixture(params=["staging", "tracked"])
def sandbox(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    """2経路でフックを配置したサンドボックスのルートを返す(PC-27)。

    利用できない経路はこのフィクスチャ内で skip する(staging 固有テストは
    別途 `pytestmark_staging` を使うので、ここでの skip 対象は「共有 PC を
    tracked 経路で検証したいが、まだ staging が適用・コミットされておらず
    追跡済みフックが存在しない」場合に限られる)。
    """
    route = request.param
    dest = tmp_path / "sandbox"
    if route == "staging":
        if not STAGING_PATH.exists():
            pytest.skip("_staging_tdd_gate.py が無い環境ではスキップ")
        _obtain_hooks_dir(dest, STAGING_PATH, tmp_path / "__no_tracked__.py")
    else:
        if not (TRACKED_HOOKS_DIR / "tdd_gate.py").exists():
            pytest.skip(
                "追跡済み .claude/hooks/tdd_gate.py が無い環境ではスキップ"
                "(staging が未適用・未コミット)"
            )
        _obtain_hooks_dir(dest, tmp_path / "__no_staging__.py", TRACKED_HOOKS_DIR)
    _seed_repo_files(dest)
    return dest


# --------------------------------------------------------------------------
# 実行ヘルパー
# --------------------------------------------------------------------------


def sentinel_path(sandbox: Path) -> Path:
    return sandbox / ".claude" / "checkpoints" / "tdd_red.json"


def blocks_log_path(sandbox: Path) -> Path:
    return sandbox / ".claude" / "checkpoints" / "tdd_gate_blocks.log"


def _base_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    if extra:
        env.update(extra)
    return env


def run_red(
    sandbox: Path, args: list[str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    hook = sandbox / ".claude" / "hooks" / "tdd_red.py"
    return subprocess.run(
        [sys.executable, str(hook), *args],
        cwd=str(cwd or sandbox),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=_base_env(),
    )


def run_unlock(
    sandbox: Path, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    hook = sandbox / ".claude" / "hooks" / "tdd_unlock.py"
    return subprocess.run(
        [sys.executable, str(hook)],
        cwd=str(cwd or sandbox),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=_base_env(),
    )


def run_gate(
    sandbox: Path,
    tool_input: dict[str, str] | None,
    cwd: Path | None = None,
    gate_env: str | None = "1",
    stdin_override: str | None = None,
) -> subprocess.CompletedProcess[str]:
    hook = sandbox / ".claude" / "hooks" / "tdd_gate.py"
    payload_cwd = str(cwd or sandbox)
    if stdin_override is not None:
        stdin_text = stdin_override
    else:
        payload: dict[str, object] = {"cwd": payload_cwd}
        if tool_input is not None:
            payload["tool_input"] = tool_input
        stdin_text = json.dumps(payload)
    env = _base_env({"CLAUDE_TDD_GATE": gate_env} if gate_env is not None else None)
    return subprocess.run(
        [sys.executable, str(hook)],
        cwd=str(cwd or sandbox),
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
        env=env,
    )


def record_red(
    sandbox: Path, files: list[str], cmd: str = 'python3 -c "import sys; sys.exit(1)"'
) -> subprocess.CompletedProcess[str]:
    return run_red(sandbox, ["--cmd", cmd, "--files", *files])


# --------------------------------------------------------------------------
# tdd_red.py: 記録(PC-1〜PC-4)
# --------------------------------------------------------------------------


def test_pc1_red_records_sentinel_and_failure_log(sandbox: Path) -> None:
    """PC-1: 失敗するコマンドで記録すると、必須5キーを持つセンチネルと失敗ログができる。"""
    result = record_red(sandbox, ["tests/test_x.py"])
    assert result.returncode == 0, result.stderr

    sentinel = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))
    assert set(sentinel.keys()) == {
        "test_command",
        "test_files",
        "recorded_cwd",
        "recorded_at",
        "log_path",
    }
    assert isinstance(sentinel["test_files"], list)
    assert len(sentinel["test_files"]) == 1
    assert os.path.isabs(sentinel["test_files"][0])
    assert os.path.isabs(sentinel["recorded_cwd"])
    assert isinstance(sentinel["recorded_at"], str) and sentinel["recorded_at"]

    log_path = Path(sentinel["log_path"])
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "stdout" in log_text
    assert "stderr" in log_text


def test_pc2_red_rerecord_overwrites_single_sentinel(sandbox: Path) -> None:
    """PC-2: 別ファイルで再実行すると、センチネルは1つのまま新しい指定で上書きされる。"""
    record_red(sandbox, ["tests/test_x.py"])
    first = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))

    result = record_red(sandbox, ["tests/test_y.py"])
    assert result.returncode == 0, result.stderr
    second = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))

    assert second["test_files"] != first["test_files"]
    assert len(second["test_files"]) == 1
    assert second["test_files"][0].endswith("test_y.py")


def test_pc3_red_refuses_already_green(sandbox: Path) -> None:
    """PC-3: 既に緑のコマンドではセンチネルを作らず非0終了し、既存内容も変えない。"""
    record_red(sandbox, ["tests/test_x.py"])
    before = sentinel_path(sandbox).read_text(encoding="utf-8")

    result = run_red(
        sandbox,
        ["--cmd", 'python3 -c "import sys; sys.exit(0)"', "--files", "tests/test_x.py"],
    )
    assert result.returncode != 0
    assert "緑" in result.stderr
    after = sentinel_path(sandbox).read_text(encoding="utf-8")
    assert after == before


def test_pc4_red_requires_files(sandbox: Path) -> None:
    """PC-4: --files 省略/空なら非0終了しセンチネルを作らない。"""
    result = run_red(sandbox, ["--cmd", 'python3 -c "import sys; sys.exit(1)"'])
    assert result.returncode != 0
    assert not sentinel_path(sandbox).exists()


# --------------------------------------------------------------------------
# tdd_gate.py: ブロック判定(PC-5〜PC-11)
# --------------------------------------------------------------------------


def test_pc5_gate_blocks_recorded_test_file(sandbox: Path) -> None:
    """PC-5: 記録済みテストファイルの編集はブロックされ、3つの脱出路を案内する。"""
    record_red(sandbox, ["tests/test_x.py"])
    result = run_gate(sandbox, {"file_path": "tests/test_x.py"})
    assert result.returncode == 2
    assert "tdd_unlock.py" in result.stderr
    assert "tdd_red.py --rearm" in result.stderr
    assert "CLAUDE_TDD_GATE=0" in result.stderr


def test_pc6_gate_no_overblocking(sandbox: Path) -> None:
    """PC-6: 無関係ソース・記録に無いテスト・malformed 入力は通し、notebook は対象にする。"""
    record_red(sandbox, ["tests/test_x.py"])

    unrelated_source = run_gate(sandbox, {"file_path": "src/train.py"})
    assert unrelated_source.returncode == 0

    unrelated_test = run_gate(sandbox, {"file_path": "tests/test_y.py"})
    assert unrelated_test.returncode == 0

    notebook_recorded = run_gate(sandbox, {"notebook_path": "tests/test_x.py"})
    assert notebook_recorded.returncode == 2

    malformed = run_gate(sandbox, tool_input=None, stdin_override="not json")
    assert malformed.returncode == 0

    # PC-6(d)相当: file_path が非文字列(int)でも例外で落ちず exit 0(対象なし扱い)
    nonstring_path = run_gate(sandbox, {"file_path": 12345})
    assert nonstring_path.returncode == 0
    assert "Traceback" not in nonstring_path.stderr


def test_pc7_gate_path_identity(sandbox: Path) -> None:
    """PC-7: 実体が同一なら絶対/相対/symlink/冗長表記のいずれでも判定不変。

    名前が前方一致するだけの別ファイルは通す(prefix 一致バグの回帰防止)。
    """
    record_red(sandbox, ["tests/test_x.py"])
    real_target = (sandbox / "tests" / "test_x.py").resolve()

    link_dir = sandbox / "tests_link"
    link_dir.symlink_to(sandbox / "tests", target_is_directory=True)
    try:
        variants = [
            str(real_target),
            "tests/test_x.py",
            "tests_link/test_x.py",
            "./tests/../tests/test_x.py",
        ]
        for variant in variants:
            result = run_gate(sandbox, {"file_path": variant})
            assert result.returncode == 2, (variant, result.stderr)
    finally:
        link_dir.unlink()

    (sandbox / "tests" / "test_x_extra.py").write_text(
        "def test_extra():\n    pass\n", encoding="utf-8"
    )
    prefix_similar = run_gate(sandbox, {"file_path": "tests/test_x_extra.py"})
    assert prefix_similar.returncode == 0


def test_pc8_gate_off_always_passes(sandbox: Path) -> None:
    """PC-8: CLAUDE_TDD_GATE が 1 以外(未設定/0/true/空)なら常に素通りし stderr は空。"""
    record_red(sandbox, ["tests/test_x.py"])
    for env_value in (None, "0", "true", ""):
        result = run_gate(sandbox, {"file_path": "tests/test_x.py"}, gate_env=env_value)
        assert result.returncode == 0, (env_value, result.stderr)
        assert result.stderr == ""


def test_pc9_gate_passes_without_sentinel(sandbox: Path) -> None:
    """PC-9: センチネルが存在しなければ常に素通り。"""
    result = run_gate(sandbox, {"file_path": "tests/test_x.py"})
    assert result.returncode == 0


_BROKEN_SENTINEL_STATES: dict[str, str] = {
    "invalid_json": "{not json",
    "empty_file": "",
    "missing_test_files": json.dumps(
        {
            "test_command": "x",
            "recorded_cwd": "/tmp",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "empty_test_files": json.dumps(
        {
            "test_command": "x",
            "test_files": [],
            "recorded_cwd": "/tmp",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "test_files_not_array": json.dumps(
        {
            "test_command": "x",
            "test_files": "notalist",
            "recorded_cwd": "/tmp",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "test_files_nonstring_element": json.dumps(
        {
            "test_command": "x",
            "test_files": [1],
            "recorded_cwd": "/tmp",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "missing_recorded_cwd": json.dumps(
        {
            "test_command": "x",
            "test_files": ["a"],
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "relative_recorded_cwd": json.dumps(
        {
            "test_command": "x",
            "test_files": ["a"],
            "recorded_cwd": "relative/dir",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "test_files_relative_element": json.dumps(
        {
            "test_command": "x",
            "test_files": ["relative/dir/test_x.py"],
            "recorded_cwd": "/tmp",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
    "empty_test_command": json.dumps(
        {
            "test_command": "   ",
            "test_files": ["/tmp/test_x.py"],
            "recorded_cwd": "/tmp",
            "recorded_at": "now",
            "log_path": "x",
        }
    ),
}

_GATE_INPUTS: list[dict[str, str]] = [
    {"file_path": "src/train.py"},
    {"file_path": "tests/test_y.py"},
    {"notebook_path": "tests/test_x.py"},
]


@pytest.mark.parametrize("state_label", sorted(_BROKEN_SENTINEL_STATES))
def test_pc10_gate_broken_sentinel_is_fail_closed(
    sandbox: Path, state_label: str
) -> None:
    """PC-10: 壊れたセンチネルの10状態は、どの入力でも exit 2(全編集ブロック)。

    traceback を出さず、脱出路(tdd_red.py --rearm 等)を案内する。
    """
    sentinel_path(sandbox).write_text(
        _BROKEN_SENTINEL_STATES[state_label], encoding="utf-8"
    )
    for tool_input in _GATE_INPUTS:
        result = run_gate(sandbox, tool_input)
        assert result.returncode == 2, (state_label, tool_input, result.stderr)
        assert "Traceback" not in result.stderr
        assert "全編集を停止中" in result.stderr


def test_pc11_gate_blocks_log_increments_only_on_block(sandbox: Path) -> None:
    """PC-11: ブロック1回につき blocks.log が+1行。素通りでは増えない。行に日時・対象パスを含む。"""
    record_red(sandbox, ["tests/test_x.py"])
    log = blocks_log_path(sandbox)
    before_lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    run_gate(sandbox, {"file_path": "tests/test_x.py"})  # block
    run_gate(sandbox, {"file_path": "tests/test_x.py"})  # block
    run_gate(sandbox, {"file_path": "src/train.py"})  # pass-through

    after_lines = log.read_text(encoding="utf-8").splitlines()
    assert len(after_lines) == len(before_lines) + 2
    for line in after_lines[len(before_lines) :]:
        assert re.search(r"\d{4}-\d{2}-\d{2}", line)
        assert "tests/test_x.py" in line


def test_pc25_broken_sentinel_blocks_are_logged(sandbox: Path) -> None:
    """PC-25: 壊れたセンチネルによる fail-closed ブロックも1回につき+1行、理由が判別できる。"""
    log = blocks_log_path(sandbox)
    for state_label, content in _BROKEN_SENTINEL_STATES.items():
        sentinel_path(sandbox).write_text(content, encoding="utf-8")
        for tool_input in _GATE_INPUTS:
            before_lines = (
                log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            )
            result = run_gate(sandbox, tool_input)
            assert result.returncode == 2
            after_lines = log.read_text(encoding="utf-8").splitlines()
            assert len(after_lines) == len(before_lines) + 1, state_label
            assert "fail-closed" in after_lines[-1]


# --------------------------------------------------------------------------
# tdd_unlock.py: 検証つき解除(PC-12・PC-21)
# --------------------------------------------------------------------------


def test_pc12_unlock_requires_green(sandbox: Path) -> None:
    """PC-12: 赤のままでは非0終了しセンチネルを保持、緑になれば解除する。"""
    record_red(sandbox, ["tests/test_x.py"])

    still_red = run_unlock(sandbox)
    assert still_red.returncode != 0
    assert sentinel_path(sandbox).exists()

    sentinel = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))
    sentinel["test_command"] = 'python3 -c "import sys; sys.exit(0)"'
    sentinel_path(sandbox).write_text(json.dumps(sentinel), encoding="utf-8")

    now_green = run_unlock(sandbox)
    assert now_green.returncode == 0, now_green.stderr
    assert not sentinel_path(sandbox).exists()


def test_pc12_unlock_toctou_preserves_reappeared_sentinel(sandbox: Path) -> None:
    """R-011 TOCTOU: テストコマンド実行中に別プロセスがセンチネルを再記録したら、

    unlock はそれを削除せず非0終了する(実行前に読んだバイト列と、成功後の
    再読込を比較し、一致する場合のみ削除する。レビュー指摘: TOCTOU で
    実行中の Red 再記録が消される)。

    記録コマンドは、記録時(1回目の呼び出し)は非0で終わり、unlock の再実行
    (2回目の呼び出し)では2秒かけて緑になるよう、マーカーファイルで呼び出し回数を
    区別する(tdd_red.py は記録時に一度コマンドを実行して赤を確認するため)。
    """
    (sandbox / "_toctou_cmd.py").write_text(
        "import os, sys, time\n"
        "marker = '_toctou_marker'\n"
        "if not os.path.exists(marker):\n"
        "    open(marker, 'w').close()\n"
        "    sys.exit(1)\n"
        "time.sleep(2)\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    record_red(sandbox, ["tests/test_x.py"], cmd="python3 _toctou_cmd.py")
    hook = sandbox / ".claude" / "hooks" / "tdd_unlock.py"
    proc = subprocess.Popen(
        [sys.executable, str(hook)],
        cwd=str(sandbox),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_base_env(),
    )
    time.sleep(0.5)
    reappeared = json.dumps(
        {
            "test_command": 'python3 -c "import sys; sys.exit(1)"',
            "test_files": [str((sandbox / "tests" / "test_y.py").resolve())],
            "recorded_cwd": str(sandbox.resolve()),
            "recorded_at": "later",
            "log_path": "x",
        }
    )
    sentinel_path(sandbox).write_text(reappeared, encoding="utf-8")
    _, stderr = proc.communicate(timeout=_SUBPROCESS_TIMEOUT)

    assert proc.returncode != 0
    assert sentinel_path(sandbox).read_text(encoding="utf-8") == reappeared
    assert "再記録" in stderr


def test_pc21_unlock_preserves_recorded_cwd(sandbox: Path) -> None:
    """PC-21: 解除は記録された cwd で再実行され、起動位置で結果が変わらない。

    recorded_cwd が消えている/相対パスに書き換えられている場合はコマンドを
    実行せず非0終了でセンチネルを保持する(スキーマ検証の代表2ケース)。
    """
    sub = sandbox / "sub"
    (sub / "tests").mkdir(parents=True)
    (sub / "tests" / "test_rel.py").write_text(
        "def test_rel():\n    assert False\n", encoding="utf-8"
    )
    check_cmd = (
        'python3 -c "import os,sys; '
        "sys.exit(0 if os.path.basename(os.getcwd())=='sub' else 1)\""
    )

    # (a) リポジトリルートから解除
    record_red(
        sandbox, ["tests/test_rel.py"], cmd='python3 -c "import sys; sys.exit(1)"'
    )
    # tdd_red.py の cwd はサンドボックスルートなので、sub 基準で記録し直す
    r = run_red(
        sandbox,
        [
            "--cmd",
            'python3 -c "import sys; sys.exit(1)"',
            "--files",
            "tests/test_rel.py",
        ],
        cwd=sub,
    )
    assert r.returncode == 0, r.stderr
    sentinel = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))
    assert sentinel["recorded_cwd"] == str(sub.resolve())
    sentinel["test_command"] = check_cmd
    sentinel_path(sandbox).write_text(json.dumps(sentinel), encoding="utf-8")
    result_a = run_unlock(sandbox, cwd=sandbox)
    assert result_a.returncode == 0, result_a.stderr
    assert not sentinel_path(sandbox).exists()

    # (b) 別のサブディレクトリから解除
    other = sandbox / "other"
    other.mkdir()
    r = run_red(
        sandbox,
        [
            "--cmd",
            'python3 -c "import sys; sys.exit(1)"',
            "--files",
            "tests/test_rel.py",
        ],
        cwd=sub,
    )
    assert r.returncode == 0, r.stderr
    sentinel = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))
    sentinel["test_command"] = check_cmd
    sentinel_path(sandbox).write_text(json.dumps(sentinel), encoding="utf-8")
    result_b = run_unlock(sandbox, cwd=other)
    assert result_b.returncode == 0, result_b.stderr
    assert not sentinel_path(sandbox).exists()

    # (c) recorded_cwd を削除してから解除: コマンドを実行せず非0・センチネル保持
    r = run_red(
        sandbox,
        [
            "--cmd",
            'python3 -c "import sys; sys.exit(1)"',
            "--files",
            "tests/test_rel.py",
        ],
        cwd=sub,
    )
    assert r.returncode == 0, r.stderr
    shutil.rmtree(sub)
    result_c = run_unlock(sandbox, cwd=sandbox)
    assert result_c.returncode != 0
    assert sentinel_path(sandbox).exists()

    # (d) recorded_cwd を相対パスに書き換えてから解除: コマンドを実行せず非0・センチネル保持
    sentinel = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))
    sentinel["recorded_cwd"] = "relative/path"
    sentinel_path(sandbox).write_text(json.dumps(sentinel), encoding="utf-8")
    result_d = run_unlock(sandbox, cwd=sandbox)
    assert result_d.returncode != 0
    assert sentinel_path(sandbox).exists()


@pytest.mark.parametrize("state_label", sorted(_BROKEN_SENTINEL_STATES))
def test_pc21_unlock_broken_sentinel_does_not_execute_command(
    sandbox: Path, state_label: str
) -> None:
    """PC-21(補足): unlock も PC-10 と同じ10状態でコマンド未実行・非0・センチネル保持。"""
    content = _BROKEN_SENTINEL_STATES[state_label]
    sentinel_path(sandbox).write_text(content, encoding="utf-8")
    result = run_unlock(sandbox)
    assert result.returncode != 0
    assert sentinel_path(sandbox).exists()
    assert sentinel_path(sandbox).read_text(encoding="utf-8") == content


# --------------------------------------------------------------------------
# tdd_red.py --rearm(PC-13)
# --------------------------------------------------------------------------


def test_pc13_rearm_deletes_sentinel_and_logs(sandbox: Path) -> None:
    """PC-13: --rearm はセンチネルを削除し blocks.log に rearm を1行追記する。

    センチネル不在での --rearm は非0終了で blocks.log を増やさない。
    """
    record_red(sandbox, ["tests/test_x.py"])
    log = blocks_log_path(sandbox)
    before = log.read_text(encoding="utf-8").splitlines() if log.exists() else []

    result = run_red(sandbox, ["--rearm"])
    assert result.returncode == 0, result.stderr
    assert not sentinel_path(sandbox).exists()

    after = log.read_text(encoding="utf-8").splitlines()
    assert len(after) == len(before) + 1
    assert "rearm" in after[-1]

    before2 = log.read_text(encoding="utf-8")
    result2 = run_red(sandbox, ["--rearm"])
    assert result2.returncode != 0
    after2 = log.read_text(encoding="utf-8")
    assert after2 == before2


# --------------------------------------------------------------------------
# 静的検査・起動位置の不変性(PC-20・PC-22)
# --------------------------------------------------------------------------


def test_pc20_static_contracts(sandbox: Path) -> None:
    """PC-20: tdd_gate.py に subprocess 呼び出しが無く、tdd_red/unlock は
    timeout 指定つき subprocess.run と正しい例外捕捉を持つ。3本とも
    standalone のパス正規化関数を定義する。
    """
    hooks_dir = sandbox / ".claude" / "hooks"
    gate_src = (hooks_dir / "tdd_gate.py").read_text(encoding="utf-8")
    red_src = (hooks_dir / "tdd_red.py").read_text(encoding="utf-8")
    unlock_src = (hooks_dir / "tdd_unlock.py").read_text(encoding="utf-8")

    assert "subprocess" not in gate_src

    for src in (red_src, unlock_src):
        assert "timeout=" in src
        assert "except (OSError, subprocess.TimeoutExpired, UnicodeError)" in src

    for src in (gate_src, red_src, unlock_src):
        assert 'os.name == "nt"' in src
        assert "_path_for_match" in src


def test_pc22_invocation_from_subdirectory_uses_same_sentinel(sandbox: Path) -> None:
    """PC-22: サブディレクトリから起動しても3本ともリポジトリルート直下の
    同一センチネル・同一 blocks.log を読み書きし、サブディレクトリ配下に
    .claude/checkpoints/ を新規作成しない。
    """
    subdir = sandbox / "src"

    r = run_red(
        sandbox,
        [
            "--cmd",
            'python3 -c "import sys; sys.exit(1)"',
            "--files",
            "../tests/test_x.py",
        ],
        cwd=subdir,
    )
    assert r.returncode == 0, r.stderr
    assert sentinel_path(sandbox).exists()
    assert not (subdir / ".claude").exists()

    result = run_gate(
        sandbox,
        {"file_path": str((sandbox / "tests" / "test_x.py").resolve())},
        cwd=subdir,
    )
    assert result.returncode == 2, result.stderr
    assert not (subdir / ".claude").exists()

    sentinel = json.loads(sentinel_path(sandbox).read_text(encoding="utf-8"))
    sentinel["test_command"] = 'python3 -c "import sys; sys.exit(0)"'
    sentinel_path(sandbox).write_text(json.dumps(sentinel), encoding="utf-8")
    unlock_result = run_unlock(sandbox, cwd=subdir)
    assert unlock_result.returncode == 0, unlock_result.stderr
    assert not sentinel_path(sandbox).exists()
    assert not (subdir / ".claude").exists()


# --------------------------------------------------------------------------
# staging 固有(PC-14・PC-15・PC-23・PC-24・PC-26・PC-29)
# --------------------------------------------------------------------------


def _tree_manifest(root: Path) -> dict[str, tuple]:
    manifest: dict[str, tuple] = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            manifest[rel] = ("symlink", os.readlink(path))
        elif path.is_dir():
            manifest[rel] = ("dir", None)
        elif path.is_file():
            manifest[rel] = (
                "file",
                hashlib.sha256(path.read_bytes()).hexdigest(),
                oct(path.stat().st_mode),
            )
    return manifest


def _sandbox_with_real_settings(tmp_path: Path) -> Path:
    root = tmp_path / "stage_sandbox"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / ".claude" / "checkpoints").mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / ".claude" / "settings.json", root / ".claude" / "settings.json"
    )
    return root


def _apply_staging_cli(
    root: Path, extra_args: list[str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STAGING_PATH), "--root", str(root), *(extra_args or [])],
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytestmark_staging
def test_pc14_staging_registers_tdd_gate_in_order(tmp_path: Path) -> None:
    """PC-14: 適用後、PreToolUse(Edit|Write|NotebookEdit) が4要素になり、
    guard_scope → requirements_gate → state_gate → tdd_gate の順になる。
    他 matcher の hooks 配列は変化しない。
    """
    root = _sandbox_with_real_settings(tmp_path)
    before = json.loads(
        (root / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    other_before = {
        e["matcher"]: e["hooks"]
        for e in before["hooks"]["PreToolUse"]
        if e.get("matcher") != "Edit|Write|NotebookEdit"
    }

    result = _apply_staging_cli(root)
    assert result.returncode == 0, result.stderr

    after = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entry = next(
        e
        for e in after["hooks"]["PreToolUse"]
        if e.get("matcher") == "Edit|Write|NotebookEdit"
    )
    commands = [h["command"] for h in entry["hooks"]]
    assert len(commands) == 4
    assert [c.split("/")[-1] for c in commands] == [
        "guard_scope.py",
        "requirements_gate.py",
        "state_gate.py",
        "tdd_gate.py",
    ]
    assert sum(c.endswith("/tdd_gate.py") for c in commands) == 1

    other_after = {
        e["matcher"]: e["hooks"]
        for e in after["hooks"]["PreToolUse"]
        if e.get("matcher") != "Edit|Write|NotebookEdit"
    }
    assert other_after == other_before


@pytestmark_staging
def test_pc15_staging_idempotent_apply_twice(tmp_path: Path) -> None:
    """PC-15: 2回適用してもバイト一致・exit 0。hooks 3本の inode/mtime も不変。"""
    root = _sandbox_with_real_settings(tmp_path)
    first = _apply_staging_cli(root)
    assert first.returncode == 0, first.stderr

    hooks_dir = root / ".claude" / "hooks"
    names = ("tdd_red.py", "tdd_gate.py", "tdd_unlock.py")
    stat_before = {n: (hooks_dir / n).stat() for n in names}
    bytes_before = {n: (hooks_dir / n).read_bytes() for n in names}
    settings_before = (root / ".claude" / "settings.json").read_bytes()

    second = _apply_staging_cli(root)
    assert second.returncode == 0, second.stderr

    stat_after = {n: (hooks_dir / n).stat() for n in names}
    bytes_after = {n: (hooks_dir / n).read_bytes() for n in names}
    settings_after = (root / ".claude" / "settings.json").read_bytes()

    assert settings_before == settings_after
    for n in names:
        assert bytes_before[n] == bytes_after[n]
        assert stat_before[n].st_ino == stat_after[n].st_ino
        assert stat_before[n].st_mtime == stat_after[n].st_mtime


@pytestmark_staging
@pytest.mark.parametrize(
    "mutator,label",
    [
        (
            lambda data: data["hooks"]["PreToolUse"].append(
                next(
                    e
                    for e in data["hooks"]["PreToolUse"]
                    if e.get("matcher") == "Edit|Write|NotebookEdit"
                )
            ),
            "non_unique_matcher",
        ),
        (
            lambda data: data["hooks"].__setitem__(
                "PreToolUse",
                [
                    e
                    for e in data["hooks"]["PreToolUse"]
                    if e.get("matcher") != "Edit|Write|NotebookEdit"
                ],
            ),
            "matcher_absent",
        ),
        (
            lambda data: [
                e.__setitem__("hooks", "notalist")
                for e in data["hooks"]["PreToolUse"]
                if e.get("matcher") == "Edit|Write|NotebookEdit"
            ],
            "hooks_not_array",
        ),
    ],
)
def test_pc23_pc24_staging_rejects_ambiguous_settings(
    tmp_path: Path, mutator, label: str
) -> None:
    """PC-23/24: 前検証に失敗する3種の壊れた settings.json は非0終了・変更なし。"""
    root = _sandbox_with_real_settings(tmp_path)
    settings_path = root / ".claude" / "settings.json"
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    mutator(data)
    settings_path.write_text(json.dumps(data), encoding="utf-8")

    before = _tree_manifest(root)
    result = _apply_staging_cli(root)
    after = _tree_manifest(root)

    assert result.returncode != 0, label
    assert before == after, label


@pytestmark_staging
def test_pc23_pc24_staging_rejects_invalid_json(tmp_path: Path) -> None:
    """PC-23/24 (d): settings.json が不正 JSON なら非0終了・変更なし。"""
    root = _sandbox_with_real_settings(tmp_path)
    (root / ".claude" / "settings.json").write_text("{not json", encoding="utf-8")

    before = _tree_manifest(root)
    result = _apply_staging_cli(root)
    after = _tree_manifest(root)

    assert result.returncode != 0
    assert before == after


@pytestmark_staging
def test_pc23_pc24_staging_rejects_missing_settings_without_flag(
    tmp_path: Path,
) -> None:
    """PC-23/24 (e): settings.json 不在で --hooks-only 未指定なら非0終了・変更なし。"""
    root = tmp_path / "no_settings_sandbox"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / ".claude" / "checkpoints").mkdir(parents=True)

    before = _tree_manifest(root)
    result = _apply_staging_cli(root)
    after = _tree_manifest(root)

    assert result.returncode != 0
    assert before == after


@pytestmark_staging
def test_pc26_staging_hooks_only_skips_settings(tmp_path: Path) -> None:
    """PC-26: --hooks-only は settings.json が無くても exit 0 で hooks だけ配置し、
    settings.json を新規作成しない。2回実行してもバイト一致(冪等)。
    """
    root = tmp_path / "hooks_only_sandbox"
    (root / ".claude" / "hooks").mkdir(parents=True)
    (root / ".claude" / "checkpoints").mkdir(parents=True)

    result = _apply_staging_cli(root, ["--hooks-only"])
    assert result.returncode == 0, result.stderr
    assert not (root / ".claude" / "settings.json").exists()
    for name in ("tdd_red.py", "tdd_gate.py", "tdd_unlock.py"):
        assert (root / ".claude" / "hooks" / name).exists()

    manifest_first = _tree_manifest(root)
    result2 = _apply_staging_cli(root, ["--hooks-only"])
    assert result2.returncode == 0, result2.stderr
    manifest_second = _tree_manifest(root)
    assert manifest_first == manifest_second


def _count_orphan_tmp_files(root: Path) -> int:
    return len(list((root / ".claude" / "hooks").glob(".tdd_stage_*.tmp"))) + len(
        list((root / ".claude").glob(".tdd_stage_*.tmp"))
    )


def _load_staging_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_staging_tdd_gate_pc29", STAGING_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytestmark_staging
@pytest.mark.parametrize("wrapper_name", ["_write_tmp", "_replace"])
@pytest.mark.parametrize("call_index", [1, 2, 3, 4, 5])
def test_pc29_staging_write_failure_restores(
    tmp_path: Path, wrapper_name: str, call_index: int
) -> None:
    """PC-29: `_write_tmp`/`_replace` の各呼び出し位置で実処理完了直後に OSError を
    注入しても、非0終了・適用前後のツリーマニフェスト一致・一時ファイル残骸0件。

    apply(root) を in-process で呼ぶため importlib でモジュールを読み込む
    (計画: PC-29 の決定論的失敗注入)。全5回の書き込み(hooks 3本 + settings.json の
    バックアップ + settings.json 本体)のうち、指定した call_index 回目でラッパーが
    実処理後に例外を送出する(バックアップからの復元が正常に働くため、単発の
    失敗はすべて適用前状態への完全復元で終わる。レビュー指摘: R-020 二重失敗)。
    """
    module = _load_staging_module()
    root = _sandbox_with_real_settings(tmp_path)
    before = _tree_manifest(root)

    original = getattr(module, wrapper_name)
    call_count = {"n": 0}

    def fake(*args, **kwargs):
        result = original(*args, **kwargs)
        call_count["n"] += 1
        if call_count["n"] == call_index:
            raise OSError(f"injected failure at call {call_index}")
        return result

    setattr(module, wrapper_name, fake)
    rc = module.apply(root)
    after = _tree_manifest(root)

    assert rc != 0
    assert before == after
    assert _count_orphan_tmp_files(root) == 0


@pytestmark_staging
def test_pc29_staging_persistent_failure_prints_manual_recovery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PC-29(持続的失敗): settings.json 置換が完了した直後に失敗し、その復元
    (バックアップからの書き戻し)も失敗する場合、自動復元を諦めて非0(3)で
    終了し、バックアップの実パスと手動復旧手順(バックアップからの書き戻し /
    git checkout)を stderr に出す(レビュー指摘: R-020 二重失敗の残留)。

    復元側の失敗は「実処理未完了のまま」を模す(`original()` を呼ばない)ため、
    settings.json は tdd_gate.py 登録済みのまま残り、バックアップファイルも
    削除されずに残る(適用前状態への完全復元は不可能なケース)。
    """
    module = _load_staging_module()
    root = _sandbox_with_real_settings(tmp_path)

    original_replace = module._replace
    call_count = {"n": 0}

    def fake_replace(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 5:
            # settings.json 本体の置換: 実処理を完了させてから例外を送出する
            original_replace(*args, **kwargs)
            raise OSError("injected: settings replace failed after completing")
        if call_count["n"] == 6:
            # バックアップからの復元呼び出し: 実処理そのものを行わせず失敗させる
            # (持続的な書き込み不能を模す)
            raise OSError("injected: restore replace failed persistently")
        return original_replace(*args, **kwargs)

    module._replace = fake_replace
    rc = module.apply(root)
    captured = capsys.readouterr()

    assert rc == 3
    backup_path = root / ".claude" / "settings.json.tdd_gate_backup"
    assert backup_path.exists()
    assert str(backup_path) in captured.err
    assert "git checkout" in captured.err
    for name in ("tdd_red.py", "tdd_gate.py", "tdd_unlock.py"):
        assert (root / ".claude" / "hooks" / name).exists()


# --------------------------------------------------------------------------
# 付随更新の記述整合(PC-16・PC-17・PC-18・PC-30)
#
# PC-16(template/README)は Group C、PC-17(SKILL.md)は Group B、
# PC-30(CI workflow)は Group D の担当ファイルを検査する。計画の検証方法表の
# とおり、本ステップ(Step 1)単独ではこれら3件が FAIL(RED)のままになるのは
# 想定どおりであり、各グループの変更が統合された時点で GREEN になる。
# --------------------------------------------------------------------------


def test_pc16_template_and_readme_document_claude_tdd_gate() -> None:
    """PC-16: template は CLAUDE_TDD_GATE を既定 "0" で持ち、既存キーを失わない。
    README は環境変数表に1行、フック一覧表は tdd_gate.py のみ、ファイルツリーは
    3本すべてを載せる。
    """
    template_path = REPO_ROOT / "templates" / "settings.local.json.template"
    readme_path = REPO_ROOT / "README.md"

    template_data = json.loads(template_path.read_text(encoding="utf-8"))
    assert template_data.get("env", {}).get("CLAUDE_TDD_GATE") == "0"
    assert (
        len(template_data.get("env", {})) > 1
    )  # 既存キーが残っていること(空になっていない)

    readme_text = readme_path.read_text(encoding="utf-8")
    assert "CLAUDE_TDD_GATE" in readme_text
    assert "tdd_gate.py" in readme_text
    assert "tdd_red.py" not in _hooks_table_section(readme_text)
    assert "tdd_unlock.py" not in _hooks_table_section(readme_text)
    tree_section = _file_tree_hooks_section(readme_text)
    for name in ("tdd_red.py", "tdd_gate.py", "tdd_unlock.py"):
        assert name in tree_section


def _hooks_table_section(readme_text: str) -> str:
    """README のフック一覧表(見出し直後から次の見出しまで)を切り出す。"""
    match = re.search(r"###?\s*.*フック一覧.*\n(.*?)\n#{1,3}\s", readme_text, re.DOTALL)
    return match.group(1) if match else ""


def _file_tree_hooks_section(readme_text: str) -> str:
    """README のファイルツリー中の hooks/ 節を切り出す。"""
    match = re.search(r"hooks/\n(.*?)\n\S", readme_text, re.DOTALL)
    return match.group(1) if match else readme_text


def test_pc17_skill_doc_documents_red_discipline() -> None:
    """PC-17: tdd スキルに失敗ログ・先行コミット・--rearm・mutation の4語が現れ、
    既存4節の見出しが残っている。
    """
    skill_path = REPO_ROOT / ".claude" / "skills" / "tdd" / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")
    for term in ("失敗ログ", "先行コミット", "--rearm", "mutation"):
        assert term in text, term
    for heading in (
        "進め方",
        "事後条件は実装より先に固定する",
        "適用範囲の判断",
        "注意",
    ):
        assert heading in text, heading


def _tdd_markers(text: str) -> set[str]:
    """テスト説明マーカー("prefix: 説明" 形式で tdd を含む1行文字列)を抽出する。

    `test_hook`/`Test-Hook` 系の第一引数(説明文)と同じ "<prefix>: ..." の
    形だけを対象にし、パス構築の途中文字列(bash の文字列補間 vs PowerShell
    の `Join-Path` 分割で表記が変わる)は対象外にする。変数展開
    (bash `$VAR`/`${VAR}`、PowerShell `$Var`)とパス区切り(`\\` / `/`)は
    正規化する(両言語の変数名の大小文字規約は既存の codex_gate 節などでも
    一致させていない前例があるため、その差はマーカー不一致として扱わない。
    consistency.md の標準形を本ファイル対の実情に合わせて適用したもの)。
    """
    raw = re.findall(r'"([^"\n]*tdd[^"\n]*)"', text, re.IGNORECASE)
    normalized = set()
    for m in raw:
        if not re.match(r"^[A-Za-z_]+:\s", m):
            continue
        n = re.sub(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?", "$VAR", m)
        normalized.add(n.replace("\\", "/"))
    return normalized


def test_pc18_verify_hooks_markers_match() -> None:
    """PC-18: verify-hooks.sh / .ps1 の tdd マーカーが1対1対応する。

    consistency.md の標準形 diff と同じロジック(テストマーカー文字列の集合比較)を
    pytest から行う。
    """
    sh_text = (REPO_ROOT / "verify-hooks.sh").read_text(encoding="utf-8")
    ps1_text = (REPO_ROOT / "verify-hooks.ps1").read_text(encoding="utf-8")

    sh_markers = _tdd_markers(sh_text)
    ps1_markers = _tdd_markers(ps1_text)

    assert sh_markers, "verify-hooks.sh に tdd マーカーが見つかりません"
    assert sh_markers == ps1_markers, (
        sh_markers - ps1_markers,
        ps1_markers - sh_markers,
    )


def test_pc30_ci_has_ps1_syntax_check() -> None:
    """PC-30: CI workflow に ParseFile を使った ps1 構文検査ステップがあり、
    既存4ステップ(checkout/setup-uv/verify-hooks.sh/verify-installers.sh)が
    順序も含めて残っている。
    """
    workflow_path = REPO_ROOT / ".github" / "workflows" / "verify-hooks.yml"
    text = workflow_path.read_text(encoding="utf-8")

    assert "ParseFile" in text
    assert "verify-hooks.ps1" in text

    expected_order = [
        "actions/checkout",
        "astral-sh/setup-uv",
        "verify-hooks.sh",
        "verify-installers.sh",
    ]
    positions = [text.index(marker) for marker in expected_order]
    assert positions == sorted(positions), "既存4ステップの順序が変わっています"
