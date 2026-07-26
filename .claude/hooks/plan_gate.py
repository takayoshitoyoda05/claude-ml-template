#!/usr/bin/env python3
"""Stop フック: 計画のリソース超過・goal未定義・読めない見積もりをブロックする。

- 検査対象の計画は現在のブランチ名(git symbolic-ref)から決める。対象が
  特定できない場合(非 git / 対応する計画が0件・複数件など)は fail-open で通す
- cost_estimate / goal ブロックの必須キーと値は fail-closed で検査する
  (値が非負十進数として読めない場合もブロックする。詳細は設計書セクション12)
- invariants.md の resources ブロックは上限として使う。ファイルが無い・
  読めない・ブロックが無い・キーが無い場合は「上限比較のみ」をスキップする
  (計画側の必須キー検査は invariants の状態に関わらず実施する)
- experiment: false の行(行末まで一致)があるコード変更のみの計画は対象外
"""
import re
import subprocess
import sys
from pathlib import Path

PLANS_DIR = Path(".claude/plans")
INVARIANTS = Path(".claude/improvements/invariants.md")

COST_KEYS = ("train_minutes", "epochs", "dataset_gb", "parallel_jobs")
GOAL_KEYS = ("metric", "target", "direction", "baseline", "guard_metrics")
LIMIT_KEYS = (
    ("max_train_minutes", "train_minutes"),
    ("max_epochs", "epochs"),
    ("max_dataset_gb", "dataset_gb"),
    ("max_parallel_jobs", "parallel_jobs"),
)
# 非負の十進数(120 / 30.5 / 200. / .5)。行末の空白と # コメントは許す
# (invariants.md の上限行はコメント付きのため、許さないと上限が読めずゲートが
# 無効化される。前回の回帰修正の成果をそのまま流用する)
_NUMBER = r"([0-9]+(?:\.[0-9]*)?|\.[0-9]+)"


def _current_branch() -> str | None:
    """現在のブランチ名を返す。非 git / detached HEAD / git 不在なら None。

    unborn branch(コミット0件)でもブランチ名を返すことを実測済みのため、
    `git rev-parse --abbrev-ref HEAD` ではなく `git symbolic-ref` を使う
    (前者は unborn branch で exit 128 になる)。
    """
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def _slug_from_branch(branch: str) -> str:
    """ブランチ名の最終セグメントから worktree の `-group-<英数字>` を1回だけ除く。"""
    segment = branch.rsplit("/", 1)[-1]
    return re.sub(r"-group-[A-Za-z0-9]+$", "", segment, count=1)


def _select_plan_path(slug: str) -> Path | None:
    """slug に対応する計画ファイルを1件だけ選ぶ。曖昧・0件なら None(fail-open)。

    直接一致が最優先。直接一致が無い場合にのみ日付つき形を glob で探し、
    その候補がちょうど1件のときだけ採用する。

    slug から正規表現を組むとメタ文字(`.` `+` 等)を含むブランチ名で誤マッチ
    しうるため、glob の完全一致(stem[9:] == slug)で絞り込む
    (glob のメタ文字はブランチ名に使えないので、この問題が原理的に起きない)。
    """
    try:
        direct = PLANS_DIR / f"{slug}.md"
        if direct.exists():
            return direct
        candidates = [
            path
            for path in PLANS_DIR.glob(f"*-{slug}.md")
            if len(path.stem) > 9
            and path.stem[:8].isdigit()
            and path.stem[8] == "-"
            and path.stem[9:] == slug
        ]
        return candidates[0] if len(candidates) == 1 else None
    except OSError:
        return None


