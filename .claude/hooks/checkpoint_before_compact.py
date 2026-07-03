#!/usr/bin/env python3
"""PreCompact: コンテキスト圧縮の直前に、現在の状態をバックアップする。
async実行を想定(圧縮の速度を妨げないため)。"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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

    lines = [f"# チェックポイント ({trigger}) - {ts}", ""]

    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
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
        try:
            import shutil
            shutil.copy2(transcript_path, backup_dir / f"transcript-{trigger}-{ts}.jsonl")
        except Exception:
            pass

    sys.exit(0)


if __name__ == "__main__":
    main()
