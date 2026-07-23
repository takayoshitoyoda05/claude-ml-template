"""env_fingerprint.py の受け入れ検証を pytest 回帰テスト化したもの。

対象: `.claude/plans/20260723-env-fingerprint.md` の R-002/003/004/009/010/011。
スクリプトを import せず、実運用と同じ CLI 起動(subprocess + sys.executable)で
検証する(BrokenPipe / exit code / stdout 直列化の経路を実測するため)。
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "env_fingerprint.py"
# 全 subprocess 呼び出しで一貫させるタイムアウト(秒)。値がバラつくと
# CI 環境差でハングの検出漏れが起きるため定数化する。
_SUBPROCESS_TIMEOUT = 10
EXPECTED_KEYS = [
    "python_version",
    "platform",
    "git_commit",
    "uv_lock_sha256",
    "torch_version",
    "cuda_version",
]
# uv.lock の内容そのものは検証対象ではなく、既知バイト列との SHA-256 一致だけを
# 見たいので、実物のロックファイル形式である必要はない
KNOWN_UV_LOCK_CONTENT = b'version = 1\nrequires-python = ">=3.10"\n'


def _run_fingerprint(
    cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """`scripts/env_fingerprint.py` を CLI として subprocess 起動する。

    import せず実運用と同じ経路(sys.executable + 絶対パス)で起動することで、
    BrokenPipe / exit code / stdout 直列化まで含めて検証できるようにする。

    Args:
        cwd: サブプロセスの作業ディレクトリ。
        extra_env: 追加で設定する環境変数(GIT_CEILING_DIRECTORIES 等)。

    Returns:
        完了した subprocess の結果(stdout/stderr/returncode を含む)。
    """
    env = os.environ.copy()
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def test_output_is_valid_json(tmp_path: Path) -> None:
    """R-002: 出力が有効 JSON であり、exit code が 0 であることを確認する。"""
    result = _run_fingerprint(tmp_path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data, dict)


def test_fixed_keys_in_order(tmp_path: Path) -> None:
    """R-003: キーが固定6個・固定順であることを確認する。"""
    result = _run_fingerprint(tmp_path)
    data = json.loads(result.stdout)
    assert list(data.keys()) == EXPECTED_KEYS


def test_git_and_uv_lock_null_outside_repo(tmp_path: Path) -> None:
    """R-004: git 外・uv.lock 無しの場所では両方 null になることを確認する。

    サブプロセスの cwd が git リポジトリ配下に含まれてしまう環境でも本リポジトリの
    親探索を拾わないよう、GIT_CEILING_DIRECTORIES で探索境界を tmp_path の親に固定する。
    """
    env = {"GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}
    result = _run_fingerprint(tmp_path, env)
    data = json.loads(result.stdout)
    assert data["git_commit"] is None
    assert data["uv_lock_sha256"] is None


def test_uv_lock_sha256_matches_known_content(tmp_path: Path) -> None:
    """R-010: 既知バイト列の uv.lock を置いたとき SHA-256 が一致することを確認する。"""
    (tmp_path / "uv.lock").write_bytes(KNOWN_UV_LOCK_CONTENT)
    env = {"GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}
    result = _run_fingerprint(tmp_path, env)
    data = json.loads(result.stdout)
    expected = hashlib.sha256(KNOWN_UV_LOCK_CONTENT).hexdigest()
    assert data["uv_lock_sha256"] == expected


def test_git_commit_matches_head_in_repo(tmp_path: Path) -> None:
    """R-011: git リポジトリ内で実行すると HEAD と一致することを確認する。

    tmp_path 内に user.email/user.name をコマンド引数で指定した使い捨てリポジトリを
    作り、ユーザーの git 設定(グローバル/システム)に依存せず自己完結させる。
    実行環境のグローバル/システム git 設定(例: commit.gpgsign)や対話プロンプトが
    テスト結果に影響しないよう、全 git 呼び出しに専用 env を渡して遮断する。
    """
    git_env = os.environ.copy()
    git_env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=git_env,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    (tmp_path / "README.md").write_text("test")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "README.md"],
        check=True,
        capture_output=True,
        env=git_env,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test User",
            "commit",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
        env=git_env,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    expected = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=git_env,
        timeout=_SUBPROCESS_TIMEOUT,
    ).stdout.strip()
    result = _run_fingerprint(tmp_path)
    data = json.loads(result.stdout)
    assert data["git_commit"] == expected


def test_torch_info_matches_actual_import(tmp_path: Path) -> None:
    """R-009: torch_version/cuda_version が同一インタプリタでの実 import 結果と一致することを確認する。

    別プロセスで `import torch` を試み、可能なら実際の版数(CPU ビルドは
    cuda_version=None)を、不可能なら両方 None を期待値として個別比較する。
    torch 未導入環境では None 分岐のみ実行される(torch 有り経路は torch 導入環境でのみ検証される)。
    """
    probe_code = (
        "import json\n"
        "try:\n"
        "    import torch\n"
        "    cuda = torch.version.cuda\n"
        "    print(json.dumps({\n"
        "        'torch_version': str(torch.__version__),\n"
        "        'cuda_version': str(cuda) if cuda is not None else None,\n"
        "    }))\n"
        "except Exception:\n"
        "    print(json.dumps({'torch_version': None, 'cuda_version': None}))\n"
    )
    probe = subprocess.run(
        [sys.executable, "-c", probe_code],
        capture_output=True,
        text=True,
        check=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    expected = json.loads(probe.stdout)
    env = {"GIT_CEILING_DIRECTORIES": str(tmp_path.parent)}
    result = _run_fingerprint(tmp_path, env)
    data = json.loads(result.stdout)
    assert data["torch_version"] == expected["torch_version"]
    assert data["cuda_version"] == expected["cuda_version"]


def test_broken_pipe_returns_exit_zero() -> None:
    """子の stdout を即クローズしても exit code 0 で終了する(BrokenPipe 耐性)。"""
    with subprocess.Popen(
        [sys.executable, str(SCRIPT_PATH)], stdout=subprocess.PIPE
    ) as proc:
        assert proc.stdout is not None
        proc.stdout.close()
        try:
            returncode = proc.wait(timeout=_SUBPROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise
    assert returncode == 0
