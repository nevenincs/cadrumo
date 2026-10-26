"""Build credentials cross only private staging and distributable resource boundaries."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from cadrumo.core import config_google
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command
from dev.packaging.google_oauth import (
    GOOGLE_OAUTH_ENV,
    GOOGLE_OAUTH_RESOURCE,
    build_client_json,
    client_build_identity,
    stage_build_client,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def client_document(identity: str = "synthetic-client") -> str:
    return json.dumps(
        {
            "installed": {
                "client_id": identity,
                "client_secret": "synthetic-secret",
                "project_id": "synthetic-project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost"],
            }
        }
    )


@pytest.fixture(autouse=True)
def isolate_credentials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(GOOGLE_OAUTH_ENV, raising=False)
    monkeypatch.setattr(config_google, "installation_client_source", lambda: tmp_path / "absent")


def write_dotenv(root: Path, payload: str) -> None:
    path = root / "env/.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{GOOGLE_OAUTH_ENV}='{payload}'\n", encoding="utf-8")


def test_local_dotenv_and_ci_environment_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_dotenv(tmp_path, client_document("local"))
    assert build_client_json(tmp_path).get_secret_value() == client_document("local")
    monkeypatch.setenv(GOOGLE_OAUTH_ENV, client_document("ci"))
    assert build_client_json(tmp_path).get_secret_value() == client_document("ci")


def test_distribution_resource_roundtrip_without_environment(tmp_path: Path) -> None:
    source, distribution = tmp_path / "checkout", tmp_path / "sdist"
    write_dotenv(source, client_document())
    selected = build_client_json(source)
    staged = stage_build_client(distribution, selected)
    assert staged == distribution / GOOGLE_OAUTH_RESOURCE
    assert staged.read_text(encoding="utf-8") == client_document()
    assert build_client_json(distribution) == selected
    assert not (source / GOOGLE_OAUTH_RESOURCE).exists()


def test_absent_config_does_not_borrow_installed_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    installed = tmp_path / "other-installation.json"
    installed.write_text(client_document(), encoding="utf-8")
    monkeypatch.setattr(config_google, "installation_client_source", lambda: installed)
    with pytest.raises(ValueError, match="before packaging"):
        build_client_json(tmp_path)


def test_optional_development_provisioning_allows_only_absence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert build_client_json(tmp_path, required=False) is None
    monkeypatch.setenv(GOOGLE_OAUTH_ENV, "invalid-synthetic-configuration")
    with pytest.raises(ValueError, match="complete Google Desktop"):
        build_client_json(tmp_path, required=False)


@pytest.mark.parametrize("payload", ["not-json synthetic-secret", '{"web":{}}', '{"installed":{}}'])
def test_invalid_build_input_refuses_without_disclosure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    monkeypatch.setenv(GOOGLE_OAUTH_ENV, payload)
    with pytest.raises(ValueError, match="complete Google Desktop") as caught:
        build_client_json(tmp_path)
    assert payload not in str(caught.value)
    assert "synthetic-secret" not in str(caught.value)


def test_changed_credentials_invalidate_product_cache(tmp_path: Path) -> None:
    write_dotenv(tmp_path, client_document("first"))
    first = build_client_json(tmp_path)
    write_dotenv(tmp_path, client_document("second"))
    second = build_client_json(tmp_path)
    before = client_build_identity("source-digest", first)
    assert before != client_build_identity("source-digest", second)
    assert before == client_build_identity("source-digest", first)
    assert "synthetic" not in before


def test_hatch_wheel_sdist_and_sdist_rebuild_embed_the_same_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hatchling.builders.sdist import SdistBuilder
    from hatchling.builders.wheel import WheelBuilder

    root = tmp_path / "source"
    for relative in (
        "packaging/authority/hatch_build.py",
        "dev/__init__.py",
        "dev/packaging/__init__.py",
        "dev/packaging/google_oauth.py",
        "src/cadrumo/__init__.py",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / relative, destination)
    # Include the real core closure, including dynamically registered errors,
    # so the isolated backend cannot borrow any editable checkout modules.
    for source in (REPO_ROOT / "src/cadrumo/core").rglob("*.py"):
        if "tests" in source.parts or source.name == "conftest.py":
            continue
        destination = root / source.relative_to(REPO_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    package = root / "src/cadrumo"
    package.mkdir(parents=True, exist_ok=True)
    authority = package / "_data/registry/authority"
    authority.mkdir(parents=True)
    payload = b"synthetic authority bytes"
    digest = hashlib.sha256(payload).hexdigest()
    database = f"authority-{digest}.sqlite3"
    (authority / database).write_bytes(payload)
    (authority / "authority.current.json").write_text(
        json.dumps({"database": database, "database_sha256": digest, "database_size": len(payload)}),
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname="cadrumo"\nversion="0.0.0"\n'
        '[tool.hatch.build.targets.wheel]\npackages=["src/cadrumo"]\n'
        "[tool.hatch.build.targets.sdist]\n"
        'only-include=["src/cadrumo", "packaging/authority/hatch_build.py", "pyproject.toml"]\n'
        'exclude=["dev/**"]\n'
        '[tool.hatch.build.hooks.custom]\npath="packaging/authority/hatch_build.py"\n',
        encoding="utf-8",
    )
    write_dotenv(root, client_document())
    monkeypatch.delenv("CADRUMO_AUTHORITY_ROOT", raising=False)
    output = tmp_path / "output"
    output.mkdir()
    wheel = Path(next(WheelBuilder(str(root)).build(directory=str(output))))
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read("cadrumo/_data/google/oauth_client.json").decode() == client_document()
        assert not any(name.startswith("dev/") or name.endswith(".env") for name in archive.namelist())
    sdist = Path(next(SdistBuilder(str(root)).build(directory=str(output))))
    extracted = tmp_path / "extracted"
    with tarfile.open(sdist) as archive:
        archive.extractall(extracted, filter="data")
    rebuild_root = extracted / "cadrumo-0.0.0"
    result = run_command(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from pathlib import Path; root = Path.cwd(); "
            "sys.path[:0] = [str(root / 'src'), str(root)]; "
            "from hatchling.builders.wheel import WheelBuilder; "
            "list(WheelBuilder(str(root)).build(directory=sys.argv[1])); "
            "from cadrumo.core.config_google import GoogleOAuthClientSettings; "
            "assert GoogleOAuthClientSettings().cadrumo_google_oauth_client_json is not None; "
            "assert all(Path(module.__file__).is_relative_to(root) for name, module in sys.modules.items() "
            "if (name == 'cadrumo' or name.startswith('cadrumo.') or name == 'dev' or name.startswith('dev.')) "
            "and getattr(module, '__file__', None))",
            str(output),
        ],
        cwd=rebuild_root,
    )
    assert result.returncode == 0, result.stderr
    rebuilt = output / wheel.name
    with zipfile.ZipFile(rebuilt) as archive:
        assert archive.read("cadrumo/_data/google/oauth_client.json").decode() == client_document()
