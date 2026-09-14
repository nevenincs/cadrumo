"""Minimal facts-only publication CLI.

The generated-export CLI imports the full Modelo compiler and its rendering
graph.  Facts publication deliberately has a smaller dependency boundary: it
must be able to start without importing modules whose import-time descriptors
resolve the already-published authority.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority_artifact_path

from ..compiler.fact_providers import AUTHORED_FACT_PROVIDER_ID
from .authority_publication import publish_facts_authority_candidate

app = typer.Typer(
    name="pipeline",
    help="Publish the authored governed-facts catalogue into the typed authority artifact.",
    no_args_is_help=True,
)


@app.callback()
def _facts_cli_callback() -> None:
    """Keep the facts-only entry point in explicit subcommand mode."""


@app.command("publish-facts-authority")
def publish_facts_authority(
    registry_root: Annotated[
        Path | None,
        typer.Option("--registry-root", help="Facts registry tree; defaults to the bundled registry."),
    ] = None,
    artifact: Annotated[
        Path | None,
        typer.Option("--artifact", help="Artifact to replace; defaults to the bundled runtime authority artifact."),
    ] = None,
) -> None:
    """Compile authored facts and merge them into the current typed authority artifact."""
    artifact_path = artifact or bundled_authority_artifact_path()
    published = publish_facts_authority_candidate(
        registry_root=registry_root or bundled_path("registry", "aeat"),
        artifact_path=artifact_path,
    )
    provider_counts = Counter(
        str(fact.provider_id) for fact in published.catalogues.facts.facts.values() if fact.provider_id is not None
    )
    authored_count = provider_counts.get(AUTHORED_FACT_PROVIDER_ID, 0)
    provider_owned_count = sum(
        count for provider_id, count in provider_counts.items() if provider_id != AUTHORED_FACT_PROVIDER_ID
    )
    typer.echo(
        "publish-facts-authority"
        f"\tartifact={artifact_path}"
        f"\tidentity_digest={published.identity_digest}"
        f"\tfacts={len(published.catalogues.facts.facts)}"
        f"\tauthored={authored_count}"
        f"\tprovider_owned={provider_owned_count}"
        f"\tretained_provider_owned={provider_owned_count}",
    )


if __name__ == "__main__":
    app()
