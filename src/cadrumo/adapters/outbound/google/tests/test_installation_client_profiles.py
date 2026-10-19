"""Every profile signs in with the one installation-wide Google client; no profile holds a copy."""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.config_google import installation_client_source
from .....core.resources.bundled_data import packaged_data
from ....persistence.storage.tests.secure_sql import isolated_two_bucket_runtime
from ..installation_client import load_installation_client
from .installation_client_support import use_installation_client

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_the_installation_reads_its_client_from_its_own_package_data() -> None:
    source = Path(str(installation_client_source()))

    assert source.parts[-2:] == ("google", "oauth_client.json")
    assert source.is_relative_to(Path(str(packaged_data())))


def test_both_profiles_load_the_same_client_and_neither_folder_holds_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installation = tmp_path / "installation"
    installed = use_installation_client(monkeypatch, installation)
    profiles = tmp_path / "profiles"
    profiles.mkdir()

    with isolated_two_bucket_runtime(tmp_path=profiles) as runtime:
        for_a = load_installation_client()
        with runtime.switch_to_secondary():
            for_b = load_installation_client()
        root = runtime.primary.storage_root
        copies = [str(path.relative_to(root)) for path in root.rglob("oauth_client*.json")]

    assert for_a == for_b == installed
    assert not installation.is_relative_to(root)
    assert copies == []
