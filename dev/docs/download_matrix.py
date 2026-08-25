"""Generated download-channel matrix for ``docs/download.md``.

Reads the committed, schema-validated channel descriptor
(``docs/_data/download_channels.toml``) — the single source of truth for the
stable, version-agnostic facts about each install channel — and injects a
rendered channel table plus per-channel install commands into the
``vaultspec:generated`` marker zone of ``docs/download.md``. Hand-authored prose
outside the marker zone is never touched, mirroring the
``generated-reference-is-cli-owned`` discipline the CLI reference follows.

Sources of truth (never duplicated):

* Stable channel facts (channel id, platform, install commands, package /
  marketplace / bucket / tap names, availability state) live in the descriptor
  this module reads.
* The artifact-kind taxonomy is :class:`~dev.packaging.cohort_manifest.ArtifactKind`;
  every kind must be surfaced by exactly one channel's ``artifact_kinds`` and the
  parity gate in :mod:`dev.docs.tests.test_download_matrix` fails otherwise.
* Version, filenames, and sha256 digests are release-time facts carried by the
  cohort manifest; the ``emit-latest`` verb projects them into the runtime
  ``download-latest.json`` progressive-enhancement payload.

Availability gating
-------------------
A channel whose ``availability`` is ``public_launch`` is not yet publicly live
(the beta stance in ``docs/workstation-setup.md``): its literal install command
is withheld from the generated zone and an "at public launch" line is rendered
instead, so the page never advertises a channel ahead of its passing
distribution evidence (:mod:`dev.docs.tests.test_distribution_claims`). Flip the
descriptor to ``available`` in the same change that lands the evidence and the
literal command block renders.

Tier 1 (this generator) is build-time, offline, and always runs; Tier 2 is the
optional runtime ``download-latest.json`` fetched by ``initDownloadCards()`` in
``docs/_static/cadrumo-docs.js``, which silently degrades to this table when the
file is absent.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from .._paths import REPO_ROOT, UTF_8
from ..packaging.cohort_manifest import ArtifactKind

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Self

_UTF_8: Final[str] = UTF_8

#: Marker slug for the generated zone in ``docs/download.md`` (the
#: ``vaultspec:generated`` convention shared with the CLI reference).
_ZONE_SLUG: Final[str] = "download-matrix"
_ZONE_BEGIN: Final[str] = f"<!-- vaultspec:generated:begin {_ZONE_SLUG} -->"
_ZONE_END: Final[str] = f"<!-- vaultspec:generated:end {_ZONE_SLUG} -->"

_REGEN_HINT: Final[str] = "uv run --no-sync python -m dev.docs.download_matrix generate"


class Availability(StrEnum):
    """Closed set of publication states for one download channel."""

    AVAILABLE = "available"
    PUBLIC_LAUNCH = "public_launch"


class ChannelTier(StrEnum):
    """Closed set of channel tiers the account-wide matrix rule selects over.

    A tier is a *kind* of channel, not a product's choice: the rule in
    :func:`derived_tiers` decides which tiers a product ships from three declared
    properties, so a product that does not exist yet still gets an answer.
    """

    REGISTRY = "registry"
    STANDALONE_EXECUTABLE = "standalone-executable"
    SHARED_TAP = "shared-tap"
    SHARED_BUCKET = "shared-bucket"
    COMMUNITY_WINDOWS = "community-windows"
    HOST_EXTENSION = "host-extension"


#: Tiers that exist for users who cannot be assumed to hold the language
#: toolchain. They are selected together because they answer one need — an
#: install that does not presuppose a developer environment.
_MANAGED_INSTALLER_TIERS: Final[frozenset[ChannelTier]] = frozenset(
    {
        ChannelTier.SHARED_TAP,
        ChannelTier.SHARED_BUCKET,
        ChannelTier.COMMUNITY_WINDOWS,
    },
)


class ChannelMatrix(BaseModel):
    """The per-product input to the account-wide derived channel matrix.

    These are the only product-specific facts the rule consumes. Everything else
    about which channels a product ships is computed, which is what lets one rule
    serve a product nobody has described yet.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    exposes_user_invoked_command: bool
    assumes_language_toolchain: bool
    extends_host_application: bool
    #: Tiers the rule selects that this product does not ship yet. Declared so
    #: the gap is visible data rather than a silent absence.
    pending_tiers: tuple[ChannelTier, ...] = ()

    @model_validator(mode="after")
    def _pending_tiers_are_unique_and_selected(self) -> Self:
        if len(set(self.pending_tiers)) != len(self.pending_tiers):
            raise ValueError("pending_tiers lists a duplicate tier")
        unselected = sorted(tier.value for tier in self.pending_tiers if tier not in derived_tiers(self))
        if unselected:
            raise ValueError(
                f"pending_tiers names tier(s) the matrix rule does not select: {unselected}; "
                "a tier the rule excludes is not pending, it is simply not this product's",
            )
        return self


