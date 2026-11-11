"""Authority provenance of a persona-table run: publish if stale, prove currency, record the tree.

A table replayed on an authority published from an older registry tree than the
code under test is not evidence. ``run`` therefore publishes into the private
authority root, checks that the published generation records the legal sources
of this exact tree, and writes the tree, generation and database digest beside
the rows so ``render`` can print them.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

AUTHORITY_ROOT_VARIABLE = "CADRUMO_AUTHORITY_ROOT"
DESCRIPTOR_NAME = "authority.current.json"
META_SUFFIX = ".meta.json"
Publisher = Callable[[Path], None]


class ProvenanceError(Exception):
    """The authority cannot be shown to match the tree under test."""


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """What a rows file was produced from."""

    tree: str
    logical_generation: str
    database_sha256: str


def meta_path(rows_file: Path) -> Path:
    """The sidecar recording the provenance of ``rows_file``."""
    return rows_file.with_name(rows_file.name + META_SUFFIX)


def require_authority_root(environment: Mapping[str, str]) -> Path:
    """The private authority root, refusing to fall back to the default authority."""
    value = environment.get(AUTHORITY_ROOT_VARIABLE, "").strip()
    if not value:
        raise ProvenanceError(f"{AUTHORITY_ROOT_VARIABLE} is not set; a table runs only on a private authority")
    return Path(value).resolve()


def _publish_in_process(destination: Path) -> None:
    from dev.registry.pipeline.authority_cli import publish_authority

    publish_authority(
        registry_root=None,
        source_root=None,
        destination=destination,
        profile_schema=None,
        eager_baseline=None,
        if_stale=True,
    )


def publish_if_stale(root: Path, *, publisher: Publisher = _publish_in_process) -> None:
    """Publish the authority of this tree into ``root`` unless it is already current.

    The canonical ``publish-authority --if-stale`` function runs in this process,
    so it publishes the registry of the same code the rows will replay.
    """
    try:
        publisher(root)
    except Exception as failure:
        raise ProvenanceError(f"publish-authority --if-stale failed: {type(failure).__name__}: {failure}") from failure


def _identities(root: Path) -> tuple[str, str | None]:
    """The identity of this tree's legal sources, and the one the descriptor at ``root`` records."""
    from cadrumo.core.resources.bundled_data import bundled_path
    from dev.registry.pipeline.authority_publication import authority_database_currency

    currency = authority_database_currency(
        root / DESCRIPTOR_NAME,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        profile_schema_path=bundled_path("registry", "cadrumo", "user_profile", "schema.toml"),
    )
    return currency.candidate_identity_digest, currency.recorded_identity_digest


def verify_current(root: Path, *, tree: str) -> RunProvenance:
    """Prove the authority at ``root`` records this tree's legal sources, or raise naming both digests."""
    candidate, recorded = _identities(root)
    if recorded != candidate:
        raise ProvenanceError(
            f"authority at {root} is not current for this tree: recorded {recorded}, tree sources {candidate}"
        )
    descriptor = json.loads((root / DESCRIPTOR_NAME).read_text(encoding="utf-8"))
    return RunProvenance(
        tree=tree,
        logical_generation=str(descriptor["logical_generation"]),
        database_sha256=str(descriptor["database_sha256"]),
    )


def prepare_authority(
    environment: Mapping[str, str], *, tree: str, publisher: Publisher = _publish_in_process
) -> RunProvenance:
    """Publish if stale, verify, and return the provenance, or raise before any row runs."""
    root = require_authority_root(environment)
    publish_if_stale(root, publisher=publisher)
    return verify_current(root, tree=tree)


def write_meta(rows_file: Path, provenance: RunProvenance) -> Path:
    """Write the sidecar beside ``rows_file``, replacing the previous run's."""
    path = meta_path(rows_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(provenance), indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def read_meta(path: Path) -> dict[str, str] | None:
    """The recorded provenance at ``path``, or ``None`` when no sidecar exists."""
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in document.items()}
