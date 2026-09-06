#!/usr/bin/env python3
"""状態ファイル(`.claude/state/<slug>.json`)関連の共通ヘルパー。

state_gate.py・reinject_after_compact.py・resume_session_state.py の3フックが
`_current_branch` を個別に複製し、reinject_after_compact.py・
resume_session_state.py の2フックがさらに `_state_section` を複製していたのを
ここへ集約する(レビュー差し戻し対応。複製すると将来どれか1つだけ変更されて
ドリフトする恐れがあるため)。`_validate_state` とスキーマ定数群も
state_gate.py から移設し、`_state_section` から呼べるようにする
(Codex MEDIUM指摘対応: 読み込み側が未検証のままだった穴を塞ぐ)。

ブランチ名→slug変換自体(`plan_gate._slug_from_branch`)はこのモジュールでは
扱わない。呼び出し側が引き続き `plan_gate` から直接importして slug を
計算し、`_state_section` へ渡す(R-014の複製禁止対象=正規表現ベースの
slug導出はこれまで通り一本化されたまま)。
"""

import json
from pathlib import Path
import subprocess

_STATE_HEADING = "## 現在の実行状態(検証済み・これを正とする)"

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


def _current_branch(cwd: str | None = None) -> str:
    """現在のブランチ名を返す。取得できなければ空文字列。

    Args:
        cwd: git を実行する作業ディレクトリ。None なら現行の subprocess 既定
            (プロセス cwd)を使う(state_gate.py 以外の呼び出し元は引数無しの
            まま呼び、挙動は変わらない)。
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
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
    if not isinstance(obj["size"], str) or obj["size"] not in _SIZE_ENUM:
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
        if value is not None and (not isinstance(value, str) or value not in enum_values):
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


def _state_section(slug: str) -> tuple[str, str | None]:
    """状態ファイル(.claude/state/<slug>.json)の注入用セクションを組み立てる。

    reinject_after_compact.py・resume_session_state.py で共通の3分岐
    (ok / broken / missing_with_plan / silent。設計書 R-010、
    ユーザー決定 2026-09-04)。branch が特定できない(= slug を渡せない)場合の
    "silent" 分岐は呼び出し側の責務(このモジュールは slug 計算後の状態のみ扱う)。
    JSON として読めてもスキーマ違反なら "broken" として扱う(R-003: 未検証の
    ままだと「検証済み・これを正とする」見出しが偽になる)。

    Returns:
        (status, section_text) の組。"ok" のときのみ section_text が非 None。
    """
    state_path = Path(".claude/state") / f"{slug}.json"
    if state_path.exists():
        try:
            content = state_path.read_text(encoding="utf-8")
            obj = json.loads(content)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            return "broken", None
        if _validate_state(obj) is not None:
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
