"""codex_gate.py の再発火抑制(同一状態抑制 + 一時停止)のテスト。

対象: `_staging_codex_gate.py` が配置する codex_gate.py。
staging を `--root` でサンドボックスへ適用し、その出力を tmp の git
リポジトリに対して subprocess で実行して検証する(実リポジトリの
保護パスには触れない)。
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING = REPO_ROOT / "_staging_codex_gate.py"


def _apply_staging(root: Path) -> Path:
    result = subprocess.run(
        [sys.executable, str(STAGING), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    hook = root / ".claude" / "hooks" / "codex_gate.py"
    assert hook.exists()
    return hook


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True, timeout=10)
    subprocess.run(
        ["git", "config", "user.email", "t@example.com"],
        cwd=path,
        check=True,
        timeout=10,
    )
    subprocess.run(
        ["git", "config", "user.name", "t"], cwd=path, check=True, timeout=10
    )
    (path / "a.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, timeout=10)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True, timeout=10)


def _head(path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()


def _write_sentinel(repo: Path) -> None:
    checkpoints = repo / ".claude" / "checkpoints"
    checkpoints.mkdir(parents=True, exist_ok=True)
    (checkpoints / "codex_review_done.txt").write_text(
        _head(repo) + "\n", encoding="utf-8"
    )


def _run_gate(hook: Path, repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(hook)],
        cwd=repo,
        capture_output=True,
        text=True,
        env={"CLAUDE_CROSS_REVIEW": "1", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        timeout=30,
    )


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    hook = _apply_staging(tmp_path / "sandbox")
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_sentinel(repo)
    return hook, repo


def test_clean_tree_passes(tmp_path: Path) -> None:
    """回帰: HEAD 一致かつクリーンなら従来どおり通過する。"""
    hook, repo = _setup(tmp_path)
    result = _run_gate(hook, repo)
    assert result.returncode == 0, result.stderr


def test_dirty_tree_blocks_first_time(tmp_path: Path) -> None:
    """回帰: dirty tree の初回停止は exit 2 で警告する。"""
    hook, repo = _setup(tmp_path)
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    result = _run_gate(hook, repo)
    assert result.returncode == 2
    assert "未コミット変更" in result.stderr


def test_same_dirty_state_suppressed_second_time(tmp_path: Path) -> None:
    """同一状態抑制: 状態が変わらない2回目以降の停止は黙って通す。"""
    hook, repo = _setup(tmp_path)
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    first = _run_gate(hook, repo)
    assert first.returncode == 2
    second = _run_gate(hook, repo)
    assert second.returncode == 0, second.stderr
    assert second.stderr == ""
    third = _run_gate(hook, repo)
    assert third.returncode == 0, third.stderr


def test_changed_dirty_state_blocks_again(tmp_path: Path) -> None:
    """同一状態抑制: 状態が変われば(別ファイル追加)再びブロックする。"""
    hook, repo = _setup(tmp_path)
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    assert _run_gate(hook, repo).returncode == 2
    assert _run_gate(hook, repo).returncode == 0
    (repo / "b.txt").write_text("new\n", encoding="utf-8")
    result = _run_gate(hook, repo)
    assert result.returncode == 2
    assert "未コミット変更" in result.stderr


def test_pass_clears_suppression(tmp_path: Path) -> None:
    """正常通過で指紋が破棄され、同一の dirty 状態が再出現したら改めて警告する。

    コミットで HEAD が変わるため、同一 status 出力でも指紋は変わるのが通常経路。
    ここでは「通過後に指紋ファイルが消えている」ことを直接確認する。
    """
    hook, repo = _setup(tmp_path)
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    assert _run_gate(hook, repo).returncode == 2
    last_block = repo / ".claude" / "checkpoints" / "codex_gate_last_block.txt"
    assert last_block.exists()
    # クリーンに戻して通過させる
    subprocess.run(
        ["git", "checkout", "-q", "--", "a.txt"], cwd=repo, check=True, timeout=10
    )
    assert _run_gate(hook, repo).returncode == 0
    assert not last_block.exists()


def test_pause_file_passes_unconditionally(tmp_path: Path) -> None:
    """一時停止: codex_gate_pause が存在すれば dirty でも初回から通す。"""
    hook, repo = _setup(tmp_path)
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    (repo / ".claude" / "checkpoints" / "codex_gate_pause").write_text(
        "", encoding="utf-8"
    )
    result = _run_gate(hook, repo)
    assert result.returncode == 0, result.stderr


def test_no_sentinel_block_also_suppressed(tmp_path: Path) -> None:
    """センチネル不在ブロックにも同一状態抑制が効く(種別を含めた指紋)。"""
    hook = _apply_staging(tmp_path / "sandbox")
    repo = tmp_path / "repo"
    _init_repo(repo)  # センチネルは作らない
    first = _run_gate(hook, repo)
    assert first.returncode == 2
    assert "まだ実行されていません" in first.stderr
    second = _run_gate(hook, repo)
    assert second.returncode == 0, second.stderr


def test_staging_codex_gate_idempotent_apply_twice(tmp_path: Path) -> None:
    """staging の冪等性: 2回適用してもバイト単位で同一。"""
    root = tmp_path / "sandbox"
    hook = _apply_staging(root)
    first_bytes = hook.read_bytes()
    _apply_staging(root)
    assert hook.read_bytes() == first_bytes