def _extract_block(text: str, key: str) -> str | None:
    """`<key>:` ブロックの本文を抽出する。ブロックが見つからなければ None を返す。

    最初に一致した見出し行を採用し、以降インデントが見出し行以下の非空行に
    達するまでを本文とする(空行は本文として継続。コードフェンス行は
    インデント0なので終端になる)。
    """
    header_re = re.compile(rf"^(\s*){key}\s*:\s*(?:#.*)?$")
    lines = text.splitlines()
    start = None
    header_indent = 0
    for i, line in enumerate(lines):
        m = header_re.match(line)
        if m is not None:
            start = i + 1
            header_indent = len(m.group(1))
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start:]:
        if line.strip() == "":
            body.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= header_indent:
            break
        body.append(line)
    return "\n".join(body)


def _read_number(block: str, key: str) -> tuple[bool, float | None]:
    """ブロック本文内で `<key>:` の値を非負十進数として読む。

    Returns:
        (キー行が見つかったか, 読めた数値)。キー行はあるが値が読めない場合は
        (True, None) を返す。呼び出し側は「キー自体が無い」場合と「値が
        読めない」場合を区別して別々のエラーメッセージを出す。
    """
    m = re.search(
        rf"^\s*{key}\s*:\s*{_NUMBER}\s*(?:#.*)?$",
        block,
        re.MULTILINE,
    )
    if m is not None:
        try:
            return True, float(m.group(1))
        except ValueError:
            # 不正な数値表記(例: 1.2.3)はパース不能として扱う
            return True, None
    if re.search(rf"^\s*{key}\s*:", block, re.MULTILINE):
        return True, None
    return False, None


def _validate_cost_estimate(plan: str, escape_hint: str) -> list[str]:
    """cost_estimate ブロックの必須4キー・値を検査する(C1-C3)。

    Args:
        plan: 計画ファイルの全文。
        escape_hint: `experiment: false` の案内文言(未定義系エラーに付与)。

    Returns:
        検出したエラーメッセージのリスト。問題が無ければ空リスト。
    """
    cost_block = _extract_block(plan, "cost_estimate")
    if cost_block is None:
        return [f"cost_estimate ブロックが未定義です{escape_hint}"]

    errors: list[str] = []
    for key in COST_KEYS:
        found, value = _read_number(cost_block, key)
        if not found:
            errors.append(f"cost_estimate.{key} が未定義です{escape_hint}")
        elif value is None:
            errors.append(
                f"cost_estimate.{key} の値が非負の十進数として読めません"
                f"{escape_hint}"
            )
    return errors


def _validate_goal_ranges(goal_block: str) -> list[str]:
    """goal.direction と goal.guard_metrics の値域を検査する(C7-C8)。

    `_validate_goal` から分離した理由: 必須キーの有無チェック(C4-C6)と
    値域チェック(C7-C8)を1関数にまとめると複雑度が閾値を超えるため。

    Args:
        goal_block: `_extract_block(plan, "goal")` で抽出した goal ブロックの本文。

    Returns:
        検出したエラーメッセージのリスト。問題が無ければ空リスト。
    """
    errors: list[str] = []

    direction_match = re.search(
        r"^\s*direction\s*:\s*(.+?)\s*(?:#.*)?$", goal_block, re.MULTILINE
    )
    if direction_match is not None:
        direction = direction_match.group(1).strip()
        if direction not in ("minimize", "maximize"):
            errors.append(
                f"goal.direction の値 {direction!r} が不正です。"
                "minimize か maximize を指定してください。"
            )

    guard_match = re.search(
        r"^\s*guard_metrics\s*:\s*(.*?)\s*(?:#.*)?$", goal_block, re.MULTILINE
    )
    if guard_match is not None:
        guard_value = guard_match.group(1).strip()
        has_names = bool(
            re.search(r"^\s*-\s*name\s*:", goal_block, re.MULTILINE)
        )
        if guard_value != "[]" and not has_names:
            errors.append(
                "goal.guard_metrics が空です。`guard_metrics: []` と明示するか、"
                "`- name:` で1件以上指定してください。"
            )

    return errors


