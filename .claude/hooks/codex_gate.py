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

再発火の抑制(2026-09-07 追加):
- 同一状態抑制: ブロックするとき (種別 + HEAD + status出力) の指紋を
  .claude/checkpoints/codex_gate_last_block.txt に記録し、前回ブロック時と
  同一指紋なら警告を繰り返さず通す(状態ごとに警告1回。並列実装の待機
  ターンで同一警告が数十回連続発火した事象への対策)。状態が変われば
  再びブロックし、正常通過時は指紋を破棄する
- 一時停止: .claude/checkpoints/codex_gate_pause が存在すれば無条件で通す。
  このファイルはユーザーが `!` 実行(touch/rm)でのみ操作する。
  エージェントによる作成は禁止(センチネルと同じ規律。このゲートの
  脅威モデルは「偶然の素通り防止」であり偽装への完全耐性は non-goal)

中身の照合はエージェント自身による偽装を完全には防げない(HEAD は
計算可能)が、cross-review スキルを経由せず偶然通過することはなくなる。
"""

import hashlib
import os
import subprocess
import sys

SENTINEL = os.path.join(".claude", "checkpoints", "codex_review_done.txt")
LAST_BLOCK = os.path.join(".claude", "checkpoints", "codex_gate_last_block.txt")
PAUSE_FILE = os.path.join(".claude", "checkpoints", "codex_gate_pause")


def current_head():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def worktree_status():
    """git status --porcelain の生出力を返す(取得不能なら None)。

    staged / unstaged / 未追跡ファイルすべてを対象にする(未追跡を除外すると
    新規ファイル中心の実装がレビューを通らずに完了できてしまうため)。
    --untracked-files=all を明示し、status.showUntrackedFiles=no の環境でも
    未追跡ファイルを見逃さない。gitignore 済みのファイルは対象外。
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    # ゲート自身の記録(.claude/checkpoints/ 配下: センチネル・抑制指紋・
    # 一時停止ファイル)は「レビューすべき変更」ではないため状態から除外する。
    # 実リポジトリでは gitignore 済みでそもそも現れないが、除外を明示することで
    # 指紋の安定性(自分の書き込みで状態が変わる自己言及)を環境に依存させない。
    # 除外は untracked(`?? `)行に限定する: checkpoints は gitignore 前提で
    # 追跡されないため rename 表記(`R  a -> b`)には現れず、追跡済みの
    # checkpoints 変更という異常系はあえて dirty 扱いのままにする(安全側)
    lines = [
        line
        for line in result.stdout.splitlines()
        if not (
            line.startswith("?? ")
            and line[3:].strip().strip('"').startswith(".claude/checkpoints/")
        )
    ]
    return "\n".join(lines)


def _fingerprint(kind, head, status_output):
    material = "\n".join([kind, head or "(no-head)", status_output or "(no-status)"])
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _read_last_block():
    try:
        with open(LAST_BLOCK, encoding="utf-8-sig") as f:
            return f.read().strip()
    except (OSError, UnicodeError):
        # UnicodeDecodeError は OSError で捕まらない(python-style.md の契約)。
        # 読めない指紋は記録なしとして扱う(=ブロック側へ倒れる安全側)
        return None


def _write_last_block(fingerprint):
    try:
        os.makedirs(os.path.dirname(LAST_BLOCK), exist_ok=True)
        with open(LAST_BLOCK, "w", encoding="utf-8") as f:
            f.write(fingerprint + "\n")
    except OSError:
        pass  # 記録できなくてもブロック自体は行う(抑制が効かないだけ)


def _clear_last_block():
    try:
        os.remove(LAST_BLOCK)
    except OSError:
        pass


def block(kind, head, status_output, detail):
    """同一状態なら黙って通し、新しい状態なら指紋を記録してブロックする。"""
    fingerprint = _fingerprint(kind, head, status_output)
    if _read_last_block() == fingerprint:
        # 前回ブロック時から状態が変わっていない(待機ターンの再発火)。
        # 警告は状態ごとに1回で十分なので繰り返さない
        sys.exit(0)
    _write_last_block(fingerprint)
    print(
        detail + "先に cross-review スキルを実行してください。\n"
        "  方法: 「クロスレビューして」または「@cross-review を実行して」\n"
        "  スキップしたい場合は CLAUDE_CROSS_REVIEW を 0 に変更してください。\n"
        "  (同一状態のままなら次回以降この警告は抑制されます。長時間の待機は\n"
        "   ユーザーの `! touch .claude/checkpoints/codex_gate_pause` で一時停止できます)",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    if os.environ.get("CLAUDE_CROSS_REVIEW", "") != "1":
        sys.exit(0)

    if os.path.exists(PAUSE_FILE):
        # ユーザーによる一時停止(削除で再開)。エージェントは作成しない規律
        sys.exit(0)

    head = current_head()
    status_output = worktree_status()

    recorded = None
    if os.path.exists(SENTINEL):
        try:
            # utf-8-sig: PowerShell の Out-File -Encoding utf8 が付ける BOM を許容
            with open(SENTINEL, encoding="utf-8-sig") as f:
                recorded = f.read().strip()
        except (OSError, UnicodeError):
            # UnicodeDecodeError は OSError で捕まらない(python-style.md の契約)
            recorded = None

    if not recorded:
        block("no_sentinel", head, status_output, "[codex_gate] Codex クロスレビューがまだ実行されていません。\n")

    if head is None:
        # 照合できない状態で通すとセンチネルが永続 fail-open になるためブロック
        block(
            "no_head",
            head,
            status_output,
            "[codex_gate] git で HEAD を取得できず、レビュー記録を照合できません。\n"
            "git リポジトリ内で実行しているか確認してください。\n",
        )

    if recorded != head:
        # 古い HEAD のセンチネルは無効なので破棄してから再レビューを要求する
        try:
            os.remove(SENTINEL)
        except OSError:
            pass
        block(
            "head_mismatch",
            head,
            status_output,
            "[codex_gate] センチネルの HEAD が現在と一致しません"
            "(レビュー後にコミットが進んでいます)。\n",
        )

    if status_output is None or status_output.strip() != "":
        # 未コミット変更(未追跡含む)はレビューを通っていない
        block(
            "dirty_tree",
            head,
            status_output,
            "[codex_gate] レビュー後の未コミット変更(未追跡ファイル含む)があります"
            "(または作業ツリーの状態を確認できません)。\n"
            "コミットしてから再レビューしてください。\n",
        )

    # HEAD 一致かつクリーン: レビュー済みのまま通過(センチネルは保持)。
    # 通過したら抑制指紋は破棄する(同じ dirty 状態が再出現したら改めて警告する)
    _clear_last_block()
    sys.exit(0)


if __name__ == "__main__":
    main()