def derived_tiers(matrix: ChannelMatrix) -> frozenset[ChannelTier]:
    """Return the channel tiers the account matrix rule selects for a product.

    The rule, from the account distribution standard: every product ships its
    language-native registry (the floor, and the only channel where dependency
    resolution happens); a product exposing a user-invoked command additionally
    ships standalone per-platform executables, which removes the toolchain
    prerequisite; a product exposing a user-invoked command to an audience that
    cannot be assumed to hold the toolchain additionally ships the managed
    installers; and, orthogonally, a product extending a host application ships
    that host's own channel.
    """
    tiers = {ChannelTier.REGISTRY}
    if matrix.exposes_user_invoked_command:
        tiers.add(ChannelTier.STANDALONE_EXECUTABLE)
        if not matrix.assumes_language_toolchain:
            tiers |= _MANAGED_INSTALLER_TIERS
    if matrix.extends_host_application:
        tiers.add(ChannelTier.HOST_EXTENSION)
    return frozenset(tiers)


class DownloadChannel(BaseModel):
    """One stable, version-agnostic install channel."""

    # Not strict: the descriptor is loaded from TOML, so list->tuple and
    # str->enum coercion at the boundary is intended.
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    tier: ChannelTier
    artifact_kinds: tuple[ArtifactKind, ...] = Field(min_length=1)
    availability: Availability
    package: str = Field(min_length=1)
    registry: str = Field(min_length=1)
    #: Distribution-evidence row ids this channel must produce before it may be
    #: claimed. The readiness gate derives its required set from these.
    evidence_rows: tuple[str, ...] = Field(min_length=1)
    install_commands: tuple[str, ...] = ()
    bucket: str | None = None
    bucket_repo: str | None = None
    tap: str | None = None
    marketplace: str | None = None
    marketplace_source: str | None = None

    @model_validator(mode="after")
    def _unique_kinds_and_rows(self) -> Self:
        if len(set(self.artifact_kinds)) != len(self.artifact_kinds):
            raise ValueError(f"channel {self.id!r} lists a duplicate artifact kind")
        if len(set(self.evidence_rows)) != len(self.evidence_rows):
            raise ValueError(f"channel {self.id!r} lists a duplicate evidence row")
        return self


