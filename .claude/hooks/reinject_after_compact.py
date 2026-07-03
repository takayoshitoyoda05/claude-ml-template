#!/usr/bin/env python3
"""SessionStart(compact時のみ): 圧縮直後に、直前のチェックポイントと
注意事項を会話に再注入する。"""
import json
import sys
from pathlib import Path


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    source = data.get("source", "")
    if source != "compact":
        # 通常起動やresumeでは何もしない(CLAUDE.mdが別途読み込まれるため)
        sys.exit(0)

    parts = []
    latest = Path(".claude/checkpoints/latest.md")
    if latest.exists():
        parts.append("## 直前のチェックポイント\n" + latest.read_text(encoding="utf-8"))

    parts.append(
        "## コンテキスト圧縮が発生しました\n"
        "- ルート直下のCLAUDE.mdは再読込済みだが、サブディレクトリの"
        "CLAUDE.md(例: projects/Deep_MIL/CLAUDE.md)は自動では再読込されない。"
        "必要ならそのディレクトリのファイルを読んで明示的に再確認すること。\n"
        "- design-interview 等のスキルを使用中だった場合、手順の続きを"
        "覚えているか確認し、怪しければユーザーに確認すること。\n"
        "- 具体的なファイルパス・数値・直前の指示は失われている可能性がある。"
        "推測で進めず、.claude/plans/ や docs/EXPERIMENT_LOG.md を確認すること。"
    )

    print("\n\n".join(parts))
    sys.exit(0)


if __name__ == "__main__":
    main()
