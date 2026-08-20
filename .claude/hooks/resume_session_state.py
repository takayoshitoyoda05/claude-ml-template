#!/usr/bin/env python3
"""SessionStart(startup時のみ): 直前セッションの記録状態を再開時に注入する。

Stop フック record_session_state.py が毎ターン上書きする
`.claude/checkpoints/session_state.md` を、新しいセッションの起動直後に
文脈へ注入し、上限で切れた作業の再開を促す。既存の
reinject_after_compact.py(SessionStart, matcher: compact)とは別ファイルの
別経路であり、source を自身でも再判定することで、matcher の解釈が
どうであれ compact 時に二重注入しない(R-4)。

この機能に限り fail-open とする: 記録が無い・古い・壊れていてもセッション
開始を妨げてはならない。異常系は常に無出力・exit 0 とする。
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(".claude/checkpoints/session_state.md")
_MAX_AGE_HOURS = 72
_BRANCH_LINE_PREFIX = "## Git ブランチ:"


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


def _recorded_branch(content: str) -> str | None:
    """状態ファイル本文から `## Git ブランチ:` 行のブランチ名を取り出す。"""
    for line in content.splitlines():
        if line.startswith(_BRANCH_LINE_PREFIX):
            return line[len(_BRANCH_LINE_PREFIX) :].strip()
    return None


def _resume_instructions() -> str:
    return (
        "## セッション再開\n"
        "前回セッションの進行状態の記録が見つかった。以下を守ること:\n"
        "- 自動で作業を続行せず、対応する計画ファイルを読み直してユーザーに"
        "再開可否を確認する\n"
        "- 未コミット変更が残っていないか `git status` で確認する\n"
        "- この記録は前回ターン終了時点のものであり、それ以降の作業は"
        "含まれない可能性がある\n"
    )


def _run() -> None:
    if os.environ.get("CLAUDE_SESSION_RESUME", "1") == "0":
        return

    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # compact 時の注入は既存 reinject_after_compact.py の担当。clear は
    # ユーザーが意図的に文脈を消しているため注入しない
    if data.get("source") != "startup":
        return

    try:
        if not STATE_FILE.exists():
            return
        age_hours = (datetime.now().timestamp() - STATE_FILE.stat().st_mtime) / 3600
        if age_hours > _MAX_AGE_HOURS:
            return
        content = STATE_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return

    if not content.strip():
        return

    recorded = _recorded_branch(content)
    if recorded is None or recorded != _current_branch():
        return

    print(_resume_instructions() + "\n" + content)


def main() -> None:
    try:
        _run()
    except Exception:
        # fail-open: 記録が無い・古い・壊れていてもセッション開始を妨げない
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
