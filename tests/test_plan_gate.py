"""plan_gate.py の受け入れテスト。

対象: `.claude/plans/20260726-plan-gate-precision.md` の R-001〜R-012。
`tests/test_env_fingerprint.py` に倣い、フックを import せず
`subprocess.run([sys.executable, <plan_gate 絶対パス>], ...)` で CLI 起動する
(実運用の Stop フックと同じ経路で検証するため)。

Step 6(ユーザーによる `.claude/hooks/plan_gate.py` への適用)より前は、
現行実装(fail-open な旧仕様)に対して多数 FAIL するのが正しい状態(RED)。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PLAN_GATE_PATH = (
    Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "plan_gate.py"
)
_SUBPROCESS_TIMEOUT = 10

# invariants.md の完備フィクスチャ。リポジトリ本体の値をコピーせずテスト内で
# 固定する(値の変更でテストが揺れるのを防ぐため。計画 Step 2 の注記に従う)。
_INVARIANTS_COMPLETE = (
    "resources:\n"
    "  max_train_minutes: 120\n"
    "  max_epochs: 100\n"
    "  max_dataset_gb: 10\n"
    "  max_parallel_jobs: 1\n"
)
_INVARIANTS_NO_RESOURCES = "# 上限は別ファイルで管理している\nother: 1\n"
_INVARIANTS_LIMIT_UNREADABLE = (
    "resources:\n"
    "  max_train_minutes: 1e3\n"
    "  max_epochs: 100\n"
    "  max_dataset_gb: 10\n"
    "  max_parallel_jobs: 1\n"
)

_COST_COMPLETE = (
    "cost_estimate:\n"
    "  train_minutes: 30\n"
    "  epochs: 5\n"
    "  dataset_gb: 1\n"
    "  parallel_jobs: 1\n"
)
_GOAL_COMPLETE = (
    "goal:\n"
    "  metric: rmse\n"
    "  target: 0.15\n"
    "  direction: minimize\n"
    "  baseline: 0.21\n"
    "  guard_metrics: []\n"
)
# cost_estimate 4キー・goal 5キーを完備した計画本文(特記の無いケースはこれを使う)
_COMPLETE_PLAN = "学習ジョブを epoch 付きで実行する\n" + _COST_COMPLETE + _GOAL_COMPLETE
# 実験語(学習)は含むが cost_estimate も goal も無い計画本文
_EXPERIMENTAL_NO_BLOCKS = "学習ジョブを実行する\n"


def _cost_with_train_minutes(value: str) -> str:
    """train_minutes だけを差し替えた cost_estimate ブロックを組み立てる。"""
    return (
        "cost_estimate:\n"
        f"  train_minutes: {value}\n"
        "  epochs: 5\n"
        "  dataset_gb: 1\n"
        "  parallel_jobs: 1\n"
    )


def _init_repo(tmp_path: Path, branch: str | None, init_git: bool) -> None:
    """指定があれば一時ディレクトリで `git init -b <branch>` する。

    Args:
        tmp_path: pytest が用意する一時ディレクトリ。
        branch: `git init -b <branch>` するブランチ名。None なら何もしない。
        init_git: False なら git init 自体を行わない(非 git ディレクトリの再現)。
    """
    if init_git and branch is not None:
        subprocess.run(
            ["git", "init", "-q", "-b", branch],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )


def _write_plans(
    tmp_path: Path,
    plan_name: str | None,
    plan_text: str | None,
    plan_bytes: bytes | None,
    extra_plans: dict[str, str] | None,
) -> None:
    """`.claude/plans/` に本命の計画ファイルと追加分を書き出す。

    Args:
        tmp_path: pytest が用意する一時ディレクトリ。
        plan_name: 書く計画ファイル名。None なら本命は書かない。
        plan_text: plan_name の中身。plan_name が None なら無視される。
        plan_bytes: plan_name に生バイト列で書く中身(不正UTF-8の再現用)。
            plan_text が指定されていればそちらを優先する。
        extra_plans: 追加で書くファイル名→中身の辞書。
    """
    plans_dir = tmp_path / ".claude" / "plans"
    if plan_name is not None or extra_plans:
        plans_dir.mkdir(parents=True, exist_ok=True)
    if plan_name is not None and plan_text is not None:
        (plans_dir / plan_name).write_text(plan_text, encoding="utf-8")
    elif plan_name is not None and plan_bytes is not None:
        (plans_dir / plan_name).write_bytes(plan_bytes)
    for name, text in (extra_plans or {}).items():
        (plans_dir / name).write_text(text, encoding="utf-8")


def _write_invariants(
    tmp_path: Path,
    invariants_text: str | None,
    invariants_bytes: bytes | None,
    invariants_is_dir: bool,
) -> None:
    """`.claude/improvements/invariants.md` を書く(不正UTF-8・ディレクトリ化も再現)。

    Args:
        tmp_path: pytest が用意する一時ディレクトリ。
        invariants_text: invariants.md の中身。None なら invariants_bytes を見る。
        invariants_bytes: invariants.md に生バイト列で書く中身
            (不正UTF-8の再現用)。invariants_text が None のときのみ使う。
        invariants_is_dir: True なら invariants.md と同名のディレクトリを作り、
            読み取り時に OSError(IsADirectoryError)が起きる状態を再現する。
    """
    improvements_dir = tmp_path / ".claude" / "improvements"
    if invariants_is_dir:
        (improvements_dir / "invariants.md").mkdir(parents=True, exist_ok=True)
    elif invariants_text is not None:
        improvements_dir.mkdir(parents=True, exist_ok=True)
        (improvements_dir / "invariants.md").write_text(
            invariants_text, encoding="utf-8"
        )
    elif invariants_bytes is not None:
        improvements_dir.mkdir(parents=True, exist_ok=True)
        (improvements_dir / "invariants.md").write_bytes(invariants_bytes)


def _run(
    tmp_path: Path,
    branch: str | None,
    plan_name: str | None = None,
    plan_text: str | None = None,
    plan_bytes: bytes | None = None,
    invariants_text: str | None = _INVARIANTS_COMPLETE,
    invariants_bytes: bytes | None = None,
    extra_plans: dict[str, str] | None = None,
    init_git: bool = True,
    invariants_is_dir: bool = False,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """一時ディレクトリにフィクスチャを組み立て、plan_gate.py を CLI 起動する。

    パスはすべて `Path` の結合で組み立て、シェルのリダイレクトは使わない
    (保護パス名をリテラルで含むリダイレクトは guard_bash がブロックするため)。
    フィクスチャの組み立ては `_init_repo` / `_write_plans` / `_write_invariants`
    に分けている(責務ごとに薄いヘルパーへ分割し、この関数自体の複雑度を
    抑えるため)。

    Args:
        tmp_path: pytest が用意する一時ディレクトリ。
        branch: `git init -b <branch>` するブランチ名。None なら git init しない。
        plan_name: `.claude/plans/` に書く計画ファイル名。None なら書かない。
        plan_text: plan_name の中身。plan_name が None なら無視される。
        plan_bytes: plan_name に生バイト列で書く中身(不正UTF-8の再現用)。
            plan_text が指定されていればそちらを優先する。
        invariants_text: `.claude/improvements/invariants.md` の中身。
            None なら invariants.md 自体を作らない。
        invariants_bytes: invariants.md に生バイト列で書く中身
            (不正UTF-8の再現用)。invariants_text が None のときのみ使う。
        extra_plans: 追加で `.claude/plans/` に書くファイル名→中身の辞書。
        init_git: False なら git init 自体を行わない(非 git ディレクトリの再現)。
        invariants_is_dir: True なら invariants.md と同名のディレクトリを作り、
            読み取り時に OSError(IsADirectoryError)が起きる状態を再現する。
        extra_env: サブプロセスに追加で渡す環境変数(GIT_CEILING_DIRECTORIES 等)。

    Returns:
        plan_gate.py を実行した結果(stdout/stderr/returncode を含む)。
    """
    _init_repo(tmp_path, branch, init_git)
    _write_plans(tmp_path, plan_name, plan_text, plan_bytes, extra_plans)
    _write_invariants(tmp_path, invariants_text, invariants_bytes, invariants_is_dir)

    env = os.environ.copy()
    if extra_env is not None:
        env.update(extra_env)

    return subprocess.run(
        [sys.executable, str(PLAN_GATE_PATH)],
        cwd=str(tmp_path),
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT,
    )


def test_t01_no_plans_dir(tmp_path: Path) -> None:
    """T-01: `.claude/plans/` 自体が無ければ exit 0。"""
    result = _run(tmp_path, branch=None, init_git=False)
    assert result.returncode == 0


def test_t02_non_git_dir(tmp_path: Path) -> None:
    """T-02: 非 git ディレクトリでは(計画があっても)exit 0。

    親ディレクトリが git 管理下にある環境でも誤検出しないよう、
    GIT_CEILING_DIRECTORIES で git の親探索を tmp_path の親で止める。
    """
    result = _run(
        tmp_path,
        branch=None,
        init_git=False,
        plan_name="20260726-something.md",
        plan_text=_EXPERIMENTAL_NO_BLOCKS,
        extra_env={"GIT_CEILING_DIRECTORIES": str(tmp_path.parent)},
    )
    assert result.returncode == 0


def test_t03_no_matching_plan(tmp_path: Path) -> None:
    """T-03: ブランチに対応する計画が無ければ exit 0(無関係な計画は無視)。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-bar.md",
        plan_text=_COMPLETE_PLAN,
    )
    assert result.returncode == 0


