#!/usr/bin/env python3
"""Stop フック: セッションのコンテキスト使用量が重くなったことを、画面を
見ていなくても気づけるように警告する(非ブロック)。

CLAUDE_SESSION_MONITOR=1 のときだけ動作する。transcript の末尾の
assistant message.usage(input_tokens + cache_read_input_tokens +
cache_creation_input_tokens)を実測値として使い、warn/high の2水準で
handoff を案内する。auto-compact が同一セッションで2回以上発生した
ときは使用量水準に関わらず1回だけ警告する(圧縮直後は使用量が
下がって見えるため、二次指標として併用する)。

checkpoint_before_compact.py(PreCompact)、reinject_after_compact.py
(SessionStart)、record_session_state.py(Stop・毎ターン状態記録)は
そのまま。本フックは「気づき」だけを追加する。

いかなる入力でも exit 0 で終了する(警告のみで作業を止めない)。
"""

import json
import os
import sys
from pathlib import Path

_STATE_PATH = Path(".claude/checkpoints/session_monitor_state.json")

_WARN_MESSAGE = (
    "コンテキストが重くなっています(約{tokens:,} tokens)。"
    "『handoffして』で引き継ぎ文書を作れます。"
    "session_state.md は毎ターン更新済みです。"
)
_HIGH_MESSAGE = (
    "コンテキスト使用量が high 水準です(約{tokens:,} tokens)。"
    "『handoffして』で引き継ぎ文書を作れます。"
    "session_state.md は毎ターン更新済みです。"
)
_COMPACT_MESSAGE = (
    "auto-compact が複数回発生しました(compact_count={compact_count})。"
    "『handoffして』で引き継ぎ文書を作れます。"
    "session_state.md は毎ターン更新済みです。"
)


def _int_env(name: str, default: int) -> int:
    """環境変数から整数を読む。未設定・不正値は既定値にフォールバックする。

    Args:
        name: 環境変数名。
        default: 未設定・パース失敗時の既定値。

    Returns:
        解決した整数値。
    """
    raw = os.environ.get(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _sum_usage(usage: dict) -> int | None:
    """usage の3フィールドを合算する。型が不正なら None を返す(壊れた行はスキップ)。

    Args:
        usage: transcript の message.usage オブジェクト。

    Returns:
        合算値。フィールドが数値でない場合は None。
    """
    try:
        return (
            usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
        )
    except TypeError:
        return None


def _read_usage_tokens(transcript_path: str) -> int:
    """transcript を行単位ストリームで走査し、最後に見つかった usage 合算値を返す。

    ファイル全体をメモリに保持しない(非機能要件)。読み取り不能・
    JSON 不正な行は無視して継続する(fail-open)。

    Args:
        transcript_path: Stop ペイロードの transcript_path。

    Returns:
        最後に見つかった有効な usage の合算値。見つからなければ 0。
    """
    if not transcript_path:
        return 0
    total = 0
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "assistant":
                    continue
                message = entry.get("message")
                if not isinstance(message, dict):
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                value = _sum_usage(usage)
                if value is not None:
                    total = value
    except (OSError, UnicodeError):
        return 0
    return total


def _load_state(path: Path) -> dict:
    """状態ファイルを読む。破損・読取不能なら空として初期化する(fail-open)。

    Args:
        path: 状態ファイルのパス。

    Returns:
        session_id をキーとする辞書。読めなければ空辞書。
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(path: Path, state: dict) -> None:
    """状態ファイルを書く。失敗しても警告は出せないため黙って諦める(fail-open)。

    Args:
        path: 状態ファイルのパス。
        state: 書き込む状態全体。
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except (OSError, UnicodeError, ValueError):
        pass


def main() -> None:
    if os.environ.get("CLAUDE_SESSION_MONITOR", "0") != "1":
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except (OSError, UnicodeError, ValueError):
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)
    if payload.get("stop_hook_active"):
        sys.exit(0)

    session_id = str(payload.get("session_id", "unknown"))
    usage_tokens = _read_usage_tokens(str(payload.get("transcript_path", "")))

    state = _load_state(_STATE_PATH)
    session_state = state.get(session_id)
    if not isinstance(session_state, dict):
        session_state = {}

    compact_count = int(session_state.get("compact_count", 0) or 0)
    compact_warned = bool(session_state.get("compact_warned", False))
    last_warned_tokens = int(session_state.get("last_warned_tokens", 0) or 0)

    warn_tokens = _int_env("CLAUDE_MONITOR_WARN_TOKENS", 150_000)
    high_tokens = _int_env("CLAUDE_MONITOR_HIGH_TOKENS", 180_000)

    messages: list[str] = []
    changed = False

    # compact_count は checkpoint_before_compact.py(PreCompact)が加算する
    # 二次指標。圧縮直後は使用量が下がって見えるため、水準に関わらず1回警告する
    if compact_count >= 2 and not compact_warned:
        messages.append(_COMPACT_MESSAGE.format(compact_count=compact_count))
        session_state["compact_warned"] = True
        changed = True

    if usage_tokens >= warn_tokens and (
        last_warned_tokens == 0 or usage_tokens >= last_warned_tokens * 1.10
    ):
        if usage_tokens >= high_tokens:
            messages.append(_HIGH_MESSAGE.format(tokens=usage_tokens))
        else:
            messages.append(_WARN_MESSAGE.format(tokens=usage_tokens))
        session_state["last_warned_tokens"] = usage_tokens
        changed = True

    if changed:
        state[session_id] = session_state
        _save_state(_STATE_PATH, state)

    if messages:
        text = "\n".join(messages)
        # systemMessage が表示されない実機構成に備え、stderr にも同文を出す
        print(json.dumps({"systemMessage": text}, ensure_ascii=False))
        print(text, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