class DownloadDescriptor(BaseModel):
    """The whole download-channel descriptor loaded from TOML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    matrix: ChannelMatrix
    channel: tuple[DownloadChannel, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _tiers_match_the_derived_matrix(self) -> Self:
        """Refuse a descriptor whose channels disagree with the derived rule.

        Present tiers plus declared-pending tiers must be exactly the tiers the
        rule selects. Dropping a channel therefore cannot pass unnoticed, and
        acquiring one the rule does not select cannot either.
        """
        selected = derived_tiers(self.matrix)
        present = {channel.tier for channel in self.channel}
        accounted = present | set(self.matrix.pending_tiers)
        if unselected := sorted(tier.value for tier in present - selected):
            raise ValueError(
                f"channel(s) declare tier(s) the matrix rule does not select: {unselected}; "
                "either the product properties in [matrix] are wrong or the channel does not belong",
            )
        if unaccounted := sorted(tier.value for tier in selected - accounted):
            raise ValueError(
                f"the matrix rule selects tier(s) no channel serves: {unaccounted}; "
                "ship the channel or declare the tier in [matrix] pending_tiers",
            )
        return self

    @model_validator(mode="after")
    def _evidence_rows_are_partitioned(self) -> Self:
        owner: dict[str, str] = {}
        for channel in self.channel:
            for row in channel.evidence_rows:
                if row in owner:
                    raise ValueError(
                        f"evidence row {row!r} is claimed by both {owner[row]!r} and {channel.id!r}; "
                        "each row proves exactly one channel",
                    )
                owner[row] = channel.id
        return self

    @model_validator(mode="after")
    def _kinds_are_partitioned(self) -> Self:
        ids = [channel.id for channel in self.channel]
        if len(set(ids)) != len(ids):
            raise ValueError("channel ids must be unique")
        seen: dict[ArtifactKind, str] = {}
        for channel in self.channel:
            for kind in channel.artifact_kinds:
                if kind in seen:
                    raise ValueError(
                        f"artifact kind {kind.value!r} is claimed by both {seen[kind]!r} and {channel.id!r}; "
                        "each ArtifactKind must be surfaced by exactly one channel",
                    )
                seen[kind] = channel.id
        missing = sorted(kind.value for kind in ArtifactKind if kind not in seen)
        if missing:
            raise ValueError(
                f"no download channel surfaces artifact kind(s): {missing}; "
                "add the kind to a channel's artifact_kinds in docs/_data/download_channels.toml",
            )
        return self


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def descriptor_path(repo_root: Path | None = None) -> Path:
    """Return the descriptor path under ``docs/_data``."""
    root = repo_root or REPO_ROOT
    return root / "docs" / "_data" / "download_channels.toml"


def download_page_path(repo_root: Path | None = None) -> Path:
    """Return the ``docs/download.md`` page path."""
    root = repo_root or REPO_ROOT
    return root / "docs" / "download.md"


def load_descriptor(path: Path | None = None) -> DownloadDescriptor:
    """Load and strictly validate the channel descriptor."""
    resolved = path or descriptor_path()
    raw = tomllib.loads(resolved.read_text(encoding=_UTF_8))
    return DownloadDescriptor.model_validate(raw)


# ---------------------------------------------------------------------------
# Claimed channels -> required evidence
# ---------------------------------------------------------------------------


def claimed_channels(descriptor: DownloadDescriptor) -> tuple[DownloadChannel, ...]:
    """Return the channels this release actually claims.

    A channel is claimed when it is publicly live (``availability = available``),
    because that is precisely when the documentation prints its literal install
    command and a reader can act on it. The language-native registry is always
    claimed regardless: it is the floor of the account standard, so the required
    evidence set can never collapse to nothing.
    """
    return tuple(
        channel
        for channel in descriptor.channel
        if channel.availability is Availability.AVAILABLE or channel.tier is ChannelTier.REGISTRY
    )


def required_evidence_rows(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return the distribution-evidence rows the claimed channels must prove.

    Evidence stays proportional to claims: a release claiming one channel proves
    one channel, a release claiming five proves five. No gate is weakened and no
    row is removed — an unclaimed channel simply stops blocking a claimed one.
    """
    return tuple(sorted({row for channel in claimed_channels(descriptor) for row in channel.evidence_rows}))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _availability_note(channel: DownloadChannel) -> str:
    """Return the "how you get the current beta" cell for one channel."""
    if channel.availability is Availability.AVAILABLE:
        return f"Release page artifact; {channel.registry} live"
    return f"Release page artifact; {channel.registry} at public launch"


def _install_block(channel: DownloadChannel) -> str:
    """Return the per-channel install section.

    An ``available`` channel renders its literal install commands in a fenced
    code block. A ``public_launch`` channel withholds the literal command (so the
    page never advertises a channel ahead of its passing distribution evidence)
    and renders an "at public launch" line instead.
    """
    heading = f"**{channel.title}**: {channel.platform}"
    if channel.availability is Availability.AVAILABLE and channel.install_commands:
        commands = "\n".join(channel.install_commands)
        return f"{heading}\n\n```bash\n{commands}\n```\n"
    if channel.availability is Availability.AVAILABLE and not channel.install_commands:
        return f"{heading}\n\nDownload the release-page artifact and install it through {channel.registry}.\n"
    return (
        f"{heading}\n\n"
        f"The {channel.registry} opens at public launch; until then, install the "
        f"release-page artifact attached to the latest release.\n"
    )