def test_t04_direct_match_blocks(tmp_path: Path) -> None:
    """T-04: ブランチ名と完全一致する計画(実験語あり・goal 無し)は exit 2。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=_EXPERIMENTAL_NO_BLOCKS,
    )
    assert result.returncode == 2


def test_t05_group_suffix_stripped(tmp_path: Path) -> None:
    """T-05: worktree ブランチの `-group-B` を除いた slug で計画を解決する。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo-group-B",
        plan_name="20260726-foo.md",
        plan_text=_EXPERIMENTAL_NO_BLOCKS,
    )
    assert result.returncode == 2


def test_t06_glob_dated_match(tmp_path: Path) -> None:
    """T-06: 日付なしブランチ名でも glob で日付つき計画に一致する。"""
    result = _run(
        tmp_path,
        branch="feature/foo",
        plan_name="20260726-foo.md",
        plan_text=_EXPERIMENTAL_NO_BLOCKS,
    )
    assert result.returncode == 2


def test_t07_ambiguous_glob_skips(tmp_path: Path) -> None:
    """T-07: 候補が2件になったら曖昧なので検査しない(exit 0)。"""
    result = _run(
        tmp_path,
        branch="feature/foo",
        extra_plans={
            "20260726-foo.md": _EXPERIMENTAL_NO_BLOCKS,
            "20260725-foo.md": _EXPERIMENTAL_NO_BLOCKS,
        },
    )
    assert result.returncode == 0


