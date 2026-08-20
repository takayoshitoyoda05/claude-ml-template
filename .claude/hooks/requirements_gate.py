#!/usr/bin/env python3
"""PreToolUse (Edit|Write|NotebookEdit): 計画ファイルの作成前に、
受け入れ条件テーブル付きの設計書が存在することを機械検査する。

CLAUDE_REQUIREMENTS_GATE=1 のときだけ動作する。/ml-pipeline の手順0.5
(要件ヒアリング)が生成する設計書(docs/active/ または docs/drafts/)が
無いまま planner が計画(.claude/plans/*.md)を書き始めるのをブロックする
(手順0.5 はプロンプト指示であり、それ自体に強制力が無いことへの補助線)。

検査は「有効な受け入れ条件テーブルを持つ設計書が1つ以上あるか」のみ。
テーブルの中身の妥当性は spec-checklist(手順3.3)と spec_gate
(CLAUDE_SPEC_CHECK=1)が担う(責務の重複を避ける)。

テスト容易性のため、検査対象ディレクトリは環境変数 CLAUDE_REQ_DOCS
(os.pathsep 区切りの複数ディレクトリ)で上書きできる。
"""
import json
import os
import sys
from pathlib import Path

from _common import AcceptanceTableError, parse_acceptance_table


def docs_dirs() -> list[Path]:
    """検査対象の設計書ディレクトリ一覧を解決する。

    優先順位: CLAUDE_REQ_DOCS(テスト用上書き) >
    CLAUDE_WORK_SCOPE 配下 > カレントディレクトリの docs/active・docs/drafts。

    Returns:
        検査対象ディレクトリのリスト(存在確認は呼び出し側で行う)。
    """
    env = os.environ.get("CLAUDE_REQ_DOCS", "").strip()
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p.strip()]
    work_scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    base = Path(work_scope) if work_scope else Path.cwd()
    return [base / "docs" / "active", base / "docs" / "drafts"]


def has_acceptance_design(dirs: list[Path]) -> bool:
    """有効な受け入れ条件テーブルを持つ設計書が1つでもあるか調べる。

    Args:
        dirs: 検査対象ディレクトリのリスト。

    Returns:
        1件でも見つかれば True。読めない・不正なファイルは黙って飛ばす
        (不正テーブルの詳細指摘は spec-checklist / spec_gate の責務)。
    """
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            try:
                if parse_acceptance_table(text):
                    return True
            except AcceptanceTableError:
                continue
    return False


def is_plan_path(raw: str) -> bool:
    """書き込み先が計画ファイル(.claude/plans/*.md)かを判定する。

    Args:
        raw: ツール入力の file_path(絶対・相対、区切りは / と \\ の両方)。

    Returns:
        計画ファイルなら True。
    """
    if not raw:
        return False
    norm = raw.replace("\\", "/")
    return norm.endswith(".md") and ".claude/plans/" in norm


def main() -> None:
    if os.environ.get("CLAUDE_REQUIREMENTS_GATE", "") != "1":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # ペイロード不明での過剰ブロックはしない(補助線)
    tool_input = data.get("tool_input") or {}
    raw = str(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    if not is_plan_path(raw):
        sys.exit(0)
    if has_acceptance_design(docs_dirs()):
        sys.exit(0)
    print(
        "[requirements_gate] BLOCKED: 受け入れ条件テーブル付きの設計書が"
        " docs/active/・docs/drafts/ に1つもありません。\n"
        "計画を書く前に /ml-pipeline 手順0.5(要件ヒアリング)を実施し、"
        "design-interview で受け入れ条件テーブル付きの設計書を生成してください。\n"
        "このゲートを無効にする場合は CLAUDE_REQUIREMENTS_GATE を 0 にします。",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
