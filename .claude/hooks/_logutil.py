#!/usr/bin/env python3
"""action_log.py / agent_log.py が共有するログ保持(prune)ユーティリティ。

ログが平文で無限に溜まるのを防ぐ(checkpoint_before_compact.pyと同方針)。
"""

from pathlib import Path


def prune_old_logs(log_dir: Path, keep: int = 30) -> None:
    """ファイル数が keep を超えたら、名前順(=日付昇順)で古いものから削除する。"""
    files = sorted(log_dir.glob("*.jsonl"))
    for f in files[:-keep]:
        try:
            f.unlink()
        except OSError:
            pass