def test_t08_experiment_false_skips(tmp_path: Path) -> None:
    """T-08(既存): `experiment: false` の計画は exit 0。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text="experiment: false\n" + _EXPERIMENTAL_NO_BLOCKS,
    )
    assert result.returncode == 0


def test_t09_missing_cost_estimate_block(tmp_path: Path) -> None:
    """T-09: 実験語あり・goal 完備・cost_estimate ブロック無しは exit 2。"""
    plan_text = "学習ジョブを実行する\n" + _GOAL_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t10_missing_cost_estimate_key(tmp_path: Path) -> None:
    """T-10: cost_estimate に train_minutes が無い(他3キーはある)場合は exit 2。"""
    cost_missing_train_minutes = (
        "cost_estimate:\n  epochs: 5\n  dataset_gb: 1\n  parallel_jobs: 1\n"
    )
    plan_text = "学習ジョブを実行する\n" + cost_missing_train_minutes + _GOAL_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t11_train_minutes_exponent_unreadable(tmp_path: Path) -> None:
    """T-11: `train_minutes: 1e3` は exit 2 かつ stderr に読めない旨が出る。"""
    plan_text = (
        "学習ジョブを実行する\n" + _cost_with_train_minutes("1e3") + _GOAL_COMPLETE
    )
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2
    assert "読めません" in result.stderr


@pytest.mark.parametrize(
    "value", ["-5", '"45"', "1.2.3"], ids=["negative", "quoted", "multi-dot"]
)
def test_t12_unreadable_values(tmp_path: Path, value: str) -> None:
    """T-12: `-5` / `"45"` / `1.2.3` のいずれも非負十進数として読めず exit 2。"""
    plan_text = (
        "学習ジョブを実行する\n" + _cost_with_train_minutes(value) + _GOAL_COMPLETE
    )
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t13_valid_decimal_forms_pass(tmp_path: Path) -> None:
    """T-13: `100.` / `.5` のような正当な小数表記は exit 0(回帰防止)。"""
    cost = (
        "cost_estimate:\n"
        "  train_minutes: 100.\n"
        "  epochs: 5\n"
        "  dataset_gb: .5\n"
        "  parallel_jobs: 1\n"
    )
    plan_text = "学習ジョブを実行する\n" + cost + _GOAL_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 0


def test_t14_invariants_limit_unreadable(tmp_path: Path) -> None:
    """T-14: invariants の `max_train_minutes: 1e3` は exit 2。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=_COMPLETE_PLAN,
        invariants_text=_INVARIANTS_LIMIT_UNREADABLE,
    )
    assert result.returncode == 2