def render_zone(descriptor: DownloadDescriptor) -> str:
    """Render the generated marker-zone body (between, not including, the markers).

    The body carries a MyST ``list-table`` of every channel (platform, channel,
    availability), the per-channel install sections, and the Tier-2 mount element
    that ``initDownloadCards()`` fills at runtime.
    """
    lines: list[str] = []
    lines.append(f"<!-- GENERATED by {_REGEN_HINT} from docs/_data/download_channels.toml. Do not edit by hand. -->")
    lines.append("")
    lines.append("```{list-table}")
    lines.append(":header-rows: 1")
    lines.append(":widths: 34 26 40")
    lines.append("")
    lines.append("* - Platform")
    lines.append("  - Channel")
    lines.append("  - How you get the current beta")
    for channel in descriptor.channel:
        lines.append(f"* - {channel.platform}")
        lines.append(f"  - {channel.title}")
        lines.append(f"  - {_availability_note(channel)}")
    lines.append("```")
    lines.append("")
    lines.append("Per-channel install paths:")
    lines.append("")
    for channel in descriptor.channel:
        lines.append(_install_block(channel).rstrip())
        lines.append("")
    # Tier-2 progressive-enhancement mount: initDownloadCards() fills this with
    # the release version and direct asset links when download-latest.json is
    # present, and leaves it empty (this table is the floor) when it is absent.
    lines.append("<div data-cadrumo-downloads hidden></div>")
    return "\n".join(lines).rstrip() + "\n"


def _inject_zone(page_text: str, zone_body: str) -> str:
    """Return ``page_text`` with the marker zone replaced by ``zone_body``.

    Raises:
        ValueError: When the begin/end markers are absent or malformed.
    """
    begin = page_text.find(_ZONE_BEGIN)
    end = page_text.find(_ZONE_END)
    if begin == -1 or end == -1 or end < begin:
        raise ValueError(
            f"docs/download.md is missing the generated marker zone; expected {_ZONE_BEGIN!r} ... {_ZONE_END!r}",
        )
    prefix = page_text[:begin]
    suffix = page_text[end + len(_ZONE_END) :]
    return f"{prefix}{_ZONE_BEGIN}\n{zone_body}{_ZONE_END}{suffix}"


def render_page(descriptor: DownloadDescriptor, page_text: str) -> str:
    """Return the full ``download.md`` text with a freshly-rendered generated zone."""
    return _inject_zone(page_text, render_zone(descriptor))


def inject_download_matrix(docs_root: Path) -> None:
    """Regenerate the download.md zone in-place under ``docs_root``.

    Wired into the changed-source documentation build (:mod:`dev.docs.build`) so a
    descriptor edit previews correctly, mirroring how ``generate_cli_reference``
    regenerates the CLI reference into the temporary build tree.
    """
    repo_root = docs_root.parent
    descriptor = load_descriptor(descriptor_path(repo_root))
    page = docs_root / "download.md"
    fresh = render_page(descriptor, page.read_text(encoding=_UTF_8))
    _write_text_if_changed(page, fresh)


def _write_text_if_changed(path: Path, content: str) -> None:
    """Write ``content`` with LF newlines only when it differs from disk."""
    if path.is_file() and path.read_text(encoding=_UTF_8) == content:
        return
    path.write_text(content, encoding=_UTF_8, newline="\n")


# ---------------------------------------------------------------------------
# Tier 2 — download-latest.json runtime payload
# ---------------------------------------------------------------------------


class DownloadAsset(BaseModel):
    """One release asset projected into the runtime download payload."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: str = Field(min_length=1)
    kind: ArtifactKind
    filename: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(gt=0)
    url: str | None = None


class DownloadLatest(BaseModel):
    """Runtime payload consumed by ``initDownloadCards()`` (progressive enhancement)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_name: str = Field(pattern=r"^cadrumo\.download-latest\.v1$")
    version: str = Field(min_length=1)
    cohort_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    assets: tuple[DownloadAsset, ...] = Field(min_length=1)


