#!/usr/bin/env python3
"""SubagentStop フック: サブエージェントの実行完了を logs/agents/ に JSONL 記録する。

マルチエージェント監査の標準フィールド「委譲チェーン」に相当する記録。
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mask import mask  # noqa: E402

KEEP_LOGS = (
    30  # ログファイルの保持世代数(checkpoint_before_compact.pyのprune方針と整合)
)


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

    log_dir = Path("logs/agents")
    log_dir.mkdir(parents=True, exist_ok=True)

    session = payload.get("session_id", "unknown")[:8]
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session,
        "agent": payload.get("agent_name", payload.get("subagent_type", "")),
        "model": payload.get("resolvedModel", payload.get("model", "")),
        "transcript_path": payload.get("agent_transcript_path", ""),
        "summary": mask(str(payload.get("last_message", ""))[:2000]),
    }
    # ペイロードに usage 系フィールドがあれば含める(バージョンにより有無が異なる)
    for key in ("usage", "total_tokens", "cost_usd", "duration_ms"):
        if key in payload:
            entry[key] = payload[key]

    log_file = (
        log_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{session}.jsonl"
    )
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        # ログ失敗で作業は止めないが、欠落を可視化する(Codex指摘の採用)
        print(f"[agent_log] failed to write log: {e}", file=sys.stderr)

    _prune_old_logs(log_dir, "*.jsonl")

    sys.exit(0)


if __name__ == "__main__":
    main()
