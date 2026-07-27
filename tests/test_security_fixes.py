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
import time
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
# AWS のシークレットアクセスキーは40文字(AWS 公式ドキュメントのダミー値と同形式)
_AWS_SECRET = "wJalrXUtnFEMI" + "/K7MDENG/" + "bPxRfiCYEXAMPLEKEY"

# (検体, マスク後に残っていてはいけない部分文字列 = 秘密の本体)
_SECRET_SAMPLES = [
    pytest.param(_AKIA, _AKIA, id="aws-access-key-id"),
    pytest.param(_ASIA, _ASIA, id="aws-temporary-key-id"),
    pytest.param(
        # AWS のシークレットは40文字。実形式で検査する
        f"AWS_SECRET_ACCESS_KEY={_AWS_SECRET}",
        _AWS_SECRET,
        id="aws-secret-access-key",
    ),
    pytest.param(
        f'AWS_SECRET_ACCESS_KEY="{_AWS_SECRET}"',
        _AWS_SECRET,
        id="aws-secret-access-key-quoted",
    ),
    pytest.param("ghs_" + "a" * 25, "ghs_" + "a" * 25, id="github-server-token"),
    pytest.param("ghr_" + "a" * 25, "ghr_" + "a" * 25, id="github-refresh-token"),
    pytest.param(
        "github_pat_" + "a" * 25,
        "github_pat_" + "a" * 25,
        id="github-fine-grained-pat",
    ),
    pytest.param(
        "Authorization: Bearer abcdefghijklmnop12345",
        "abcdefghijklmnop12345",
        id="bearer-token",
    ),
    pytest.param(
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop",
        id="jwt",
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
    pytest.param(
        "xapp-1-A00-abcdefghijkl", "xapp-1-A00-abcdefghijkl", id="slack-app-token"
    ),
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
def test_mask_hides_secret(sample: str, must_be_gone: str) -> None:
    """既知の秘密情報形式がマスクされ、値の本体が残らないこと。

    `[MASKED]` の有無だけを見ると、元の値を残したまま印を足す実装や一部分しか
    置換しない実装でも通ってしまう。秘密の本体が消えていることを常に必須にする。
    """
    masked = _mask_in_subprocess(sample)
    assert "[MASKED" in masked, f"マスクが適用されていません: {masked}"
    assert must_be_gone not in masked, f"値が残っています: {masked}"


@pytest.mark.parametrize("sample", _BENIGN_SAMPLES)
def test_mask_leaves_benign_text_untouched(sample: str) -> None:
    """秘密情報でない文字列を書き換えないこと(誤爆の防止)。"""
    assert _mask_in_subprocess(sample) == sample


@pytest.mark.parametrize(
    "sample, secret",
    [
        pytest.param(
            '{"api_key": "abcdefgh12345678"}', "abcdefgh12345678", id="json-api-key"
        ),
        pytest.param(
            '{"token":"abcdefgh12345678"}', "abcdefgh12345678", id="json-no-space"
        ),
        pytest.param(
            '{"AWS_SECRET_ACCESS_KEY": "' + _AWS_SECRET + '"}',
            _AWS_SECRET,
            id="json-aws-secret",
        ),
        pytest.param("api_key=abcdefgh12345678", "abcdefgh12345678", id="bare-equals"),
        pytest.param("password: hunter2pass99", "hunter2pass99", id="colon-separated"),
    ],
)
def test_mask_hides_value_in_json_and_bare_forms(sample: str, secret: str) -> None:
    """JSON 形式でも値を伏せ、周囲の非秘密フィールドは残すこと。

    action_log は `json.dumps()` の結果をマスクするため、実運用のログはほぼ
    すべて `{"api_key": "..."}` の形になる。キー名の直後に `=`/`:` を要求する
    実装では閉じ引用符が挟まって一致せず、素通りしていた。
    入力を丸ごと潰す実装で通らないよう、非秘密部分の保持も併せて見る。
    """
    # 秘密でないフィールドを前後に足し、それが残ることまで確かめる
    wrapped = '{"file_path": "src/train.py", "note": "keep me"} ' + sample
    masked = _mask_in_subprocess(wrapped)
    assert secret not in masked
    assert "src/train.py" in masked, "非秘密フィールドまで消えています"
    assert "keep me" in masked, "非秘密フィールドまで消えています"


def test_mask_hides_private_key_without_end_line() -> None:
    """END 行を欠く秘密鍵でも本体を残さず、前後の通常文は残すこと。

    出力が途中で切れた場合(clip 後など)を想定する。
    """
    truncated = (
        "before-marker\n"
        + _KEY_BEGIN
        + "\n"
        + _KEY_BODY
        + "\n...[clipped]\nafter-marker"
    )
    masked = _mask_in_subprocess(truncated)
    assert _KEY_BODY not in masked
    assert "before-marker" in masked, "鍵の前の通常文まで消えています"
    assert "after-marker" in masked, "鍵の後の通常文まで消えています"


def test_mask_completes_quickly_on_large_input() -> None:
    """巨大な入力でも実用的な時間で終わり、内容を変えないこと(ReDoS の回帰防止)。

    キー名の中核語の前後に `[A-Za-z0-9_-]*` を置く実装は、一致しない長い
    識別子で総当たりが起き、処理時間が入力長の2乗で伸びた(実測: 5万文字で
    約130秒)。action_log は毎ツール実行で走るため実害になる。
    入力を切り捨てて速くする実装で通らないよう、出力の一致も確かめる。
    """
    payload = ("A" * 2000 + "_" + "B" * 2000 + " ") * 12  # 約5万文字
    start = time.monotonic()
    masked = _mask_in_subprocess(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 10.0, f"マスクに {elapsed:.1f} 秒かかりました(ReDoS の疑い)"
    # 秘密情報を含まない入力なので、1文字も変わってはいけない
    assert masked == payload, "秘密情報でない入力が書き換えられています"


def test_mask_hides_whole_url_userinfo() -> None:
    """URL の認証情報はユーザー名側も含めて伏せ、接続先は残すこと。

    `https://<token>@github.com` のようにユーザー名の位置にトークンを置く
    認証方式があるため、パスワードだけを伏せる粒度では漏れる。一方でスキームと
    ホストまで潰すとログから接続先を追えないので、そこは残す。
    """
    masked = _mask_in_subprocess("postgres://appuser:hunter2pass@db.example.com/mydb")
    assert "hunter2pass" not in masked
    assert "appuser" not in masked, "ユーザー名が残っています"
    assert "db.example.com" in masked, "ホストまで消えています"

    # パスワードを伴わない、ユーザー名の位置だけのトークン。接頭辞だけ削って
    # 残りを漏らす実装を通さないよう、トークン全文が消えたことを見る
    token = "ghp_" + "b" * 25
    token_only = _mask_in_subprocess(f"https://{token}@github.com/o/r.git")
    assert token not in token_only, "ユーザー名位置のトークンが残っています"
    assert "b" * 25 not in token_only, "接頭辞だけが削られ本体が残っています"
    assert "github.com" in token_only


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

    # ruff の可否は quality_gate に尋ねず直接確かめる。quality_gate は欠落を
    # 内部で握って exit 0 にするため、その stderr からは可否を判別できない。
    # cwd はゲート側と揃える(uv はカレントのプロジェクト環境を見るため、
    # 別ディレクトリで確かめると可否の判定がゲート側と食い違う)
    try:
        probe = subprocess.run(
            ["uv", "run", "ruff", "check", str(scope)],
            capture_output=True,
            text=True,
            cwd=tmp_path,
            timeout=300,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
            },
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("uv が利用できないため quality_gate の検査をスキップします")
    probe_output = probe.stdout + probe.stderr
    if probe.returncode < 0 or "failed to spawn" in probe_output.lower():
        pytest.skip("ruff が利用できないため quality_gate の検査をスキップします")
    # このテストは「欺瞞文字列が ruff の出力に現れる」ことが前提。ruff の表示形式が
    # 変わって前提が崩れたら、検出力が無いまま緑になるので先に落とす
    assert "command not found" in probe.stdout, (
        "ruff の出力に欺瞞文字列が現れないため、このテストは "
        "stdout 経由の無効化を検出できません(ruff の表示形式の変更を確認してください)"
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

    assert proc.returncode == 2, f"lint 違反がブロックされていません: {proc.stderr}"
    assert "ruff" in proc.stderr
