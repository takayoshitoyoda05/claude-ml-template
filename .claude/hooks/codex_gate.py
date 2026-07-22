#!/usr/bin/env python3
"""Stop フック: CLAUDE_CROSS_REVIEW=1 のとき、Codexクロスレビューを
完了していなければブロックする。

センチネルはプロジェクト配下(.claude/checkpoints/codex_review_done.txt)に
置き、中身に「レビュー時点の HEAD ハッシュ」を要求する。通過条件は
「HEAD がセンチネルと一致」かつ「追跡ファイルに未コミットの変更がない」。
- HEAD が一致する限りセンチネルは保持される(同じコミットに対する
  再レビューを要求しない)
- レビュー後に追跡ファイルを変更すると、コミットするまでブロックされる
  (コミットすると HEAD が進み、古いセンチネルは破棄→再レビュー要求)
- git で照合できない場合は安全側に倒してブロックする
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


def tracked_tree_clean():
    """追跡ファイルに未コミットの変更(staged/unstaged)が無ければ True。

    未追跡ファイルは対象外(コミットに入る時点で HEAD が進み、
    その diff が次のレビュー対象になるため)。
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
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

    clean = tracked_tree_clean()
    if clean is not True:
        # 未コミット変更はレビューを通っていない(コミットして再レビューが必要)
        block(
            "[codex_gate] レビュー後の未コミット変更があります(または作業ツリーの"
            "状態を確認できません)。\nコミットしてから再レビューしてください。\n"
        )

    # HEAD 一致かつクリーン: レビュー済みのまま通過(センチネルは保持)
    sys.exit(0)


if __name__ == "__main__":
    main()
