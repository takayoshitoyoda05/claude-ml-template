#!/usr/bin/env python3
"""PreToolUse: Edit/Write/NotebookEdit のスコープ外・大容量ファイル・
秘密情報を含む書き込みをブロックする。

- 環境変数 CLAUDE_WORK_SCOPE があればそのパス配下のみ許可
- なければカレントディレクトリ配下を許可
- .pth / checkpoints/ / outputs/ / runs/ 等の生成物は常にブロック
- .env / credentials.json / 秘密鍵ファイルは常にブロック
- .claude/hooks/ と settings 系(ガード自身)への書き込みは常にブロック
- 書き込み内容にAPIキーらしき文字列が含まれる場合もブロック
- cwd が作業スコープ直下の .worktrees/<名前> 配下なら、書き込み先も同じ
  worktree 配下に限定する(worktree担当エージェントのメインリポジトリ
  誤書き込み防止)
"""

import json
import os
import re
import sys

from _common import (
    ARTIFACT_DIR_PATTERNS,
    ARTIFACT_EXTENSIONS,
    BLOCKED_EXTENSIONS,
    BLOCKED_FILENAMES,
    PROTECTED_PATH_PATTERNS,
    SECRET_CONTENT_PATTERNS,
    path_for_match,
)


def contains_secret(text):
    for pat in SECRET_CONTENT_PATTERNS:
        if re.search(pat, text):
            return True
    return False


def _is_path_within(target: str, root: str) -> bool:
    """target が root 配下(root 自身を含む)にあるかを判定する。

    前方一致の誤許可(root=/work/proj で /work/proj-evil が通る)を防ぐため
    双方に末尾スラッシュを付けて比較する。Windows は大文字小文字を
    区別しないので nt のときのみ小文字化して揃える。

    Args:
        target: 判定対象の絶対パス(スラッシュ区切り)。
        root: 基準ルートの絶対パス(スラッシュ区切り)。

    Returns:
        target が root 配下なら True。
    """
    root_cmp = root.rstrip("/") + "/"
    target_cmp = target.rstrip("/") + "/"
    if os.name == "nt":
        root_cmp = root_cmp.lower()
        target_cmp = target_cmp.lower()
    return target_cmp.startswith(root_cmp)


def _effective_cwd(data: dict[str, object]) -> str:
    """ペイロードの cwd を検証して採用する。

    Args:
        data: フックが stdin から受け取ったペイロード全体。

    Returns:
        ペイロードの cwd が非空文字列ならその値。それ以外(欠落・空・
        文字列以外・例外)は os.getcwd()(誤ブロックしない安全側)。
    """
    try:
        cwd = data.get("cwd")
        if isinstance(cwd, str) and cwd.strip():
            return cwd
    except Exception:
        pass
    return os.getcwd()


def _worktree_root(cwd: str, allowed_root: str) -> str | None:
    """cwd が作業スコープ直下の .worktrees/<名前> 配下なら worktree ルートを返す。

    任意の場所の .worktrees を worktree と誤認しないよう、判定は
    realpath(allowed_root)/.worktrees/ 直下に限定する。

    Args:
        cwd: 判定対象の cwd(_effective_cwd の返り値)。
        allowed_root: 作業スコープのルート(絶対パス)。

    Returns:
        worktree ルート(realpath 解決済み・スラッシュ区切り)。cwd が
        worktree 配下でない・判定不能・例外時は None(ゲート不活性 =
        誤ブロックしない安全側)。
    """
    try:
        cwd_norm = os.path.realpath(cwd).replace("\\", "/")
        base_norm = (
            os.path.realpath(allowed_root).replace("\\", "/").rstrip("/")
            + "/.worktrees/"
        )
        if not _is_path_within(cwd_norm, base_norm):
            return None
        name = cwd_norm[len(base_norm) :].split("/", 1)[0]
        if not name:
            return None
        return base_norm + name
    except Exception:
        return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "") or tool_input.get("notebook_path", "")
    if not file_path:
        sys.exit(0)

    # 相対パスはペイロード cwd(無ければ os.getcwd())基準で解決する。
    # フックプロセスの cwd とツールが実際に書き込む基準(ペイロード cwd)は
    # 一致するとは限らないため。絶対パスは os.path.join が cwd を捨てるので
    # 従来と同じ結果になる。
    effective_cwd = _effective_cwd(data)
    abs_path = os.path.abspath(os.path.join(effective_cwd, file_path))
    norm = abs_path.replace("\\", "/")
    basename = os.path.basename(norm)
    _, ext = os.path.splitext(basename)

    if (
        path_for_match(basename) in BLOCKED_FILENAMES
        or ext.lower() in BLOCKED_EXTENSIONS
    ):
        print(
            f"[guard_scope] BLOCKED: 秘密情報ファイルの可能性がある書き込みです: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    # 末尾に "/" を足してから比較する。ディレクトリを末尾スラッシュなしで
    # 指定した場合でも PROTECTED_PATH_PATTERNS の "/.claude/hooks/" と
    # 一致させるため(ファイルパターンは元々末尾スラッシュなしなので影響しない)。
    if any(pat in path_for_match(norm) + "/" for pat in PROTECTED_PATH_PATTERNS):
        print(
            f"[guard_scope] BLOCKED: フック/設定(ガード自身)への書き込みは禁止です: {file_path}\n"
            f"変更が必要な場合はユーザーが手動で編集してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    content = (
        tool_input.get("content", "")
        or tool_input.get("new_string", "")
        or tool_input.get("new_source", "")
    )
    if content and contains_secret(content):
        print(
            f"[guard_scope] BLOCKED: 書き込み内容に秘密情報らしき文字列が含まれています: {file_path}\n"
            f"APIキーや秘密鍵は環境変数や .gitignore 対象の設定ファイルで管理してください。",
            file=sys.stderr,
        )
        sys.exit(2)

    if ext.lower() in ARTIFACT_EXTENSIONS or any(
        pat in path_for_match(norm) for pat in ARTIFACT_DIR_PATTERNS
    ):
        print(
            f"[guard_scope] BLOCKED: 生成物/大容量ファイルへの書き込みは禁止です: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    scope = os.environ.get("CLAUDE_WORK_SCOPE", "").strip()
    if scope:
        allowed_root = os.path.abspath(scope)
    else:
        allowed_root = os.path.abspath(os.getcwd())

    if not _is_path_within(norm, allowed_root.replace("\\", "/")):
        print(
            f"[guard_scope] BLOCKED: 作業スコープ({allowed_root})外への書き込みです: {file_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    # worktree 担当の cwd がスコープ直下の .worktrees/<名前> 配下なら、
    # 書き込み先も同じ worktree 配下に限定する(メインリポジトリ本体への
    # 誤書き込み防止)。symlink 迂回を塞ぐため両辺とも realpath で解決する。
    worktree_root = _worktree_root(effective_cwd, allowed_root)
    if worktree_root:
        target_realpath = os.path.realpath(abs_path).replace("\\", "/")
        if not _is_path_within(target_realpath, worktree_root):
            print(
                f"[guard_scope] BLOCKED: worktree({worktree_root})外への書き込みです: {file_path}\n"
                f"worktree担当はメインリポジトリ本体を直接変更できません。",
                file=sys.stderr,
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
