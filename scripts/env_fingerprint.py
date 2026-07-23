#!/usr/bin/env python3
"""実験の再現に必要な実行環境情報を収集し、JSON として標準出力へ出力する。

Python 版数・プラットフォーム・git commit・uv.lock のハッシュ・
torch/CUDA 版数を1コマンドで機械可読な形に固定し、MLflow や実験ログに
添付できるようにする。標準ライブラリのみで動作し、torch は任意依存として
扱う。いかなる収集の失敗も exit code 0 で JSON を返す(部分的な null を許す)。
"""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path


def _collect_python_version() -> str | None:
    """実行中の Python 版数を取得する。

    Returns:
        `sys.version` 文字列。取得に失敗した場合は None。
    """
    try:
        return sys.version
    except Exception:
        return None


def _collect_platform() -> str | None:
    """実行プラットフォームの文字列表現を取得する。

    Returns:
        `platform.platform()` の結果。取得に失敗した場合は None。
    """
    try:
        return platform.platform()
    except Exception:
        return None


def _collect_git_commit() -> str | None:
    """現在の git commit(HEAD)を取得する。

    Returns:
        `git rev-parse HEAD` の標準出力(前後空白除去)。git リポジトリ外・
        git 未導入・その他の失敗時は None。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _collect_uv_lock_sha256() -> str | None:
    """カレントディレクトリの uv.lock の SHA-256 を取得する。

    Returns:
        `uv.lock` の内容の SHA-256 16進文字列。ファイルが存在しない・
        読み込みに失敗した場合は None。
    """
    try:
        uv_lock_path = Path("uv.lock")
        content = uv_lock_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return None


def _collect_torch_info() -> tuple[str | None, str | None]:
    """torch/CUDA 版数を取得する(torch は任意依存)。

    Returns:
        `(torch_version, cuda_version)` のタプル。torch が import できない
        場合や版数取得に失敗した場合は両方 None。
    """
    try:
        import torch  # noqa: PLC0415 (任意依存のため関数内 import)

        return torch.__version__, torch.version.cuda
    except Exception:
        return None, None


def collect_fingerprint() -> dict[str, str | None]:
    """環境情報を収集し、固定順のキーを持つ dict にまとめる。

    Returns:
        キー `python_version` / `platform` / `git_commit` /
        `uv_lock_sha256` / `torch_version` / `cuda_version` を
        この順で持つ dict。各値は収集に失敗した場合 None。
    """
    torch_version, cuda_version = _collect_torch_info()
    return {
        "python_version": _collect_python_version(),
        "platform": _collect_platform(),
        "git_commit": _collect_git_commit(),
        "uv_lock_sha256": _collect_uv_lock_sha256(),
        "torch_version": torch_version,
        "cuda_version": cuda_version,
    }


def main() -> int:
    """環境フィンガープリントを収集し JSON として標準出力へ出力する。

    Returns:
        常に 0(いかなる収集失敗でも部分的な null を許容し exit 0 とする)。
    """
    fingerprint = collect_fingerprint()
    print(json.dumps(fingerprint))
    return 0


if __name__ == "__main__":
    sys.exit(main())
