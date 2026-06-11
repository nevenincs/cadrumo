"""Golden-query retrieval verification over the hardened index.

The build-time sweep trusts the index to return the right preprocessed
surface for the vocabulary it queries. This module is the trust-gate: a fixed
set of golden queries, each pinned to the surface kind it MUST hit above an
agreed score floor, run through the resident service. If a golden query stops
landing on its preprocessed surface (a sidecar regressed, the index went
stale, the dedup exclusion misfired), the verification fails and the sweep
must not be trusted.

Surfaces a query may be pinned to:

* ``normatives_sidecar`` - a BOE article ``*.extracted.md`` / ``.json``
  sidecar (the legal-grounding surface);
* ``diseno_sidecar`` - a Diseno-de-registro workbook / instruction sidecar
  (the casilla-number-to-field-position surface);
* ``any_sidecar`` - any extraction sidecar (used where several preprocessed
  surfaces are legitimate);
* ``terminology`` - a Handbook concept fragment.

The score floor follows the project RAG conventions: ~0.5 is the
strong-signal threshold (the audit-cadence rule's signal floor). Each query
declares the floor it must clear; a Spanish query against the Spanish corpus
clears a high floor, while a deliberately cross-lingual probe declares a
lower, realistic floor (declared aliases - not raw embedding - are what carry
cross-lingual matching, per the accepted decision).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Default service port (single-writer store; all search routes here).
RAG_SERVICE_PORT = 8766

#: The strong-signal score floor the RAG conventions name (~0.5).
STRONG_SIGNAL_FLOOR = 0.5


class GoldenSurface(StrEnum):
    """The preprocessed surface kind a golden query must hit."""

    NORMATIVES_SIDECAR = "normatives_sidecar"
    DISENO_SIDECAR = "diseno_sidecar"
    ANY_SIDECAR = "any_sidecar"
    TERMINOLOGY = "terminology"


@dataclass(frozen=True)
class GoldenQuery:
    """One golden query pinned to a surface it must hit above a floor."""

    query: str
    surface: GoldenSurface
    floor: float
    note: str


@dataclass(frozen=True)
class QueryHit:
    """A single retrieval result (path + score) projected from the service."""

    path: str
    score: float


@dataclass(frozen=True)
class GoldenResult:
    """The outcome of evaluating one :class:`GoldenQuery`."""

    query: GoldenQuery
    passed: bool
    best_matching_path: str | None
    best_matching_score: float
    top_hits: tuple[QueryHit, ...]


#: The fixed golden-query set. Each pins the surface it must reach and the
#: floor it must clear. Spanish-against-Spanish queries clear the strong floor;
#: the cross-lingual probe declares a realistic lower floor.
GOLDEN_QUERIES: tuple[GoldenQuery, ...] = (
    GoldenQuery(
        query="regla de prorrata operaciones deduccion",
        surface=GoldenSurface.NORMATIVES_SIDECAR,
        floor=STRONG_SIGNAL_FLOOR,
        note="prorrata concept reaches the IVA-law article sidecar",
    ),
    GoldenQuery(
        query="prorrateo porcentaje deducible",
        surface=GoldenSurface.ANY_SIDECAR,
        floor=STRONG_SIGNAL_FLOOR,
        note="prorrata synonym reaches a preprocessed grounding surface",
    ),
    GoldenQuery(
        query="posicion longitud tipo descripcion campo registro",
        surface=GoldenSurface.DISENO_SIDECAR,
        floor=STRONG_SIGNAL_FLOOR,
        note="casilla field-position table reaches a Diseno sidecar",
    ),
    GoldenQuery(
        query="disposicion transitoria tipo de gravamen",
        surface=GoldenSurface.NORMATIVES_SIDECAR,
        floor=STRONG_SIGNAL_FLOOR,
        note="transitional-provision rate reaches a normatives sidecar",
    ),
    GoldenQuery(
        query="esquema registro fichero modelo presentacion",
        surface=GoldenSurface.DISENO_SIDECAR,
        floor=STRONG_SIGNAL_FLOOR,
        note="fichero schema reaches a Diseno/instruction sidecar",
    ),
    # Four-language probe: the same concept across es/ca; the es term clears
    # the strong floor and the ca term (declared in the Handbook) reaches the
    # terminology concept. Cross-lingual embedding alone is weak, so the ca
    # probe targets the Handbook concept where its alias is declared.
    GoldenQuery(
        query="prorrata especial sectores diferenciados",
        surface=GoldenSurface.TERMINOLOGY,
        floor=0.4,
        note="es: prorrata especial reaches the Handbook concept",
    ),
    GoldenQuery(
        query="modalitat de prorrata IVA sector activitat",
        surface=GoldenSurface.TERMINOLOGY,
        floor=0.4,
        note="ca: Catalan prorrata phrasing reaches the Handbook concept",
    ),
)


def _classify(path: str) -> set[GoldenSurface]:
    """Return the surface kinds a result path belongs to."""
    kinds: set[GoldenSurface] = set()
    if ".extracted." in path:
        kinds.add(GoldenSurface.ANY_SIDECAR)
        if "/corpus/normatives/" in path:
            kinds.add(GoldenSurface.NORMATIVES_SIDECAR)
        if "/disenos_registro/" in path or "/instructions/" in path:
            kinds.add(GoldenSurface.DISENO_SIDECAR)
    if "/_data/terminology/" in path:
        kinds.add(GoldenSurface.TERMINOLOGY)
    return kinds


def run_query(
    query: str,
    *,
    repo_root: Path,
    port: int = RAG_SERVICE_PORT,
    max_results: int = 12,
    timeout_s: float = 45.0,
) -> tuple[QueryHit, ...]:
    """Run one search through the resident service and project its hits.

    Args:
        query: The search query string.
        repo_root: Repository root the command runs from.
        port: Service port to delegate to.
        max_results: How many ranked hits to request.
        timeout_s: Per-query HTTP timeout passed to the CLI.

    Returns:
        The ranked hits as ``(path, score)`` tuples.

    Raises:
        RuntimeError: If the service errors or the response is unparseable.
    """
    cmd = [
        "uv",
        "run",
        "--no-sync",
        "vaultspec-rag",
        "search",
        query,
        "--type",
        "code",
        "--port",
        str(port),
        "--max-results",
        str(max_results),
        "--timeout",
        str(int(timeout_s)),
        "--json",
    ]
    result = subprocess.run(  # noqa: S603
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=timeout_s + 30.0,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"unparseable search response for {query!r}: {result.stdout[:200]}") from exc
    if not payload.get("ok"):
        raise RuntimeError(f"search failed for {query!r}: {payload.get('error')} {payload.get('message', '')}")
    hits: list[QueryHit] = []
    for row in payload.get("data", {}).get("results", []):
        path = str(row.get("path", ""))
        score = float(row.get("score", 0.0))
        if path:
            hits.append(QueryHit(path=path, score=score))
    return tuple(hits)


def evaluate_query(golden: GoldenQuery, hits: tuple[QueryHit, ...]) -> GoldenResult:
    """Evaluate one golden query against its retrieved hits.

    A query passes when at least one hit on its pinned surface clears the
    declared floor.
    """
    best_path: str | None = None
    best_score = 0.0
    for hit in hits:
        on_surface = golden.surface in _classify(hit.path)
        if on_surface and hit.score >= golden.floor and hit.score > best_score:
            best_path = hit.path
            best_score = hit.score
    return GoldenResult(
        query=golden,
        passed=best_path is not None,
        best_matching_path=best_path,
        best_matching_score=best_score,
        top_hits=hits[:5],
    )


def raw_normatives_html_hits(hits: tuple[QueryHit, ...]) -> tuple[QueryHit, ...]:
    """Return hits that are RAW normatives HTML (not the extracted sidecar).

    Used by the dedup proof: after the ``.vaultragignore`` exclusion lands and
    the index is rebuilt, a normatives query must return zero raw-HTML hits -
    only the clean ``*.extracted.md`` sidecars survive.
    """
    return tuple(
        hit
        for hit in hits
        if "/corpus/normatives/html/" in hit.path and hit.path.endswith(".html") and ".extracted." not in hit.path
    )
