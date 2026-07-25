#!/usr/bin/env python3
"""Stop フック: 計画のリソース超過と goal 未定義をブロックする。

- invariants.md の resources ブロックを上限として読む
- 最新の計画ファイルの cost_estimate が上限を超えていたら exit 2
- 実験を含む計画(experiment: false が無い)で goal 未定義なら exit 2
- 計画ファイルが無い・パースできない場合は黙って通す(壊さない)
"""
import re
import sys
from pathlib import Path

PLANS_DIR = Path(".claude/plans")
INVARIANTS = Path(".claude/improvements/invariants.md")


def _latest_plan() -> Path | None:
    if not PLANS_DIR.exists():
        return None
    plans = sorted(PLANS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime)
    return plans[-1] if plans else None


def _read_yaml_number(text: str, key: str) -> float | None:
    # 行末まで厳密に見る。ゆるい [0-9.]+ だと `1e3` から `1` だけを拾って 1.0 と
    # 読み、1000分の見積もりが上限120を素通りしてしまう(桁を落とす誤読)。
    # 末尾の空白と # コメントは許す(invariants.md の上限行はコメント付きのため、
    # 許さないと上限が読めずゲートが無効化される)
    m = re.search(
        rf"^\s*{key}\s*:\s*([0-9]+(?:\.[0-9]*)?|\.[0-9]+)\s*(?:#.*)?$",
        text,
        re.MULTILINE,
    )
    if m is None:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        # 不正な数値表記(例: 1.2.3)はパース不能として扱う。
        # 「パースできない場合は黙って通す」というこのフックの方針に合わせる。
        return None


def main():
    plan_path = _latest_plan()
    if plan_path is None or not INVARIANTS.exists():
        sys.exit(0)

    try:
        plan = plan_path.read_text(encoding="utf-8")
        inv = INVARIANTS.read_text(encoding="utf-8")
    except OSError:
        sys.exit(0)

    # コード変更のみの計画はチェック対象外
    if re.search(r"^\s*experiment\s*:\s*false", plan, re.MULTILINE):
        sys.exit(0)

    # 計画に cost_estimate も goal も無い場合、実験計画かどうか判別できないため
    # 「学習・実験」系の語を含むときだけ必須とする(過剰ブロックの防止)
    is_experimental = bool(
        re.search(r"cost_estimate|goal\s*:", plan)
        or re.search(r"学習|実験|train|epoch", plan)
    )
    if not is_experimental:
        sys.exit(0)

    errors: list[str] = []

    # 1. goal の必須チェック
    if not re.search(r"^\s*goal\s*:", plan, re.MULTILINE):
        errors.append(
            "goal が未定義です。metric / target / direction / baseline / "
            "guard_metrics を計画に追加してください"
            "(コード変更のみなら `experiment: false` と書いてください)。"
        )
    else:
        for key in ("metric", "target", "direction", "baseline"):
            if not re.search(rf"^\s*{key}\s*:", plan, re.MULTILINE):
                errors.append(f"goal.{key} が未定義です。")

    # 2. リソース上限チェック(invariants の resources と突き合わせ)
    checks = [
        ("max_train_minutes", "train_minutes"),
        ("max_epochs", "epochs"),
        ("max_dataset_gb", "dataset_gb"),
        ("max_parallel_jobs", "parallel_jobs"),
    ]
    for limit_key, est_key in checks:
        limit = _read_yaml_number(inv, limit_key)
        est = _read_yaml_number(plan, est_key)
        if limit is not None and est is not None and est > limit:
            errors.append(
                f"リソース超過: {est_key}={est} が上限 {limit_key}={limit} を"
                f"超えています。計画を分割するか、ユーザーに上限引き上げを"
                f"相談してください。"
            )

    if errors:
        print(
            "[plan_gate] 計画がゲートを通過できません:\n- "
            + "\n- ".join(errors),
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
