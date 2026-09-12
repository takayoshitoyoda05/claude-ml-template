#!/usr/bin/env python3
"""PreToolUse(Edit|Write|NotebookEdit): Red で記録済みのテストファイルへの
編集を CLAUDE_TDD_GATE=1 の間ブロックする。

センチネル(`.claude/checkpoints/tdd_red.json`)は `tdd_red.py` が書く。
本フックはテストを実行しない(センチネル読取りとパス照合のみ)。

判定の基準が2つ異なることに注意(設計判断表):
- センチネル・ログのパスは、このフック自身の配置から求めたリポジトリ
  ルート基準(`Path(__file__).resolve().parents[2]`)で解決する。
- 編集対象パスは、PreToolUse ペイロードの `cwd`(無ければ `os.getcwd()`)
  基準で絶対化する(`guard_scope.py:111-128` と同じ規則)。

パス照合は両辺 realpath で行い、Windows のみ大文字小文字を無視する
(`_common.py:86-96` の `CASE_INSENSITIVE_FS` / `path_for_match()` と同じ規則。
本フックは `_common` を import できないため standalone で再実装する)。

センチネルが読めない・パースできない・必須キー欠落・型不正・`test_files` が
空の場合は fail-closed とし、対象ツールの**全パスの編集**をブロックする
(照合不能のため、どのパスが保護対象か判定できないため)。この場合も
例外は捕捉し、traceback を出さずにブロック理由と脱出路を案内する。

ブロックが起きるたびに `.claude/checkpoints/tdd_gate_blocks.log` に1行追記する
(効果測定・fail-closed の可視化のため)。
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINTS_DIR = REPO_ROOT / ".claude" / "checkpoints"
SENTINEL_PATH = CHECKPOINTS_DIR / "tdd_red.json"
BLOCKS_LOG_PATH = CHECKPOINTS_DIR / "tdd_gate_blocks.log"

_CASE_INSENSITIVE_FS = os.name == "nt"


def _path_for_match(path: str) -> str:
    return path.lower() if _CASE_INSENSITIVE_FS else path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_blocks_log(target: str, reason: str) -> None:
    try:
        CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(BLOCKS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{_utcnow_iso()} block {target} {reason}\n")
    except OSError:
        pass  # ログできなくてもブロック自体は行う(記録漏れのみの影響)


def _validate_sentinel(state: object) -> list[str] | None:
    """必須5キー・型・非空を検証する。不正なら None(fail-closed の合図)。"""
    if not isinstance(state, dict):
        return None
    for key in ("test_command", "recorded_cwd", "recorded_at", "log_path"):
        value = state.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
    test_files = state.get("test_files")
    if not isinstance(test_files, list) or not test_files:
        return None
    if not all(
        isinstance(f, str) and f.strip() and os.path.isabs(f) for f in test_files
    ):
        return None
    if not os.path.isabs(state["recorded_cwd"]):
        return None
    return test_files


_ESCAPE_ROUTES = (
    "次のいずれかで復帰してください:\n"
    "  1. 検証つき解除: uv run python .claude/hooks/tdd_unlock.py\n"
    "  2. Red やり直し: uv run python .claude/hooks/tdd_red.py --rearm\n"
    "  3. 緊急脱出: CLAUDE_TDD_GATE=0\n"
)


def _read_target(payload: object) -> tuple[str | None, str]:
    """ペイロードから編集対象の絶対パスと、ログ表示用の生パスを返す。

    読めない/欠落時は (None, "(不明)")(呼び出し側が fail-open/fail-closed を判断する)。
    """
    if not isinstance(payload, dict):
        return None, "(不明)"
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None, "(不明)"
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path or not isinstance(raw_path, str):
        return None, "(不明)"
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        cwd = os.getcwd()
    abs_path = os.path.abspath(os.path.join(cwd, raw_path))
    return abs_path, raw_path


def main() -> None:
    if os.environ.get("CLAUDE_TDD_GATE", "") != "1":
        sys.exit(0)
    if not SENTINEL_PATH.exists():
        sys.exit(0)

    try:
        raw = SENTINEL_PATH.read_text(encoding="utf-8-sig")
        state = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        state = None
    test_files = _validate_sentinel(state)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = None
    abs_path, raw_path = _read_target(payload)

    if test_files is None:
        # fail-closed: 照合不能のため対象ツールの全パスの編集を停止する
        _append_blocks_log(
            raw_path, "fail-closed: センチネルの照合に失敗したため全編集を停止中"
        )
        print(
            "[tdd_gate] BLOCKED: センチネルの照合に失敗したため、対象ツール"
            "(Edit/Write/NotebookEdit)の全編集を停止中です"
            "(照合不能のため全編集を停止中)。\n"
            "tdd_red.py で再記録してください。\n" + _ESCAPE_ROUTES,
            file=sys.stderr,
        )
        sys.exit(2)

    if abs_path is None:
        # ペイロードが読めない/対象パスが無い(素通り。センチネルは正常なので
        # fail-open で構わない。guard_scope.py と同じ考え方)
        sys.exit(0)

    target_norm = _path_for_match(os.path.realpath(abs_path).replace("\\", "/"))
    for recorded in test_files:
        recorded_norm = _path_for_match(os.path.realpath(recorded).replace("\\", "/"))
        if target_norm == recorded_norm:
            _append_blocks_log(raw_path, "Red で記録済みのテストファイルへの編集")
            print(
                "[tdd_gate] BLOCKED: Red で記録されたテストファイルの編集は"
                f"ブロックされています: {raw_path}\n" + _ESCAPE_ROUTES,
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