def test_t15_invariants_without_resources_block(tmp_path: Path) -> None:
    """T-15: invariants に `resources:` ブロックが無ければ(計画は完備)exit 0。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=_COMPLETE_PLAN,
        invariants_text=_INVARIANTS_NO_RESOURCES,
    )
    assert result.returncode == 0


def test_t16_resource_over_limit(tmp_path: Path) -> None:
    """T-16: `train_minutes: 999` が上限120を超えると exit 2 かつ「リソース超過」。"""
    plan_text = (
        "学習ジョブを実行する\n" + _cost_with_train_minutes("999") + _GOAL_COMPLETE
    )
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2
    assert "リソース超過" in result.stderr


def test_t17_goal_keys_outside_block(tmp_path: Path) -> None:
    """T-17: `goal:` ブロックの外に5キー全てがあり配下が空なら exit 2。

    guard_metrics を含む5キー全てをブロック外に有効値で置く。4キーだけだと
    goalキーを計画全文から検索する誤実装でも guard_metrics 欠落を理由に
    exit 2 になり、この誤実装を検出できない(このテストの目的を果たせない)。
    """
    plan_text = (
        "学習ジョブを実行する\n"
        + _COST_COMPLETE
        + "metric: rmse\ntarget: 0.15\ndirection: minimize\nbaseline: 0.21\n"
        + "guard_metrics: []\n"
        + "goal:\n"
    )
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t18_stray_key_outside_goal_block_ignored(tmp_path: Path) -> None:
    """T-18: goal ブロックが完備していれば、ブロック外の不正値は前後とも無視され exit 0。

    goal ブロックの前後両方に不正値を置く。goalキーを計画全文から検索する
    誤実装は、先頭一致・末尾一致のどちらでもこの不正値を拾ってしまうため、
    その誤実装を確実に検出できる。
    """
    stray = "target: not-a-number\ndirection: down\n"
    plan_text = stray + _COMPLETE_PLAN + stray
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 0


def test_t19_missing_guard_metrics(tmp_path: Path) -> None:
    """T-19: goal に guard_metrics が無ければ exit 2。"""
    goal_without_guard = (
        "goal:\n"
        "  metric: rmse\n"
        "  target: 0.15\n"
        "  direction: minimize\n"
        "  baseline: 0.21\n"
    )
    plan_text = "学習ジョブを実行する\n" + _COST_COMPLETE + goal_without_guard
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t20_guard_metrics_empty_list(tmp_path: Path) -> None:
    """T-20: `guard_metrics: []` は exit 0。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=_COMPLETE_PLAN,
    )
    assert result.returncode == 0


def test_t21_guard_metrics_named_entry(tmp_path: Path) -> None:
    """T-21: `guard_metrics:` 配下に `- name: ...` が1件あれば exit 0。"""
    goal_with_named_guard = (
        "goal:\n"
        "  metric: rmse\n"
        "  target: 0.15\n"
        "  direction: minimize\n"
        "  baseline: 0.21\n"
        "  guard_metrics:\n"
        "    - name: train_val_gap\n"
    )
    plan_text = "学習ジョブを実行する\n" + _COST_COMPLETE + goal_with_named_guard
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 0


def test_t22_invalid_direction(tmp_path: Path) -> None:
    """T-22: `direction: down` は値域外のため exit 2。"""
    plan_text = _COMPLETE_PLAN.replace("direction: minimize", "direction: down")
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t23_experiment_falsehood_not_skipped(tmp_path: Path) -> None:
    """T-23: `experiment: falsehood` は行末固定によりスキップされず exit 2。"""
    plan_text = "experiment: falsehood\n学習ジョブを実行する\n"
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t24_experiment_false_with_trailing_comment_skips(tmp_path: Path) -> None:
    """T-24: `experiment: false   # コード変更のみ` は末尾コメント許容で exit 0。"""
    plan_text = "experiment: false   # コード変更のみ\n"
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 0


