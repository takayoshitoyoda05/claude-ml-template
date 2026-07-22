#!/usr/bin/env python3
"""Stop フック: CLAUDE_CROSS_REVIEW=1 のとき、Codexクロスレビューを
完了していなければブロックする。

センチネルはプロジェクト配下(.claude/checkpoints/codex_review_done.txt)に
置き、中身に「レビュー時点の HEAD ハッシュ」を要求する。通過条件は
「HEAD がセンチネルと一致」かつ「作業ツリーに未コミットの変更がない
(staged / unstaged / 未追跡ファイルすべてを含む。gitignore 済みは除く)」。
- HEAD が一致する限りセンチネルは保持される(同じコミットに対する
  再レビューを要求しない)
- レビュー後にファイルを変更・追加すると、コミットするまでブロックされる
  (コミットすると HEAD が進み、古いセンチネルは破棄→再レビュー要求)
- git で照合できない場合は安全側に倒してブロックする
- 未追跡の検査は --untracked-files=all を明示し、ユーザーの git 設定
  (status.showUntrackedFiles=no)に影響されないようにする
中身の照合はエージェント自身による偽装を完全には防げない(HEAD は
計算可能)が、cross-review スキルを経由せず偶然通過することはなくなる。
"""

import os
import subprocess
import sys

SENTINEL = os.path.join(".claude", "checkpoints", "codex_review_done.txt")


def current_head():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def worktree_clean():
    """作業ツリーに未コミットの変更が無ければ True。

    staged / unstaged / 未追跡ファイルすべてを対象にする(未追跡を除外すると
    新規ファイル中心の実装がレビューを通らずに完了できてしまうため)。
    --untracked-files=all を明示し、status.showUntrackedFiles=no の環境でも
    未追跡ファイルを見逃さない。gitignore 済みのファイルは対象外。
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() == ""


def block(detail):
    print(
        detail + "先に cross-review スキルを実行してください。\n"
        "  方法: 「クロスレビューして」または「@cross-review を実行して」\n"
        "  スキップしたい場合は CLAUDE_CROSS_REVIEW を 0 に変更してください。",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    if os.environ.get("CLAUDE_CROSS_REVIEW", "") != "1":
        sys.exit(0)

    recorded = None
    if os.path.exists(SENTINEL):
        try:
            # utf-8-sig: PowerShell の Out-File -Encoding utf8 が付ける BOM を許容
            with open(SENTINEL, encoding="utf-8-sig") as f:
                recorded = f.read().strip()
        except OSError:
            recorded = None

    if not recorded:
        block("[codex_gate] Codex クロスレビューがまだ実行されていません。\n")

    head = current_head()
    if head is None:
        # 照合できない状態で通すとセンチネルが永続 fail-open になるためブロック
        block(
            "[codex_gate] git で HEAD を取得できず、レビュー記録を照合できません。\n"
            "git リポジトリ内で実行しているか確認してください。\n"
        )

    if recorded != head:
        # 古い HEAD のセンチネルは無効なので破棄してから再レビューを要求する
        try:
            os.remove(SENTINEL)
        except OSError:
            pass
        block(
            "[codex_gate] センチネルの HEAD が現在と一致しません"
            "(レビュー後にコミットが進んでいます)。\n"
        )

    clean = worktree_clean()
    if clean is not True:
        # 未コミット変更(未追跡含む)はレビューを通っていない
        block(
            "[codex_gate] レビュー後の未コミット変更(未追跡ファイル含む)があります"
            "(または作業ツリーの状態を確認できません)。\n"
            "コミットしてから再レビューしてください。\n"
        )

    # HEAD 一致かつクリーン: レビュー済みのまま通過(センチネルは保持)
    sys.exit(0)


if __name__ == "__main__":
    main()
