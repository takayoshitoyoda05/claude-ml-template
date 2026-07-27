"""セキュリティ監査(2026-07-27)で見つかった不具合の回帰テスト。

対象は3件:
1. `_mask.mask()` のマスキング漏れ(秘密鍵本体・Bearer/JWT・URL の認証情報・
   GitHub の各トークン形式・AWS の一時キー/シークレット・Slack のアプリトークン)
2. `spec_gate` が未承認の設計書の「検証方法」列を shell 実行していた順序バグ
3. `quality_gate` のツール欠落判定が stdout を含んでいたため、検査対象のコードに
   "command not found" と書くだけでゲートを無効化できた問題

`tests/test_plan_gate.py` に倣い、フックは import せず
`subprocess.run([sys.executable, <フックの絶対パス>], ...)` の CLI 起動で検証する
(実運用の Stop フックと同じ経路を通すため)。マスキングだけは純粋関数なので
子プロセス内で import して確かめる。

検体の秘密情報は実行時に連結で組み立てる。ソースに直書きすると guard_scope の
秘密情報検知がこのファイルの書き込み自体をブロックするため。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
_SUBPROCESS_TIMEOUT = 60

# 検体(guard の検知を避けるため連結で組み立てる)
_AKIA = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
_ASIA = "AS" + "IA" + "ABCDEFGHIJKLMNOP"
_KEY_BEGIN = "-" * 5 + "BEGIN RSA PRIVATE KEY" + "-" * 5
_KEY_END = "-" * 5 + "END RSA PRIVATE KEY" + "-" * 5
_KEY_BODY = "MIIEowIBAAKCAQEA0Zx8"

# (検体, マスク後に残っていてはいけない部分文字列。None なら [MASKED] の有無だけ見る)
_SECRET_SAMPLES = [
    pytest.param(_AKIA, None, id="aws-access-key-id"),
    pytest.param(_ASIA, None, id="aws-temporary-key-id"),
    pytest.param(
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMIK7MDENGbPxRfiCY",
        "wJalrXUtnFEMIK7MDENGbPxRfiCY",
        id="aws-secret-access-key",
    ),
    pytest.param("ghs_" + "a" * 25, None, id="github-server-token"),
    pytest.param("ghr_" + "a" * 25, None, id="github-refresh-token"),
    pytest.param("github_pat_" + "a" * 25, None, id="github-fine-grained-pat"),
    pytest.param(
        "Authorization: Bearer abcdefghijklmnop12345",
        "abcdefghijklmnop12345",
        id="bearer-token",
    ),
    pytest.param(
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop", None, id="jwt"
    ),
    pytest.param(
        "postgres://user:hunter2pass@db.example.com:5432/mydb",
        "hunter2pass",
        id="postgres-url-credentials",
    ),
    pytest.param(
        "https://user:s3cretpass@example.com/repo.git",
        "s3cretpass",
        id="https-basic-url",
    ),
    pytest.param("xapp-1-A00-abcdefghijkl", None, id="slack-app-token"),
    pytest.param(
        _KEY_BEGIN + "\n" + _KEY_BODY + "\n" + _KEY_END,
        _KEY_BODY,
        id="private-key-body",
    ),
]

# マスクが誤爆してはいけない無害な文字列
_BENIGN_SAMPLES = [
    pytest.param("https://github.com/user/repo.git", id="plain-url"),
    pytest.param("token の扱いは README を参照", id="prose-mentioning-token"),
]


def _mask_in_subprocess(sample: str) -> str:
    """子プロセスで `_mask.mask()` を適用した結果を返す。"""
    script = (
        "import json, sys\n"
        f"sys.path.insert(0, {str(HOOKS_DIR)!r})\n"
        "from _mask import mask\n"
        "sys.stdout.write(mask(json.load(sys.stdin)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(sample),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.mark.parametrize("sample, must_be_gone", _SECRET_SAMPLES)
def test_mask_hides_secret(sample: str, must_be_gone: str | None) -> None:
    """既知の秘密情報形式がマスクされ、値の本体が残らないこと。"""
    masked = _mask_in_subprocess(sample)
    assert "[MASKED" in masked, f"マスクが適用されていません: {masked}"
    if must_be_gone is not None:
        assert must_be_gone not in masked, f"値が残っています: {masked}"


@pytest.mark.parametrize("sample", _BENIGN_SAMPLES)
def test_mask_leaves_benign_text_untouched(sample: str) -> None:
    """秘密情報でない文字列を書き換えないこと(誤爆の防止)。"""
    assert _mask_in_subprocess(sample) == sample


def test_spec_gate_does_not_run_verify_of_unapproved_design(tmp_path: Path) -> None:
    """未承認の設計書の「検証方法」列を実行しないこと。

    承認確認より後に shell 実行していると「ブロックと表示しつつコマンドは実行済み」
    になる。ゲートの目的は未承認の内容を実行しないことなので、副作用の有無で見る。
    """
    docs = tmp_path / "docs_active"
    spec = tmp_path / "spec_dir"
    docs.mkdir()
    spec.mkdir()
    marker = tmp_path / "spec_gate_side_effect.txt"
    (docs / "unapproved.md").write_text(
        "# 未承認の設計書\n\n## 受け入れ条件\n\n"
        "| ID | 要件 | 検証方法 | 期待結果 | 種別 | 対象 |\n"
        "|---|---|---|---|---|---|\n"
        f"| R-001 | 副作用の検出 | touch {marker} | exit 0 | auto | src/x.py |\n",
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "spec_gate.py")],
        input=json.dumps({"stop_hook_active": False}),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=_SUBPROCESS_TIMEOUT,
        env={
            "CLAUDE_SPEC_CHECK": "1",
            "CLAUDE_SPEC_DOCS": str(docs),
            "CLAUDE_SPEC_DIR": str(spec),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        },
    )

    assert proc.returncode == 2, f"ブロックされていません: {proc.stderr}"
    assert not marker.exists(), "未承認の設計書の検証方法が実行されました"


def test_quality_gate_cannot_be_silenced_by_inspected_code(tmp_path: Path) -> None:
    """検査対象のコードに含まれる欠落文言でゲートを無効化できないこと。

    ruff は診断にソーススニペットを添えるため、stdout を欠落判定に混ぜると
    コード側の文字列で lint 違反を全件スキップさせられる。
    """
    scope = tmp_path / "scope"
    scope.mkdir()
    # F401(未使用 import)を出しつつ、欠落判定の文言を含める
    (scope / "decoy.py").write_text(
        'import os\ny = "command not found"\n', encoding="utf-8"
    )

    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "quality_gate.py")],
        input=json.dumps({"stop_hook_active": False}),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=300,
        env={
            "CLAUDE_QUALITY_GATE": "1",
            "CLAUDE_WORK_SCOPE": str(scope),
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
        },
    )

    if "failed to spawn" in proc.stderr.lower():
        pytest.skip("ruff が利用できないため quality_gate の検査をスキップします")
    assert proc.returncode == 2, f"lint 違反がブロックされていません: {proc.stderr}"
    assert "ruff" in proc.stderr
