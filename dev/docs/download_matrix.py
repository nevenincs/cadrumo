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


class DownloadChannel(BaseModel):
    """One stable, version-agnostic install channel."""

    # Not strict: the descriptor is loaded from TOML, so list->tuple and
    # str->enum coercion at the boundary is intended.
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    artifact_kinds: tuple[ArtifactKind, ...] = Field(min_length=1)
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
    channel: tuple[DownloadChannel, ...] = Field(min_length=1)

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


def required_evidence_rows(descriptor: DownloadDescriptor) -> tuple[str, ...]:
    """Return every distribution-evidence row the inventory must prove.

    A channel is listed because the product publishes to it, so every listed
    channel owes its rows. A channel that cannot be proven is removed from the
    inventory rather than left declared and unproven.
    """
    return tuple(sorted({row for channel in descriptor.channel for row in channel.evidence_rows}))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _install_block(channel: DownloadChannel) -> str:
    """Return the per-channel install section.

    A channel with install commands renders them in a fenced code block; one
    without renders the registry it is acquired from instead.
    """
    heading = f"**{channel.title}**: {channel.platform}"
    if channel.install_commands:
        commands = chr(10).join(channel.install_commands)
        return f"{heading}" + chr(10) * 2 + "```bash" + chr(10) + commands + chr(10) + "```" + chr(10)
    return f"{heading}" + chr(10) * 2 + f"Acquire it through {channel.registry}." + chr(10)


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
        lines.append(f"  - {channel.registry}")
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
