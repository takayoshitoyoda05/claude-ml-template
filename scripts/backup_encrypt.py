#!/usr/bin/env python3
"""`data/`(`data/exports/` を除く)を tar + age で暗号化してバックアップする(R-015)。

ローカルの `data/` は平文のまま(境界のみ暗号化)。recipient は
`.claude/backup_recipients.txt`(1行1公開鍵)に記載された2件(個人鍵+
リカバリ鍵)を使う。鍵が2件未満・`age` 未導入のいずれもエラーメッセージと
導入案内を出して非0終了し、`data/` の内容と出力先のいずれも変更しない
(書きかけの出力ファイルも残さない)。復号手順は README に文書化する。

配布元: takayoshitoyoda05/claude-ml-template テンプレート
"""

import io
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

_DATA_DIR_NAME = "data"
_EXPORTS_DIR_NAME = "exports"
_RECIPIENTS_RELATIVE_PATH = Path(".claude") / "backup_recipients.txt"
_MIN_RECIPIENTS = 2


def _read_recipients(root: Path) -> list[str]:
    """`.claude/backup_recipients.txt` から公開鍵(1行1件)を読む。

    Args:
        root: プロジェクトルート。

    Returns:
        空行を除いた公開鍵の一覧。ファイルが無ければ空リスト。
    """
    path = root / _RECIPIENTS_RELATIVE_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _build_tar(data_dir: Path) -> bytes:
    """`data/`(`exports/` を除く)を tar にまとめ、バイト列で返す。

    Args:
        data_dir: `data/` ディレクトリのパス。存在しない場合は空の tar を返す。

    Returns:
        `data/` 配下(`exports/` 除く)を格納した tar アーカイブのバイト列。
    """
    exports_dir = data_dir / _EXPORTS_DIR_NAME
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        if data_dir.is_dir():
            for path in sorted(data_dir.rglob("*")):
                if not path.is_file():
                    continue
                try:
                    path.relative_to(exports_dir)
                    continue
                except ValueError:
                    pass
                tar.add(
                    path,
                    arcname=str(Path(_DATA_DIR_NAME) / path.relative_to(data_dir)),
                )
    return buffer.getvalue()


def main(argv: list[str] | None = None) -> int:
    """コマンドライン引数の出力先パスへ、暗号化済みバックアップを書き出す。

    Args:
        argv: `[出力先パス]`(省略時は `sys.argv[1:]`)。

    Returns:
        正常終了は 0。鍵不足・`age` 未導入・暗号化失敗は非0
        (いずれも `data/` と出力先を変更しない)。
    """
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("使い方: backup_encrypt.py <出力先パス>", file=sys.stderr)
        return 1

    root = Path.cwd()
    out_path = Path(argv[0])

    if shutil.which("age") is None:
        print(
            "age が未導入。https://github.com/FiloSottile/age からインストールする",
            file=sys.stderr,
        )
        return 1

    recipients = _read_recipients(root)
    if len(recipients) < _MIN_RECIPIENTS:
        print(
            f"{_RECIPIENTS_RELATIVE_PATH} に公開鍵が{_MIN_RECIPIENTS}件未満"
            "(個人鍵+リカバリ鍵の2件を1行1件で記載する)",
            file=sys.stderr,
        )
        return 1

    tar_bytes = _build_tar(root / _DATA_DIR_NAME)

    # 途中失敗で書きかけの出力を残さないため、まず一時ファイルへ書き、
    # age が成功した場合のみ最終パスへ差し替える。
    tmp_path = out_path.with_name(out_path.name + ".partial")
    cmd = ["age"]
    for recipient in recipients:
        cmd += ["-r", recipient]
    cmd += ["-o", str(tmp_path)]

    try:
        result = subprocess.run(
            cmd,
            input=tar_bytes,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        tmp_path.unlink(missing_ok=True)
        print(f"age の実行に失敗した: {type(exc).__name__}", file=sys.stderr)
        return 1

    if result.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        stderr = result.stderr.decode("utf-8", errors="replace")
        print(f"age による暗号化に失敗した: {stderr}", file=sys.stderr)
        return 1

    tmp_path.replace(out_path)
    print(f"暗号化済みバックアップを作成した: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
