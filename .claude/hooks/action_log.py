#!/usr/bin/env python3
"""PostToolUse フック: 全ツール実行を logs/actions/ に JSONL で自動記録する。

モデルの記憶に依存しない機械記録。エージェントが「何をしたか」の完全な証跡。
記録前に秘密情報をマスキングする。
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mask import mask  # noqa: E402

MAX_FIELD = 50_000  # 1フィールドの上限文字数(巨大出力によるログ肥大の防止)
KEEP_LOGS = (
    30  # ログファイルの保持世代数(checkpoint_before_compact.pyのprune方針と整合)
)


def _clip(text: str) -> str:
    if text and len(text) > MAX_FIELD:
        return text[:MAX_FIELD] + f"\n...[clipped {len(text) - MAX_FIELD} chars]"
    return text or ""


def _prune_old_logs(log_dir: Path, pattern: str) -> None:
    """ファイル数が上限を超えたら、名前順(=日付昇順)で古いものから削除する。

    ログが平文で無限に溜まるのを防ぐ(checkpoint_before_compact.pyと同方針)。
    """
    files = sorted(log_dir.glob(pattern))
    for f in files[:-KEEP_LOGS]:
        try:
            f.unlink()
        except OSError:
            pass


def main():
    if os.environ.get("CLAUDE_ACTION_LOG", "1") == "0":
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    log_dir = Path("logs/actions")
    log_dir.mkdir(parents=True, exist_ok=True)

    session = payload.get("session_id", "unknown")[:8]
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session,
        "tool": payload.get("tool_name", ""),
        "input": mask(
            _clip(json.dumps(payload.get("tool_input", {}), ensure_ascii=False))
        ),
        "output": mask(_clip(str(payload.get("tool_response", "")))),
        "duration_ms": payload.get("duration_ms"),
    }

    log_file = (
        log_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{session}.jsonl"
    )
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        # ログ失敗で作業は止めないが、欠落を可視化する(Codex指摘の採用)
        print(f"[action_log] failed to write log: {e}", file=sys.stderr)

    _prune_old_logs(log_dir, "*.jsonl")

    sys.exit(0)


if __name__ == "__main__":
    main()
