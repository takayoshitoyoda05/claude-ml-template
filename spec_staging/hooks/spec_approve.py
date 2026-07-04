#!/usr/bin/env python3
"""ユーザーが `! uv run python .claude/hooks/spec_approve.py R-003` の形で
実行し、manual要件を承認済みとして .claude/spec/approvals.txt に記録する。

Claude 経由の Edit/Write・リダイレクト・tee による approvals.txt への書き込みは
guard_scope.py / guard_bash.py が PROTECTED_PATH_PATTERNS でブロックするため、
この記録はユーザーの `!` 手動実行でのみ可能(承認偽装の物理的な防止)。
"""
import argparse
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AcceptanceTableError, parse_acceptance_table  # noqa: E402


def resolve_docs_dir(explicit):
    if explicit:
        return Path(explicit)
    env_docs = os.environ.get("CLAUDE_SPEC_DOCS", "").strip()
    if env_docs:
        return Path(env_docs)
    work_scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    if work_scope:
        return Path(work_scope) / "docs" / "active"
    return Path("docs") / "active"


def resolve_spec_dir(explicit):
    if explicit:
        return Path(explicit)
    env_spec = os.environ.get("CLAUDE_SPEC_DIR", "").strip()
    if env_spec:
        return Path(env_spec)
    work_scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    if work_scope:
        return Path(work_scope) / ".claude" / "spec"
    return Path(".claude") / "spec"


def find_design_for_id(docs_dir, req_id):
    """req_id を含む設計書を探し、その stem(拡張子抜きファイル名)を返す。"""
    if not docs_dir.exists():
        return None
    for f in sorted(docs_dir.glob("*.md")):
        try:
            rows = parse_acceptance_table(f.read_text(encoding="utf-8"))
        except AcceptanceTableError:
            continue
        for row in rows:
            if row["id"] == req_id:
                return f.stem
    return None


def main():
    parser = argparse.ArgumentParser(
        description="manual要件を承認済みとして approvals.txt に記録する"
    )
    parser.add_argument("req_id", help="承認する要件ID(例: R-003)")
    parser.add_argument("--docs", help="設計書ディレクトリの上書き(テスト用)")
    parser.add_argument("--spec-dir", help="状態ディレクトリの上書き(テスト用)")
    args = parser.parse_args()

    docs_dir = resolve_docs_dir(args.docs)
    spec_dir = resolve_spec_dir(args.spec_dir)

    design_name = find_design_for_id(docs_dir, args.req_id)
    if design_name is None:
        print(
            f"[spec_approve] エラー: {docs_dir} 配下の設計書に要件ID {args.req_id} が"
            f"見つかりません。",
            file=sys.stderr,
        )
        sys.exit(1)

    spec_dir.mkdir(parents=True, exist_ok=True)
    approvals_file = spec_dir / "approvals.txt"
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    with approvals_file.open("a", encoding="utf-8") as f:
        f.write(f"{design_name} {args.req_id} {timestamp}\n")

    print(
        f"OK: 設計書 '{design_name}' の {args.req_id} を承認済みとして"
        f"記録しました({approvals_file})"
    )


if __name__ == "__main__":
    main()
