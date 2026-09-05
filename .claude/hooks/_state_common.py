#!/usr/bin/env python3
"""状態ファイル(`.claude/state/<slug>.json`)関連の共通ヘルパー。

state_gate.py・reinject_after_compact.py・resume_session_state.py の3フックが
`_current_branch` を個別に複製し、reinject_after_compact.py・
resume_session_state.py の2フックがさらに `_state_section` を複製していたのを
ここへ集約する(レビュー差し戻し対応。複製すると将来どれか1つだけ変更されて
ドリフトする恐れがあるため)。

ブランチ名→slug変換自体(`plan_gate._slug_from_branch`)はこのモジュールでは
扱わない。呼び出し側が引き続き `plan_gate` から直接importして slug を
計算し、`_state_section` へ渡す(R-014の複製禁止対象=正規表現ベースの
slug導出はこれまで通り一本化されたまま)。
"""

import json
from pathlib import Path
import subprocess

_STATE_HEADING = "## 現在の実行状態(検証済み・これを正とする)"


def _current_branch() -> str:
    """現在のブランチ名を返す。取得できなければ空文字列。"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _state_section(slug: str) -> tuple[str, str | None]:
    """状態ファイル(.claude/state/<slug>.json)の注入用セクションを組み立てる。

    reinject_after_compact.py・resume_session_state.py で共通の3分岐
    (ok / broken / missing_with_plan / silent。設計書 R-010、
    ユーザー決定 2026-09-04)。branch が特定できない(= slug を渡せない)場合の
    "silent" 分岐は呼び出し側の責務(このモジュールは slug 計算後の状態のみ扱う)。

    Returns:
        (status, section_text) の組。"ok" のときのみ section_text が非 None。
    """
    state_path = Path(".claude/state") / f"{slug}.json"
    if state_path.exists():
        try:
            content = state_path.read_text(encoding="utf-8")
            json.loads(content)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return "broken", None
        section = (
            f"{_STATE_HEADING}\n"
            "以下はスキーマ検証済みの構造化状態です。散文サマリより優先して従うこと。\n"
            "```json\n" + content.strip() + "\n```"
        )
        return "ok", section

    plan_path = Path(".claude/plans") / f"{slug}.md"
    if plan_path.exists():
        return "missing_with_plan", None
    return "silent", None
