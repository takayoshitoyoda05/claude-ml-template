#!/usr/bin/env python3
"""Stop フック: 各ターン終了時にパイプライン進行状態を機械的に記録する。

セッション上限は予告なく来るため、圧縮直前(PreCompact)だけの保存では
上限で切れた作業を拾えない。毎ターンの Stop で `.claude/checkpoints/
session_state.md` を上書き記録し(世代管理はしない)、次のセッション起動時に
resume_session_state.py(SessionStart, matcher: startup)が自動で注入して
再開を促す。

この機能に限り fail-open とする(計画の設計判断6): 記録の失敗でターン終了
そのものを妨げてはならない。main() 全体を防御し、どの経路でも sys.exit(0)
で終える。
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _mask import mask  # noqa: E402

# plan_gate.py の slug 導出をそのまま import して使う(正規表現を別々に複製
# すると、どちらか片方だけが将来変更されてドリフトする恐れがある。record
# フックは plan_gate と同一のブランチ→slug 規則である必要があるため、
# 複製ではなく実体を共有する。PC-13 が両モジュールの parity を照合する)
from plan_gate import _slug_from_branch  # noqa: E402

STATE_FILE = Path(".claude/checkpoints/session_state.md")
PLANS_DIR = Path(".claude/plans")
_TAIL_BYTES = 256 * 1024  # transcript 全読みを避けるための末尾シーク量(PC-7)
_GIT_TIMEOUT = 5
_MAX_CONVERSATION_CHARS = 800
_MAX_PLAN_TABLE_LINES = 20
_MAX_PLAN_TABLE_LINE_CHARS = 120
_MAX_STATUS_LINES = 40
_STEP_MENTION_RE = re.compile(r"手順\s*\d+(?:\.\d+)?")
_TABLE_LINE_RE = re.compile(r"^\| \d+ \|")


def _run_git(args: list[str]) -> str:
    """git コマンドを実行して stdout を返す。失敗時は空文字列(fail-open)。"""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _read_tail(path: Path, max_bytes: int = _TAIL_BYTES) -> str:
    """transcript の末尾 max_bytes だけを読む(毎ターンの全読みを避ける。PC-7)。

    先頭を切り詰めた場合、途中から始まる不完全な1行目は捨てる。
    """
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - max_bytes)
        f.seek(start)
        data = f.read()
    text = data.decode("utf-8", errors="replace")
    if start > 0:
        newline = text.find("\n")
        if newline != -1:
            text = text[newline + 1 :]
    return text


def _extract_text(content: object) -> str:
    """JSONL の message.content からテキスト部分だけを取り出す。

    文字列ならそのまま。リストなら type == "text" の要素のみを連結する
    (tool_result / tool_use / thinking 等は捨てる。tool_result のみの
    エントリは空文字列になり、呼び出し側で「ユーザー発話」として不採用になる)。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return ""


def _scan_conversation(text: str) -> tuple[str | None, str | None, str | None]:
    """transcript 末尾テキストから (最後のユーザー発話, 最後のアシスタント発話, 最後の手順番号言及) を返す。

    行ごとに JSON として解釈し、解釈できない行(壊れた行・空行)は無視して
    続行する(1行の破損で記録全体を諦めない)。
    """
    last_user: str | None = None
    last_assistant: str | None = None
    last_step: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        entry_type = entry.get("type")
        if entry_type not in ("user", "assistant"):
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        extracted = _extract_text(message.get("content"))
        if not extracted:
            continue
        step_matches = list(_STEP_MENTION_RE.finditer(extracted))
        if step_matches:
            last_step = step_matches[-1].group(0)
        if entry_type == "user":
            last_user = extracted
        else:
            last_assistant = extracted
    return last_user, last_assistant, last_step


def _format_conversation_piece(text: str | None) -> str:
    if not text:
        return "(取得不可)"
    # 先にマスクしてから切り詰める。切り詰め→マスクの順序だと、秘密情報
    # パターンが切り詰め境界をまたぐ場合に前半だけが残って正規表現に
    # マッチせず、断片が平文のまま状態ファイルに残る(R-3 違反)
    return mask(text)[:_MAX_CONVERSATION_CHARS]


