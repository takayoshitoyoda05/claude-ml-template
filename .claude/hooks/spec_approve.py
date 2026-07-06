#!/usr/bin/env python3
"""ユーザーが `!` で手動実行する承認スクリプト。

- `! uv run python .claude/hooks/spec_approve.py R-003`
  manual要件を承認済みとして .claude/spec/approvals.txt に記録する。
  あわせて、その要件を含む設計書の現在のハッシュを design_hashes.txt に
  記録する(ユーザーが承認時点で見ていた設計書内容を確定させるため)。
- `! uv run python .claude/hooks/spec_approve.py --design <設計書名>`
  設計書(docs/active/<設計書名>.md)の計画承認としてハッシュのみ記録する
  (manual要件を持たない設計書用)。spec_gate は記録済みハッシュと現在の
  設計書内容を照合し、未承認・承認後の改変をブロックする。

Claude 経由の Edit/Write・リダイレクト・tee・cp/mv 等による approvals.txt /
design_hashes.txt への書き込みは guard_scope.py / guard_bash.py が
PROTECTED_PATH_PATTERNS でブロックし、このスクリプト自体の実行も guard_bash.py
がブロックする(コマンド文字列に spec_approve が含まれたら拒否)。ユーザーの
`!` 実行は PreToolUse フックを通らないため、この記録はユーザーの手動実行での
み可能(承認偽装の物理的な防止)。
"""
import argparse
import datetime
import sys

from _common import (
    AcceptanceTableError,
    design_file_sha256,
    parse_acceptance_table,
    resolve_docs_dir,
    resolve_spec_dir,
)


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


def record_design_hash(spec_dir, docs_dir, design_name, timestamp):
    """設計書の現在内容の sha256 を design_hashes.txt に追記する(後勝ち=最新承認)。"""
    design_file = docs_dir / f"{design_name}.md"
    digest = design_file_sha256(design_file)
    spec_dir.mkdir(parents=True, exist_ok=True)
    hashes_file = spec_dir / "design_hashes.txt"
    with hashes_file.open("a", encoding="utf-8") as f:
        f.write(f"{design_name} {digest} {timestamp}\n")
    return hashes_file


def main():
    parser = argparse.ArgumentParser(
        description="manual要件の承認/設計書の計画承認(ハッシュ記録)を行う"
    )
    parser.add_argument("req_id", nargs="?", help="承認する要件ID(例: R-003)")
    parser.add_argument(
        "--design",
        help="設計書名(docs/active/<名前>.md の名前部分)。計画承認としてハッシュのみ記録する",
    )
    parser.add_argument("--docs", help="設計書ディレクトリの上書き(テスト用)")
    parser.add_argument("--spec-dir", help="状態ディレクトリの上書き(テスト用)")
    args = parser.parse_args()

    if not args.req_id and not args.design:
        parser.error("要件ID または --design <設計書名> のいずれかを指定してください")

    docs_dir = resolve_docs_dir(args.docs)
    spec_dir = resolve_spec_dir(args.spec_dir)
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")

    if args.design:
        design_name = args.design.removesuffix(".md")
        if not (docs_dir / f"{design_name}.md").exists():
            print(
                f"[spec_approve] エラー: 設計書 {docs_dir / (design_name + '.md')} が"
                f"見つかりません。",
                file=sys.stderr,
            )
            sys.exit(1)
        hashes_file = record_design_hash(spec_dir, docs_dir, design_name, timestamp)
        print(
            f"OK: 設計書 '{design_name}' の現在内容を計画承認として"
            f"記録しました({hashes_file})"
        )

    if args.req_id:
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
        with approvals_file.open("a", encoding="utf-8") as f:
            f.write(f"{design_name} {args.req_id} {timestamp}\n")
        # 要件承認はその設計書内容を見た上での判断なので、設計書ハッシュも更新する
        record_design_hash(spec_dir, docs_dir, design_name, timestamp)

        print(
            f"OK: 設計書 '{design_name}' の {args.req_id} を承認済みとして"
            f"記録しました({approvals_file})"
        )


if __name__ == "__main__":
    main()
