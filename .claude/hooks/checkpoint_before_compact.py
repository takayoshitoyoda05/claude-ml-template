#!/usr/bin/env python3
"""PreCompact: コンテキスト圧縮の直前に、現在の状態をバックアップする。
async実行を想定(圧縮の速度を妨げないため)。"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mask import mask  # noqa: E402


KEEP_GENERATIONS = 10


def prune_old(backup_dir, pattern):
    """タイムスタンプ順(=名前順)で古い世代を削除する。
    会話ログを含むファイルが平文で無限に溜まるのを防ぐ。"""
    files = sorted(backup_dir.glob(pattern))
    for f in files[:-KEEP_GENERATIONS]:
        try:
            f.unlink()
        except Exception:
            pass


def _record_compact(session_id: str, backup_dir: Path) -> None:
    """auto-compact 発生時にセッション別の回数を状態ファイルへ加算する。

    session_monitor.py が読む状態ファイルと同じスキーマを使う
    (圧縮直後は使用量が下がって見えるため、二次指標として利用するため)。
    """
    state_path = backup_dir / "session_monitor_state.json"
    try:
        text = state_path.read_text(encoding="utf-8") if state_path.exists() else "{}"
        state = json.loads(text)
        if not isinstance(state, dict):
            state = {}
    except (OSError, UnicodeError, ValueError):
        state = {}
    session_state = state.get(session_id)
    if not isinstance(session_state, dict):
        session_state = {}
    try:
        compact_count = int(session_state.get("compact_count", 0) or 0)
    except (TypeError, ValueError):
        compact_count = 0
    session_state["compact_count"] = compact_count + 1
    state[session_id] = session_state
    try:
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, UnicodeError, ValueError):
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    trigger = data.get("trigger", "unknown")  # "manual" or "auto"
    transcript_path = data.get("transcript_path", "")

    backup_dir = Path(".claude/checkpoints")
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    # session_monitor: auto-compact の発生回数をセッション別に記録する
    if trigger == "auto":
        _record_compact(data.get("session_id", "unknown"), backup_dir)

    lines = [f"# チェックポイント ({trigger}) - {ts}", ""]

    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
        ).stdout.strip()
        # 再注入時のトークン量を抑えるため、長すぎる status は切り詰める
        status_lines = status.splitlines()
        if len(status_lines) > 40:
            omitted = len(status_lines) - 40
            status = "\n".join(status_lines[:40]) + f"\n... 他 {omitted} 件"
        lines.append(f"## Git ブランチ: {branch}")
        lines.append("## git status --short")
        lines.append("```")
        lines.append(status if status else "(変更なし)")
        lines.append("```")
    except Exception:
        pass

    lines.append("")
    lines.append("## 注意")
    lines.append("この直後にコンテキスト圧縮が発生する。具体的な指示や数値は")
    lines.append("要約で失われる可能性がある。作業再開時は .claude/plans/ や")
    lines.append("docs/EXPERIMENT_LOG.md、対象プロジェクトの CLAUDE.md を")
    lines.append("再確認すること。")

    content = "\n".join(lines)
    (backup_dir / "latest.md").write_text(content, encoding="utf-8")
    (backup_dir / f"state-{trigger}-{ts}.md").write_text(content, encoding="utf-8")

    if transcript_path and Path(transcript_path).exists():
        # 会話全体には秘密情報が混入しうる。action_log / agent_log / report_gen と
        # 同じくマスキングを通してから保存する(ここだけ平文だと、他をマスクした
        # 意味が失われる)
        try:
            text = Path(transcript_path).read_text(encoding="utf-8", errors="replace")
            (backup_dir / f"transcript-{trigger}-{ts}.jsonl").write_text(
                mask(text), encoding="utf-8"
            )
        except Exception:
            pass

    prune_old(backup_dir, "state-*.md")
    prune_old(backup_dir, "transcript-*.jsonl")

    sys.exit(0)


if __name__ == "__main__":
    main()
