#!/usr/bin/env python3
"""SessionStart(compact時のみ): 圧縮直後に、構造化状態・直前のチェックポイントと
注意事項を会話に再注入する。

`.claude/state/<slug>.json`(SKILL.state 部分採用。設計書 §4.5)が読めれば、
それを「検証済み・これを正とする」節として latest.md より前に出す(R-008)。
状態ファイルが破損している場合、または不在で同ブランチの計画ファイル
(`.claude/plans/<slug>.md`、パイプラインが動いていた証拠)がある場合は節を
出さず1行だけ通知する。両方不在(非パイプラインセッション)なら状態セクションも
通知も出さない(R-010。ユーザー決定 2026-09-04: 無条件通知は非パイプライン
セッションの起動時ノイズになるため、計画ファイルの有無で3分岐する)。

ブランチ名からの状態ファイルパス導出は `plan_gate._slug_from_branch` の import
で行う(state_gate.py・resume_session_state.py と同じ規約。正規表現複製禁止)。
現在ブランチの取得(`_current_branch`)と状態セクションの組み立て本体
(`_state_section`)は `_state_common` から共有する(resume_session_state.py と
複製禁止)。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_gate import _slug_from_branch  # noqa: E402
from _state_common import _current_branch, _state_section as _common_state_section  # noqa: E402


def _state_section() -> tuple[str, str | None]:
    """状態ファイルの注入用セクションを組み立てる(`_state_common` 実装を共有)。

    Returns:
        (status, section_text) の組。status は "ok"(状態注入)/
        "broken"(JSON破損、通知のみ)/ "missing_with_plan"(不在だが計画ファイルが
        あり通知のみ)/ "silent"(両方不在または現在ブランチ不明、何も出さない)。
        "ok" のときのみ section_text が非 None。
    """
    branch = _current_branch()
    if not branch:
        return "silent", None
    slug = _slug_from_branch(branch)
    return _common_state_section(slug)


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

    status, section = _state_section()
    if status == "ok":
        parts.append(section)
    elif status in ("broken", "missing_with_plan"):
        parts.append(
            "状態ファイルが読めないため、状態セクションは省略します(.claude/state/)。"
        )

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