def test_t25_invariants_unreadable_plan_complete(tmp_path: Path) -> None:
    """T-25: invariants.md が読めない(ディレクトリ)+ 計画完備なら exit 0(例外終了しない)。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=_COMPLETE_PLAN,
        invariants_is_dir=True,
    )
    assert result.returncode == 0


def test_t26_invariants_unreadable_plan_incomplete(tmp_path: Path) -> None:
    """T-26: invariants.md が読めなくても計画側(goal 欠落)の検査は実施される。"""
    plan_text = "学習ジョブを実行する\n" + _COST_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
        invariants_is_dir=True,
    )
    assert result.returncode == 2


def test_t27_glob_extra_prefix_not_matched(tmp_path: Path) -> None:
    """T-27: `20260726-extra-foo.md` は glob の誤マッチにならず exit 0。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-extra-foo.md",
        plan_text=_COMPLETE_PLAN,
    )
    assert result.returncode == 0


def test_t28_direct_match_takes_priority_over_glob(tmp_path: Path) -> None:
    """T-28: 直接一致があれば、glob候補が完備でもそれを無視して直接一致を検査対象にする。

    `foo.md`(不備)と `20260726-foo.md`(完備)の両方があるとき、直接一致の
    `foo.md` が優先されて exit 2 になることを確認する。glob 候補を優先したり、
    どちらか片方だけを見る誤実装ではこの exit 2 にならない。
    """
    result = _run(
        tmp_path,
        branch="feature/foo",
        plan_name="foo.md",
        plan_text=_EXPERIMENTAL_NO_BLOCKS,
        extra_plans={"20260726-foo.md": _COMPLETE_PLAN},
    )
    assert result.returncode == 2