def _validate_goal(plan: str, escape_hint: str) -> list[str]:
    """goal ブロックの必須5キー・値を検査する(C4-C6)。値域は _validate_goal_ranges に委譲する。

    Args:
        plan: 計画ファイルの全文。
        escape_hint: `experiment: false` の案内文言(goal 未定義エラーに付与)。

    Returns:
        検出したエラーメッセージのリスト。問題が無ければ空リスト。
    """
    goal_block = _extract_block(plan, "goal")
    if goal_block is None:
        return [
            (
                "goal が未定義です。metric / target / direction / baseline / "
                f"guard_metrics を計画に追加してください{escape_hint}"
            )
        ]

    errors: list[str] = []
    for key in GOAL_KEYS:
        if not re.search(rf"^\s*{key}\s*:", goal_block, re.MULTILINE):
            errors.append(f"goal.{key} が未定義です。")

    for key in ("target", "baseline"):
        found, value = _read_number(goal_block, key)
        if found and value is None:
            errors.append(f"goal.{key} の値が非負の十進数として読めません。")

    errors.extend(_validate_goal_ranges(goal_block))
    return errors


def _validate_resource_limits(plan: str) -> list[str]:
    """invariants.md の resources 上限と計画の cost_estimate を比較する(C9-C10)。

    invariants.md が読めない・resources ブロックが無い場合や、計画に
    cost_estimate ブロックが無い場合は比較自体をスキップする(計画側の必須
    キー検査は `_validate_cost_estimate` が別途担うため、ここでは責務を
    分けて独立に読み直す。OSError で例外終了しないようにする)。

    Args:
        plan: 計画ファイルの全文。

    Returns:
        検出したエラーメッセージのリスト。問題が無ければ空リスト。
    """
    try:
        inv_text = INVARIANTS.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []

    resources_block = _extract_block(inv_text, "resources")
    if resources_block is None:
        return []

    cost_block = _extract_block(plan, "cost_estimate")
    errors: list[str] = []
    for limit_key, est_key in LIMIT_KEYS:
        limit_found, limit_value = _read_number(resources_block, limit_key)
        if not limit_found:
            continue
        if limit_value is None:
            errors.append(
                f"invariants の {limit_key} が非負の十進数として読めません。"
            )
            continue
        if cost_block is None:
            continue
        est_found, est_value = _read_number(cost_block, est_key)
        if est_found and est_value is not None and est_value > limit_value:
            errors.append(
                f"リソース超過: {est_key}={est_value} が上限 "
                f"{limit_key}={limit_value} を超えています。計画を分割するか、"
                "ユーザーに上限引き上げを相談してください。"
            )
    return errors


def main() -> None:
    if not PLANS_DIR.exists():
        sys.exit(0)

    branch = _current_branch()
    if branch is None:
        sys.exit(0)

    plan_path = _select_plan_path(_slug_from_branch(branch))
    if plan_path is None:
        sys.exit(0)

    try:
        plan = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        sys.exit(0)

    # コード変更のみの計画はチェック対象外(行末まで固定。`experiment: falsehood`
    # や散文中の同じ書き出しの行でスキップが成立してしまう現行実装の穴を塞ぐ)
    if re.search(r"^\s*experiment\s*:\s*false\s*(?:#.*)?$", plan, re.MULTILINE):
        sys.exit(0)

    # 計画に cost_estimate も goal も無い場合、実験計画かどうか判別できないため
    # 「学習・実験」系の語を含むときだけ必須とする(過剰ブロックの防止)
    is_experimental = bool(
        re.search(r"cost_estimate|goal\s*:", plan)
        or re.search(r"学習|実験|train|epoch", plan)
    )
    if not is_experimental:
        sys.exit(0)

    escape_hint = "(コード変更のみなら `experiment: false` と書いてください)。"
    errors: list[str] = []
    errors.extend(_validate_cost_estimate(plan, escape_hint))
    errors.extend(_validate_goal(plan, escape_hint))
    errors.extend(_validate_resource_limits(plan))

    if errors:
        print(
            f"[plan_gate] 検査対象の計画: {plan_path}\n"
            "[plan_gate] 計画がゲートを通過できません:\n- " + "\n- ".join(errors),
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
