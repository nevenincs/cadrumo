"""Gates for the generated download-channel matrix.

Real-behavior tests over :mod:`dev.docs.download_matrix`: the descriptor loads
and strictly validates, every :class:`~dev.packaging.cohort_manifest.ArtifactKind`
is surfaced by exactly one documented channel (parity), the ``--check`` drift gate
fires on a mutated zone, and ``docs/download.md`` carries the generated marker
zone. No mocks — the real descriptor, the real page, and the real cohort schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

import pytest

from dev._paths import REPO_ROOT

from ...packaging.cohort_manifest import ArtifactKind
from ..download_matrix import (
    _ZONE_BEGIN,
    _ZONE_END,
    ChannelTier,
    DownloadDescriptor,
    build_download_latest,
    download_page_path,
    load_descriptor,
    main,
    render_page,
    render_zone,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]

_REPO_ROOT: Final[Path] = REPO_ROOT


def test_descriptor_loads_and_validates() -> None:
    """The committed descriptor loads under the strict pydantic schema."""
    descriptor = load_descriptor()
    assert isinstance(descriptor, DownloadDescriptor)
    assert descriptor.channel, "descriptor must declare at least one channel"


def test_every_artifact_kind_has_a_documented_channel() -> None:
    """Parity: every cohort ArtifactKind is surfaced by exactly one channel row.

    A cohort ArtifactKind with no documented channel row is the failure this
    gate exists to catch — a new artifact kind that ships without a place in the
    download page.
    """
    descriptor = load_descriptor()
    covered: dict[ArtifactKind, list[str]] = {}
    for channel in descriptor.channel:
        for kind in channel.artifact_kinds:
            covered.setdefault(kind, []).append(channel.id)

    missing = sorted(kind.value for kind in ArtifactKind if kind not in covered)
    assert not missing, (
        f"cohort ArtifactKind(s) {missing} have no documented download channel; "
        "add them to a channel's artifact_kinds in docs/_data/download_channels.toml"
    )
    duplicated = {kind.value: ids for kind, ids in covered.items() if len(ids) > 1}
    assert not duplicated, f"artifact kind(s) claimed by more than one channel: {duplicated}"


def test_runtime_wheelhouse_belongs_to_the_base_python_channel() -> None:
    """The generic offline runtime closure is part of Python acquisition.

    It must not recreate a host-extension or client-specific download channel.
    """
    descriptor = load_descriptor()
    owners = [
        channel.id
        for channel in descriptor.channel
        if ArtifactKind.PYTHON_WHEELHOUSE in channel.artifact_kinds
    ]
    assert owners == ["python"]
    # The claim is about WHERE the wheelhouse lives, not about whether the
    # product extends a host application at all: both host-extension channels
    # ship, so the wheelhouse earns its home by its owner being the language
    # registry rather than one of them.
    owner = next(channel for channel in descriptor.channel if channel.id == "python")
    assert owner.tier is ChannelTier.REGISTRY


def test_generated_zone_present_in_download_page() -> None:
    """docs/download.md carries the generated marker zone."""
    page_text = download_page_path().read_text(encoding="utf-8")
    assert _ZONE_BEGIN in page_text
    assert _ZONE_END in page_text
    assert page_text.index(_ZONE_BEGIN) < page_text.index(_ZONE_END)
    assert "data-cadrumo-downloads" in page_text, "Tier-2 mount element must be present in the generated zone"


def test_check_is_clean_for_committed_page() -> None:
    """The committed download.md is in sync with the descriptor (drift gate clean)."""
    assert main(["--check"]) == 0


def test_check_fails_on_mutated_zone() -> None:
    """Mutating the generated zone makes render_page differ from disk (drift detected)."""
    descriptor = load_descriptor()
    page_text = download_page_path().read_text(encoding="utf-8")
    fresh = render_page(descriptor, page_text)
    # Corrupt the zone body between the markers.
    begin = fresh.index(_ZONE_BEGIN) + len(_ZONE_BEGIN)
    mutated = fresh[:begin] + "\nMUTATED DRIFT LINE\n" + fresh[begin:]
    assert mutated != fresh
    # A re-render of the mutated page restores the canonical zone, proving the
    # check would flag the mutation as drift.
    restored = render_page(descriptor, mutated)
    assert restored == fresh


def test_zone_withholds_literal_commands_for_gated_channels() -> None:
    """Gated (public_launch) channels never emit a bare install command.

    This is the guard that keeps the page from advertising a channel ahead of
    its passing distribution evidence (see test_distribution_claims).
    """
    descriptor = load_descriptor()
    zone = render_zone(descriptor)
    for channel in descriptor.channel:
        if channel.availability.value == "public_launch":
            for command in channel.install_commands:
                assert command not in zone, (
                    f"gated channel {channel.id!r} leaked literal command {command!r} into the generated zone"
                )


def _write_cohort_manifest(directory: Path) -> Path:
    """Write a minimal-but-valid cohort manifest and its artifact files."""
    from datetime import UTC, datetime

    from ...packaging.cohort_manifest import (
        REQUIRED_ARTIFACT_KINDS,
        BuildIdentity,
        SourceIdentity,
        create_manifest,
        write_manifest,
    )

    artifacts: list[tuple[str, ArtifactKind, Path]] = []
    for name, kind in REQUIRED_ARTIFACT_KINDS.items():
        artifact = directory / f"{name}.bin"
        artifact.write_bytes(name.encode("utf-8"))
        artifacts.append((name, kind, artifact))
    manifest = create_manifest(
        root=directory,
        version="9.9.9",
        source=SourceIdentity(commit="a" * 40),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        builder=BuildIdentity(
            implementation="dev.packaging.release_cohort",
            format_version=1,
            python="3.13.0",
            uv="0.0.0",
            platform="test",
            architecture="x86_64",
            build_constraints_sha256="b" * 64,
        ),
        artifacts=artifacts,
    )
    return write_manifest(directory, manifest)


def test_emit_latest_projects_cohort_manifest(tmp_path: Path) -> None:
    """emit-latest projects a real cohort manifest into a typed download payload."""
    manifest_path = _write_cohort_manifest(tmp_path)
    payload = build_download_latest(
        cohort_manifest_path=manifest_path,
        release_base_url="https://github.com/nevenincs/cadrumo/releases/download/v9.9.9",
    )
    assert payload.schema_name == "cadrumo.download-latest.v1"
    assert payload.version == "9.9.9"
    assert payload.assets, "payload must carry the cohort assets"
    for asset in payload.assets:
        assert asset.url is not None and asset.url.endswith(asset.filename)
        assert len(asset.sha256) == 64

    # The emitted JSON round-trips back through the typed model.
    output = tmp_path / "download-latest.json"
    assert main(["emit-latest", "--cohort-manifest", str(manifest_path), "--output", str(output)]) == 0
    reloaded = json.loads(output.read_text(encoding="utf-8"))
    assert reloaded["schema_name"] == "cadrumo.download-latest.v1"


@pytest.mark.parametrize(
    "release_base_url",
    ("not-a-url", "http://example.invalid/releases/v9.9.9", "https://example.invalid/releases/v9.9.9?asset=x"),
)
def test_emit_latest_refuses_malformed_or_noncanonical_release_base_url(tmp_path: Path, release_base_url: str) -> None:
    """Asset URLs are derived only from an unambiguous HTTPS release directory."""
    manifest_path = _write_cohort_manifest(tmp_path)

    with pytest.raises(ValueError, match="release_base_url"):
        build_download_latest(cohort_manifest_path=manifest_path, release_base_url=release_base_url)
