#!/usr/bin/env python3
"""PreToolUse(matcher "Read"): data/ 配下の読み取りを NO_READ実効時に遮断する。

判定はプロファイル解決(CLAUDE_DATA_PROFILE)と個別変数
(CLAUDE_DATA_NO_READ)の組み合わせで決まる。個別変数が非空ならプロファイルより
優先する。値は "1"(data/全体)または data/直下のサブディレクトリ名の
カンマ区切り("raw,processed" 等)。sensitive プロファイルは "1" 相当、
internal・public・空は無効。

data/synthetic/・data/exports/・data/data.lock・data/.backup_stamp は
遮断対象外(data_gate.py と同じ除外規約。合成サンプル・正規の持ち出し
経路・ロック/バックアップ管理用メタファイルのため)。

`.claude/spec/data_unlock.txt`(CLAUDE_SPEC_DIR配下)に有効期限内の UTC
epoch秒が記録されていれば一時的に許可する(`.claude/hooks/data_unlock.py`
がユーザー `!` 実行専用で書く)。読めない・解釈できない・期限切れの記録は
すべて「解除されていない」として扱う(遮断の目的上、ここだけはfail-closed側)。

相対パスの解決はペイロードの cwd を優先する(guard_scope.py と同じ規約。
Read ツールの tool_input.file_path は相対/絶対の明示が無いため)。
"""

import json
import os
import sys
import time
from pathlib import Path

from _common import resolve_spec_dir

# data_gate.py にも同じ除外規約を同梱する(意図的な重複。hooks自己完結原則 R-022。
# PC-13 が両者の実効結果の一致を固定する)。
_EXCLUDED_DATA_PREFIXES = ("synthetic/", "exports/")
_EXCLUDED_DATA_FILES = ("data.lock", ".backup_stamp")


def resolve_no_read_value() -> str:
    """CLAUDE_DATA_NO_READ(個別)を優先し、無ければ CLAUDE_DATA_PROFILE から解決する。

    Returns:
        "" (無効) / "0" (無効) / "1" (data/ 全体) /
        data/ 直下のサブディレクトリ名のカンマ区切り、のいずれか。
    """
    individual = os.environ.get("CLAUDE_DATA_NO_READ", "").strip()
    if individual:
        return individual
    profile = os.environ.get("CLAUDE_DATA_PROFILE", "").strip().lower()
    if profile == "sensitive":
        return "1"
    return ""


def _unlock_active() -> bool:
    """一時解除の記録が有効期限内なら True(壊れている・無い・期限切れは False)。"""
    spec_dir = resolve_spec_dir()
    unlock_file = Path(spec_dir) / "data_unlock.txt"
    if not unlock_file.exists():
        return False
    try:
        content = unlock_file.read_text(encoding="utf-8").strip()
        expiry = int(content)
    except (OSError, UnicodeError, ValueError):
        return False
    return expiry > int(time.time())


def _effective_cwd(data: dict[str, object]) -> str:
    """ペイロードの cwd を検証して採用する(guard_scope.py と同じ規約)。"""
    try:
        cwd = data.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return cwd
    except Exception:
        pass
    return os.getcwd()


def _rel_after_data(norm_path: str) -> str | None:
    """絶対パス(スラッシュ区切り)の data/ 配下の相対部分を返す(配下でなければ None)。"""
    idx = norm_path.rfind("/data/")
    if idx != -1:
        return norm_path[idx + len("/data/") :]
    if norm_path.startswith("data/"):
        return norm_path[len("data/") :]
    return None


def _is_excluded_data_rel(rel: str) -> bool:
    """data_gate.py と同じ除外規約(synthetic/・exports/・data.lock・.backup_stamp)。"""
    if rel.startswith(_EXCLUDED_DATA_PREFIXES):
        return True
    return rel in _EXCLUDED_DATA_FILES


def _no_read_blocks_rel(rel: str, no_read_value: str) -> bool:
    """NO_READ実効値がこの相対パスを遮断対象にするなら True。"""
    if no_read_value in ("", "0"):
        return False
    if no_read_value == "1":
        return True
    subdirs = {s.strip() for s in no_read_value.split(",") if s.strip()}
    return rel.split("/", 1)[0] in subdirs


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        sys.exit(0)
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    effective_cwd = _effective_cwd(data)
    abs_path = os.path.abspath(os.path.join(effective_cwd, file_path))
    norm = abs_path.replace("\\", "/")

    rel = _rel_after_data(norm)
    if rel is None or _is_excluded_data_rel(rel):
        sys.exit(0)

    no_read_value = resolve_no_read_value()
    if not _no_read_blocks_rel(rel, no_read_value):
        sys.exit(0)

    if _unlock_active():
        print(
            "[data_read_gate] 一時解除が有効なため data/ の読み取りを許可します"
            "(期限内)。",
            file=sys.stderr,
        )
        sys.exit(0)

    print(
        f"[data_read_gate] BLOCKED: data/ 配下の読み取りは遮断されています: {file_path}\n"
        f"統計量だけが必要なら `uv run python scripts/data_summary.py <path>`"
        f"(窓口)を使ってください。個票が必要な場合はユーザーに"
        f" `! uv run python .claude/hooks/data_unlock.py [--minutes N]` "
        f"の実行を依頼してください(既定30分・上限240分)。",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