_HTTP_URL_ADAPTER = TypeAdapter(AnyHttpUrl)


def _release_download_base_url(value: str) -> str:
    """Return one canonical HTTPS release directory URL suitable for asset projection."""
    try:
        parsed = _HTTP_URL_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError("release_base_url must be a canonical HTTPS URL without query or fragment components") from exc
    if parsed.scheme != "https" or parsed.query is not None or parsed.fragment is not None:
        raise ValueError("release_base_url must be a canonical HTTPS URL without query or fragment components")
    return str(parsed).rstrip("/")


def build_download_latest(
    *,
    cohort_manifest_path: Path,
    release_base_url: str | None = None,
) -> DownloadLatest:
    """Project a validated cohort manifest into the ``download-latest.json`` payload.

    Reads (never mutates) the ``cadrumo.release-cohort.v1`` manifest; each cohort
    artifact becomes a :class:`DownloadAsset` carrying its filename, sha256, and
    size. When ``release_base_url`` is given each asset also carries its direct
    download URL.
    """
    from ..packaging.cohort_manifest import CohortManifest

    manifest = CohortManifest.model_validate_json(cohort_manifest_path.read_text(encoding=_UTF_8))
    base = _release_download_base_url(release_base_url) if release_base_url else None
    assets = tuple(
        DownloadAsset(
            name=record.name,
            kind=record.kind,
            filename=Path(record.path).name,
            sha256=record.sha256,
            size=record.size,
            url=f"{base}/{Path(record.path).name}" if base else None,
        )
        for record in manifest.artifacts
    )
    return DownloadLatest(
        schema_name="cadrumo.download-latest.v1",
        version=manifest.version,
        cohort_id=manifest.cohort_id,
        assets=assets,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_generate(*, check: bool) -> int:
    descriptor = load_descriptor()
    page = download_page_path()
    on_disk = page.read_text(encoding=_UTF_8)
    fresh = render_page(descriptor, on_disk)
    if check:
        if on_disk != fresh:
            print(
                f"DRIFT: {page} generated zone is stale; regenerate with {_REGEN_HINT}",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {page} generated zone is fresh.")
        return 0
    _write_text_if_changed(page, fresh)
    print(f"Wrote {page}")
    return 0


def _run_emit_latest(args: argparse.Namespace) -> int:
    payload = build_download_latest(
        cohort_manifest_path=Path(args.cohort_manifest).resolve(strict=True),
        release_base_url=args.release_base_url,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload.model_dump_json(indent=2) + "\n", encoding=_UTF_8, newline="\n")
    print(f"Wrote {output.resolve()}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Render the generated zone, verify freshness (``--check``), or emit the runtime payload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when the download.md generated zone differs from fresh output (implies the generate verb).",
    )
    sub = parser.add_subparsers(dest="command")

    generate = sub.add_parser("generate", help="Inject the generated channel matrix into docs/download.md.")
    generate.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when the on-disk generated zone differs from fresh output.",
    )

    emit = sub.add_parser("emit-latest", help="Emit the runtime download-latest.json from a cohort manifest.")
    emit.add_argument("--cohort-manifest", required=True, help="Path to a cadrumo.release-cohort.v1 manifest JSON.")
    emit.add_argument(
        "--output",
        default="download-latest.json",
        help="Destination path for the emitted download-latest.json (default: ./download-latest.json).",
    )
    emit.add_argument(
        "--release-base-url",
        default=None,
        help="Immutable release download base URL; when given, each asset carries its direct URL.",
    )

    args = parser.parse_args(argv)

    if args.command == "emit-latest":
        return _run_emit_latest(args)
    # generate (default) — top-level --check or `generate --check` both drift-gate.
    check = bool(args.check or getattr(args, "check", False))
    return _run_generate(check=check)


if __name__ == "__main__":
    raise SystemExit(main())
