#!/usr/bin/env python3
"""PreToolUse(matcher "Edit|Write|NotebookEdit"): `.claude/state/<slug>.json` への
書き込み前にスキーマを検証する(SKILL.state 部分採用。設計書 §4.5)。

検証対象は「現在のブランチに対応する状態ファイル」だけに絞る
(`.claude/state/<現在ブランチの slug>.json`)。ブランチ名からの状態ファイル
パス導出は `plan_gate._slug_from_branch` の import で行う
(reinject_after_compact.py・resume_session_state.py と同じ規約。正規表現の
複製禁止)。他ブランチ・他worktree由来と思われる `.claude/state/*.json` は
このフックの対象外として通す(PC-6「配下でなければ通す」の拡張)。

検証規則: 必須キー存在+型+enum値+未知キー拒否(未知キー拒否は論文の
「状態キーの偶発上書き」対策。設計書2節参照)。Edit の場合は old_string の
一意置換のみを想定し、置換結果を再現できない場合(ファイルが読めない・
old_string が1回だけ現れない等)は fail-open で通す(PC-7)。

内部で予期せぬ例外が起きた場合も fail-open とする(PC-5)。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_gate import _slug_from_branch  # noqa: E402

NOTES_MAX_CHARS = 500

_REQUIRED_KEYS = {
    "schema_version", "branch", "task_summary", "size", "current_step",
    "gates", "open_findings", "artifacts", "next_action", "notes", "updated_at",
}
_GATES_ENUM = {
    "spec_checklist": {"READY", "NEEDS_WORK"},
    "plan_premortem": {"PASS", "SEND_BACK"},
    "plan_approval": {"human", "auto"},
    "evaluator": {"PASS", "FAIL"},
    "final_gate": {"APPROVE", "SEND_BACK"},
}
_ARTIFACT_KEYS = {"plan", "design_doc", "report"}
_SIZE_ENUM = {"S", "M", "L"}


def _current_branch() -> str:
    """現在のブランチ名を返す。取得できなければ空文字列(resume_session_state.py と同じ規約)。"""
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


def _expected_state_path() -> str | None:
    """現在のブランチに対応する状態ファイルの絶対パス(スラッシュ区切り)を返す。

    現在ブランチが特定できない場合は None(対象を特定できないため fail-open)。
    """
    branch = _current_branch()
    if not branch:
        return None
    slug = _slug_from_branch(branch)
    path = os.path.join(".claude", "state", f"{slug}.json")
    return os.path.abspath(path).replace("\\", "/")


def _effective_cwd(data: dict) -> str:
    """ペイロードの cwd を検証して採用する(guard_scope.py と同じ規約)。"""
    cwd = data.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return cwd
    return os.getcwd()


def _validate_state(obj: object) -> str | None:
    """状態オブジェクトを検証する。違反理由(str)を返す。問題なければ None。"""
    if not isinstance(obj, dict):
        return "state はオブジェクトである必要があります"

    unknown = set(obj.keys()) - _REQUIRED_KEYS
    if unknown:
        return f"未知のキー: {', '.join(sorted(unknown))}"
    missing = _REQUIRED_KEYS - set(obj.keys())
    if missing:
        return f"必須キー欠落: {', '.join(sorted(missing))}"

    if not isinstance(obj["schema_version"], int) or isinstance(obj["schema_version"], bool):
        return "schema_version は整数である必要があります"
    for key in ("branch", "task_summary", "current_step", "next_action", "notes", "updated_at"):
        if not isinstance(obj[key], str):
            return f"{key} は文字列である必要があります"
    if obj["size"] not in _SIZE_ENUM:
        return f"size が不正な値です(値: {obj['size']!r})"
    if len(obj["notes"]) > NOTES_MAX_CHARS:
        return f"notes は{NOTES_MAX_CHARS}字以内である必要があります(現在{len(obj['notes'])}字)"

    gates = obj["gates"]
    if not isinstance(gates, dict):
        return "gates はオブジェクトである必要があります"
    unknown_gates = set(gates.keys()) - set(_GATES_ENUM)
    if unknown_gates:
        return f"gates に未知のキー: {', '.join(sorted(unknown_gates))}"
    missing_gates = set(_GATES_ENUM) - set(gates.keys())
    if missing_gates:
        return f"gates の必須キー欠落: {', '.join(sorted(missing_gates))}"
    for key, enum_values in _GATES_ENUM.items():
        value = gates[key]
        if value is not None and value not in enum_values:
            return f"gates.{key} が不正な値です(値: {value!r})"

    open_findings = obj["open_findings"]
    if not isinstance(open_findings, list) or any(
        not isinstance(item, str) for item in open_findings
    ):
        return "open_findings は文字列のリストである必要があります"

    artifacts = obj["artifacts"]
    if not isinstance(artifacts, dict):
        return "artifacts はオブジェクトである必要があります"
    unknown_artifacts = set(artifacts.keys()) - _ARTIFACT_KEYS
    if unknown_artifacts:
        return f"artifacts に未知のキー: {', '.join(sorted(unknown_artifacts))}"
    missing_artifacts = _ARTIFACT_KEYS - set(artifacts.keys())
    if missing_artifacts:
        return f"artifacts の必須キー欠落: {', '.join(sorted(missing_artifacts))}"
    for key in _ARTIFACT_KEYS:
        value = artifacts[key]
        if value is not None and not isinstance(value, str):
            return f"artifacts.{key} は文字列または null である必要があります"

    return None


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

    expected = _expected_state_path()
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