def _read_conversation(transcript_path: str) -> tuple[str, str, str]:
    """transcript から直近の会話3項目を取り出す。読めない場合は全て「取得不可」。"""
    if not transcript_path:
        return "(取得不可)", "(取得不可)", "(見つかりません)"
    path = Path(transcript_path)
    try:
        if not path.exists():
            return "(取得不可)", "(取得不可)", "(見つかりません)"
        text = _read_tail(path)
    except (OSError, UnicodeError):
        return "(取得不可)", "(取得不可)", "(見つかりません)"
    last_user, last_assistant, last_step = _scan_conversation(text)
    return (
        _format_conversation_piece(last_user),
        _format_conversation_piece(last_assistant),
        mask(last_step) if last_step else "(見つかりません)",
    )


def _plan_section(branch: str) -> list[str]:
    """対応する計画ファイルの直接一致のみを見る(あいまい候補は解決しない)。

    plan_gate.py は日付つき glob フォールバック(`*-{slug}.md`)を持つが、
    ここでは意図的に複製しない。あいまい候補から誤った計画を選ぶと再開時の
    判断を誤らせるため、確実な一致か「該当なし」の二択にする(PC-15)。
    """
    if not branch:
        return ["該当なし(ブランチが特定できません)"]
    slug = _slug_from_branch(branch)
    plan_path = PLANS_DIR / f"{slug}.md"
    if not plan_path.exists():
        return [
            f"該当なし(`.claude/plans/{slug}.md` が存在しない。"
            "`.claude/plans/` を確認すること)"
        ]
    lines = [str(plan_path), "", "### 実装手順表(先頭20行)"]
    try:
        plan_text = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return lines
    table_lines = [
        line[:_MAX_PLAN_TABLE_LINE_CHARS]
        for line in plan_text.splitlines()
        if _TABLE_LINE_RE.match(line)
    ][:_MAX_PLAN_TABLE_LINES]
    lines.extend(table_lines)
    return lines


def _status_section() -> str:
    status = _run_git(["status", "--short"])
    if not status:
        return "(変更なし)"
    lines = status.splitlines()
    # 再注入時のトークン量を抑えるため、長すぎる status は切り詰める
    # (checkpoint_before_compact.py と同じ切り詰め方)
    if len(lines) > _MAX_STATUS_LINES:
        omitted = len(lines) - _MAX_STATUS_LINES
        return "\n".join(lines[:_MAX_STATUS_LINES]) + f"\n... 他 {omitted} 件"
    return status


def _build_state(branch: str, transcript_path: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_user, last_assistant, last_step = _read_conversation(transcript_path)

    lines = [
        f"# セッション状態記録 - {now}",
        "",
        f"## Git ブランチ: {branch or '(不明)'}",
        "",
        "## HEAD",
        _run_git(["log", "-1", "--format=%h %s"]) or "(コミットなし)",
        "",
        "## 直近コミット3件",
        _run_git(["log", "-3", "--oneline"]) or "(コミットなし)",
        "",
        "## git status --short",
        "```",
        _status_section(),
        "```",
        "",
        "## 対応する計画",
        *_plan_section(branch),
        "",
        "## 直近の会話",
        "### 最後のユーザー発話",
        last_user,
        "",
        "### 最後のアシスタント発話",
        last_assistant,
        "",
        f"## 直近に言及された手順番号(推定・要確認): {last_step}",
        "",
        "## 再開時の注意",
        "- この記録は前回ターン終了時点のもの。以降の作業は含まれない可能性がある",
        "- 自動で作業を続行せず、計画ファイルを読み直してユーザーに再開可否を確認すること",
        "- 未コミット変更を `git status` で確認すること",
    ]
    return "\n".join(lines) + "\n"


def _run() -> None:
    if os.environ.get("CLAUDE_SESSION_RESUME", "1") == "0":
        return

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}

    branch = _run_git(["branch", "--show-current"])
    transcript_path = data.get("transcript_path", "") or ""

    content = _build_state(branch, transcript_path)

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(content, encoding="utf-8")


def main() -> None:
    try:
        _run()
    except Exception:
        # fail-open: 記録の失敗でターン終了そのものを妨げない(設計判断6)
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
