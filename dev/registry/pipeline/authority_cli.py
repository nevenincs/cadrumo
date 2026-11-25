"""Publish the validated runtime registry authority."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cadrumo.core.resources.bundled_data import bundled_path

from .authority_publication import (
    authority_database_currency,
    authority_publication_destination,
    publish_sqlite_authority_candidate,
)


def publish_authority(
    registry_root: Annotated[
        Path | None,
        typer.Option("--registry-root", help="Registry tree to publish; defaults to the bundled registry."),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option("--source-root", help="Source tree holding the legal corpus; defaults to bundled data."),
    ] = None,
    destination: Annotated[
        Path | None,
        typer.Option(
            "--destination",
            help="Authority directory to update; defaults to the configured authority root.",
        ),
    ] = None,
    profile_schema: Annotated[
        Path | None,
        typer.Option(
            "--profile-schema",
            help="Profile declaration captured with the candidate; required for custom source sets.",
        ),
    ] = None,
    eager_baseline: Annotated[
        Path | None,
        typer.Option(
            "--eager-baseline",
            help="Write the development benchmark baseline from the same validated artifact.",
        ),
    ] = None,
    if_stale: Annotated[
        bool,
        typer.Option(
            "--if-stale",
            help="Publish only when the existing artifact no longer records the live sources.",
        ),
    ] = False,
) -> None:
    """Validate the registry candidate and atomically republish the runtime authority artifact.

    A refused validation, or a candidate that changes while it is validated,
    leaves the previous artifact byte-for-byte in place.

    ``--if-stale`` asks the currency reader first and returns without
    publishing when the recorded generation still matches a fresh receipt over
    the same trees. That question is a content read with no compilation, so it
    costs seconds against a publication's minutes, and it makes repeated
    invocation cheap enough for a lifecycle step to run unconditionally. The
    recorded identity names the legal sources only, so a compiler change
    reaches the artifact through a publication without ``--if-stale``.
    """
    if profile_schema is None and (registry_root is not None or source_root is not None):
        raise typer.BadParameter(
            "custom authority candidates require an explicit --profile-schema source",
            param_hint="--profile-schema",
        )
    destination_path = destination or authority_publication_destination()
    resolved_registry_root = registry_root or bundled_path("registry", "aeat")
    resolved_source_root = source_root or bundled_path()
    resolved_profile_schema = profile_schema or bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    if if_stale:
        currency = authority_database_currency(
            destination_path / "authority.current.json",
            registry_root=resolved_registry_root,
            source_root=resolved_source_root,
            profile_schema_path=resolved_profile_schema,
        )
        if currency.is_current:
            typer.echo(
                "publish-authority"
                f"	descriptor={currency.descriptor_path}"
                f"	identity_digest={currency.recorded_identity_digest}"
                "	published=skipped-current",
            )
            return
    descriptor = publish_sqlite_authority_candidate(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        destination=destination_path,
        profile_schema_path=resolved_profile_schema,
        eager_baseline_path=eager_baseline,
    )
    typer.echo(
        "publish-authority"
        f"\tdescriptor={destination_path / 'authority.current.json'}"
        f"\tidentity_digest={descriptor.logical_generation}"
        f"\tdatabase={descriptor.database}",
    )
    # Named recipes, not prose: an operator is expected to run these verbatim.
    # Target publication stays explicit and per-target because the guidance for a
    # drifted target is to investigate the record bytes rather than republish, so
    # there is deliberately no publish-every-stale-target verb to point at.
    typer.echo("next\tcurrentness=check-registry\tpublication=registry-publish-target")
