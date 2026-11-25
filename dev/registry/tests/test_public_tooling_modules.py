from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from pydantic import ValidationError

from ..conformance.model import ConformanceModel
from ..pipeline import authority_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _SampleFact(ConformanceModel):
    count: int


def test_conformance_model_enforces_strict_frozen_values() -> None:
    fact = _SampleFact(count=3)

    with pytest.raises(ValidationError):
        _SampleFact(count="3")
    with pytest.raises(ValidationError):
        fact.count = 4


def test_publish_authority_requires_profile_schema_for_custom_roots() -> None:
    with pytest.raises(typer.BadParameter, match="explicit --profile-schema"):
        authority_cli.publish_authority(registry_root=Path("custom-registry"))


def test_publish_authority_if_stale_skips_publication_when_current(monkeypatch, capsys) -> None:
    calls: list[tuple[Path, Path, Path, Path]] = []
    destination = Path("authority")

    def currency(path: Path, *, registry_root: Path, source_root: Path, profile_schema_path: Path):
        calls.append((path, registry_root, source_root, profile_schema_path))
        return SimpleNamespace(
            is_current=True,
            descriptor_path=path,
            recorded_identity_digest="identity",
        )

    def unexpected_publish(**kwargs):
        pytest.fail(f"current authority must skip publication: {kwargs}")

    monkeypatch.setattr(authority_cli, "authority_database_currency", currency)
    monkeypatch.setattr(authority_cli, "publish_sqlite_authority_candidate", unexpected_publish)

    authority_cli.publish_authority(destination=destination, if_stale=True)

    assert calls and calls[0][0] == destination / "authority.current.json"
    assert "published=skipped-current" in capsys.readouterr().out