def test_t29_invalid_utf8_plan_skips(tmp_path: Path) -> None:
    """T-29: 計画ファイルが不正なUTF-8バイト列でも例外終了せず exit 0。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_bytes=b"\xff\xfe invalid utf-8 \xff",
    )
    assert result.returncode == 0


def test_t30_invalid_utf8_invariants_skips(tmp_path: Path) -> None:
    """T-30: invariants.md が不正なUTF-8でも例外終了せず、計画完備なら exit 0。"""
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=_COMPLETE_PLAN,
        invariants_text=None,
        invariants_bytes=b"resources:\n  max_train_minutes: \xff\xfe\n",
    )
    assert result.returncode == 0


def test_t31_real_cost_estimate_after_sample_over_limit(tmp_path: Path) -> None:
    """T-31: 見本(上限内)の後にある本物 cost_estimate が上限超過なら exit 2。

    最初に一致したブロックだけを検査する旧実装は見本の `train_minutes: 30`
    だけを見て通してしまう(実測 exit 0)。全ブロックを検査する新実装は
    後続の本物 `train_minutes: 9999` も見て exit 2 にする。
    """
    sample = "```yaml\n" + _cost_with_train_minutes("30") + "```\n"
    real = _cost_with_train_minutes("9999")
    plan_text = "学習ジョブを実行する\n" + sample + real + _GOAL_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2
    assert "リソース超過" in result.stderr


def test_t32_real_goal_after_sample_invalid_direction(tmp_path: Path) -> None:
    """T-32: 見本(完備)の後にある本物 goal の direction が不正なら exit 2。

    最初に一致したブロックだけを検査する旧実装は見本の完備 goal だけを見て
    通してしまう(実測 exit 0)。全ブロックを検査する新実装は後続の本物
    `direction: down` も見て exit 2 にする。
    """
    sample = "```yaml\n" + _GOAL_COMPLETE + "```\n"
    real = _GOAL_COMPLETE.replace("direction: minimize", "direction: down")
    plan_text = "学習ジョブを実行する\n" + _COST_COMPLETE + sample + real
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t33_real_goal_after_sample_is_empty(tmp_path: Path) -> None:
    """T-33: 見本の goal だけが完備で、本物の goal 見出しが空なら exit 2。

    最初に一致したブロックだけを検査する旧実装は見本の完備 goal だけを見て
    通してしまう(実測 exit 0)。全ブロックを検査する新実装は後続の本物の
    空の `goal:` 見出しも見て、必須5キー欠落により exit 2 にする。
    """
    sample = "```yaml\n" + _GOAL_COMPLETE + "```\n"
    plan_text = "学習ジョブを実行する\n" + _COST_COMPLETE + sample + "goal:\n"
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t34_real_blocks_only_inside_fence_still_pass(tmp_path: Path) -> None:
    """T-34: 見本を伴わず本物の cost_estimate/goal が```yamlフェンス内にあるだけの計画は従来どおり exit 0。

    planner.md の出力例は cost_estimate / goal を```yamlフェンス内に書くため、
    フェンス領域を除外する方式ではこの形式の本物の計画が全部ブロックされて
    しまう。全ブロック検査方式ならフェンスの有無に関わらず内容だけで判定する
    ため、この形式でも壊れないことを確認する(この修正の副作用がないことの証明)。
    """
    plan_text = "```yaml\n" + _COMPLETE_PLAN + "```\n"
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 0


def test_t35_duplicate_error_across_blocks_deduped(tmp_path: Path) -> None:
    """T-35: 見本と本物の両方に同じ不備があっても、同一メッセージは1回だけ出る。

    全ブロック検査により見本・本物それぞれから同じエラーが生成されうるため、
    重複除去(出現順維持)が効いていることを確認する。
    """
    cost_missing_train_minutes = (
        "cost_estimate:\n  epochs: 5\n  dataset_gb: 1\n  parallel_jobs: 1\n"
    )
    sample = "```yaml\n" + cost_missing_train_minutes + "```\n"
    real = cost_missing_train_minutes
    plan_text = "学習ジョブを実行する\n" + sample + real + _GOAL_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2
    assert result.stderr.count("cost_estimate.train_minutes が未定義です") == 1


def test_t36_nested_cost_estimate_over_limit_detected(tmp_path: Path) -> None:
    """T-36: 外側 cost_estimate が上限内でも、内側に入れ子の本物が上限超過なら exit 2。

    ブロック確定後に本文の終端まで走査位置を飛ばす実装は、内側により深い
    インデントで入れ子になった同名ブロックを取りこぼす(実測 exit 0)。
    1行ずつ走査する修正版は入れ子のブロックも独立に検査して exit 2 にする。
    """
    plan_text = (
        "学習ジョブを実行する\n"
        "cost_estimate:\n"
        "  train_minutes: 30\n"
        "  epochs: 10\n"
        "  dataset_gb: 1\n"
        "  parallel_jobs: 1\n"
        "  詳細:\n"
        "    cost_estimate:\n"
        "      train_minutes: 9999\n"
        "      epochs: 10\n"
        "      dataset_gb: 1\n"
        "      parallel_jobs: 1\n"
    ) + _GOAL_COMPLETE
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2
    assert "リソース超過" in result.stderr


def test_t37_nested_goal_invalid_direction_detected(tmp_path: Path) -> None:
    """T-37: 外側 goal が正常でも、内側に入れ子の本物で direction が不正なら exit 2。

    ブロック確定後に本文の終端まで走査位置を飛ばす実装は、内側により深い
    インデントで入れ子になった同名ブロックを取りこぼす(実測 exit 0)。
    1行ずつ走査する修正版は入れ子のブロックも独立に検査して exit 2 にする。
    """
    plan_text = (
        "学習ジョブを実行する\n" + _COST_COMPLETE + "goal:\n"
        "  metric: rmse\n"
        "  target: 0.15\n"
        "  direction: minimize\n"
        "  baseline: 0.21\n"
        "  guard_metrics: []\n"
        "  詳細:\n"
        "    goal:\n"
        "      metric: rmse\n"
        "      target: 0.15\n"
        "      direction: down\n"
        "      baseline: 0.21\n"
        "      guard_metrics: []\n"
    )
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2


def test_t38_consecutive_empty_then_eof_block_both_extracted(tmp_path: Path) -> None:
    """T-38: 空ブロックの直後に続くブロックと、EOFで終わる複数ブロックが両方とも抽出される。

    先頭の空 `cost_estimate:`(直後に次の見出しが続くため本文0行)と、
    ファイル末尾でそのまま終わる本物の `cost_estimate:` の両方が独立に
    検査されることを、両方の由来のエラーメッセージが出ることで確認する。
    """
    plan_text = (
        "学習ジョブを実行する\n" + _GOAL_COMPLETE + "cost_estimate:\n"
        "cost_estimate:\n"
        "  train_minutes: 9999\n"
        "  epochs: 5\n"
        "  dataset_gb: 1\n"
        "  parallel_jobs: 1\n"
    )
    result = _run(
        tmp_path,
        branch="pipeline/20260726-foo",
        plan_name="20260726-foo.md",
        plan_text=plan_text,
    )
    assert result.returncode == 2
    assert "cost_estimate.train_minutes が未定義です" in result.stderr
    assert "リソース超過" in result.stderr
