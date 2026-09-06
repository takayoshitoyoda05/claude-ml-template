#!/usr/bin/env python3
"""PreToolUse(matcher "Edit|Write|NotebookEdit"): `.claude/state/<slug>.json` への
書き込み前にスキーマを検証する(SKILL.state 部分採用。設計書 §4.5)。

検証対象は「現在のブランチに対応する状態ファイル」だけに絞る
(`.claude/state/<現在ブランチの slug>.json`)。ブランチ名からの状態ファイル
パス導出は `plan_gate._slug_from_branch` の import で行う
(reinject_after_compact.py・resume_session_state.py と同じ規約。正規表現の
複製禁止)。ブランチ取得(`_current_branch`)・検証本体(`_validate_state`)は
`_state_common` から import する(reinject_after_compact.py・
resume_session_state.py と共有。複製禁止)。他ブランチ・他worktree由来と
思われる `.claude/state/*.json` はこのフックの対象外として通す
(PC-6「配下でなければ通す」の拡張)。

ブランチ取得・状態パス導出・対象パス判定は全て「実効 cwd」
(ペイロードの `cwd` があればそれ、無ければプロセス cwd。guard_scope.py と
同じ規約)基準に統一する。プロセス cwd とペイロード cwd が食い違うケース
(例: 別 worktree からの呼び出し)で検証がスキップされるのを防ぐため。

検証規則: 必須キー存在+型+enum値+未知キー拒否(未知キー拒否は論文の
「状態キーの偶発上書き」対策。設計書2節参照)。Edit の場合は old_string の
一意置換のみを想定し、置換結果を再現できない場合(ファイルが読めない・
old_string が1回だけ現れない等)は fail-open で通す(PC-7)。

内部で予期せぬ例外が起きた場合も fail-open とする(PC-5)。
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_gate import _slug_from_branch  # noqa: E402
from _state_common import _current_branch, _validate_state  # noqa: E402


def _expected_state_path(effective_cwd: str) -> str | None:
    """`effective_cwd` 基準で、現在のブランチに対応する状態ファイルの絶対パス
    (スラッシュ区切り)を返す。

    現在ブランチが特定できない場合は None(対象を特定できないため fail-open)。
    """
    branch = _current_branch(effective_cwd)
    if not branch:
        return None
    slug = _slug_from_branch(branch)
    path = os.path.join(effective_cwd, ".claude", "state", f"{slug}.json")
    return os.path.abspath(path).replace("\\", "/")


def _effective_cwd(data: dict) -> str:
    """ペイロードの cwd を検証して採用する(guard_scope.py と同じ規約)。"""
    cwd = data.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return cwd
    return os.getcwd()


def _resulting_content(tool_name: str, tool_input: dict, abs_path: str) -> str | None:
    """Write/Edit 適用後の本文を返す。再現できない場合は None(fail-open, PC-7)。"""
    if tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None

    old_string = tool_input.get("old_string")
    new_string = tool_input.get("new_string", "")
    if not isinstance(old_string, str) or not isinstance(new_string, str):
        return None
    try:
        current = Path(abs_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if tool_input.get("replace_all"):
        if old_string not in current:
            return None
        return current.replace(old_string, new_string)
    if current.count(old_string) != 1:
        return None
    return current.replace(old_string, new_string, 1)


def _run() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if not isinstance(data, dict):
        return

    tool_name = data.get("tool_name")
    if tool_name not in ("Write", "Edit"):
        return
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return

    effective_cwd = _effective_cwd(data)
    abs_path = os.path.abspath(os.path.join(effective_cwd, file_path))
    norm_path = abs_path.replace("\\", "/")

    if "/.claude/state/" not in norm_path or not norm_path.endswith(".json"):
        return  # PC-6: 対象外のパスは内容を問わず通す

    expected = _expected_state_path(effective_cwd)
    if expected is None or norm_path != expected:
        return  # 現在ブランチの状態ファイルでなければ対象外(PC-6 の拡張)

    content = _resulting_content(tool_name, tool_input, abs_path)
    if content is None:
        return  # 適用結果を再現できない(PC-7): fail-open

    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        print(
            "[state_gate] BLOCKED: 状態ファイルの内容が JSON として解釈できません。",
            file=sys.stderr,
        )
        sys.exit(2)

    reason = _validate_state(obj)
    if reason is not None:
        print(f"[state_gate] BLOCKED: {reason}", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    try:
        _run()
    except Exception:
        # fail-open: 検証処理内部の予期せぬ例外で書き込みを妨げない(PC-5)
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
