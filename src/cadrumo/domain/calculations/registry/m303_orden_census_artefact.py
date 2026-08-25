"""Canonical build-generated annual-Orden census artefact.

Extracting one pinned annual Orden is a full BeautifulSoup parse of its BOE
HTML, and the five supported ejercicios cost about 1.6 seconds of every warm
authority load. Nothing about that parse varies per process: the sources are
digest-pinned and the extractor is versioned, so the result is a pure function of
bytes the release already carries. This module is where that result is written
once by the build and read back by every runtime: the build is the gate and the
runtime asserts identity.

**What is shipped is the CENSUS, not a digest.** The committed manifest carries
only per-source invariants (counts, a module distribution, a few scalars); the
compiled projections are built FROM the full census, so a runtime handed only a
digest would have nothing to compile. That distinction is the whole reason this
artefact exists rather than a checksum.

**What the runtime checks, and what it deliberately does not.** A shipped census
is honoured only when its ``source_content_digest`` equals the pinned source's
own ``sha256`` -- which the registry already holds in its ``sources`` catalogue,
so the check costs no file read -- and its ``extractor_version`` equals the
running extractor's. Neither opens the HTML. Any mismatch, absence, or foreign
shape falls back to extracting in full, so the artefact can only ever be a
shortcut to the same censuses, never a second source of them.

This module owns the artefact's filename, its location, its envelope schema, and
both directions of its serialisation. Nothing else may spell any of those: a
second spelling is how a build writes a name the runtime never reads, and the
failure is silent because the runtime simply falls back and stays slow.

See Also:
    :mod:`~domain.calculations.registry._m303_orden_manifest`
        The committed invariants manifest this artefact sits beside, and the
        staleness refusal both share.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema import RegistryModel
from cadrumo.domain.calculations.registry.schema_references import SourceReference

from ....core.external_constants import UTF_8_ENCODING
from ._m303_orden_constants import EXTRACTOR_VERSION
from .ids import SourceRefId
from .m303_orden_raw_models import M303AnnualOrdenSourceCensus

M303_ORDEN_CENSUS_ARTEFACT_FILENAME = "censuses.json"
"""The sole filename of the generated census artefact. Never spelled elsewhere."""

M303_ORDEN_CENSUS_SCHEMA_VERSION = "m303-annual-orden-censuses-v1"
"""Bumped when the envelope shape changes; a foreign version falls back to extraction."""

_LOGGER = logging.getLogger(__name__)


class M303AnnualOrdenCensusArtefact(RegistryModel):
    """Every pinned annual Orden's census, as the build extracted them.

    ``extractor_version`` is carried on the envelope AND on each census. That is
    not redundancy for its own sake: the envelope's copy lets a stale artefact be
    rejected in one comparison without validating the whole payload, while the
    per-census copy is what the existing census model already guarantees and what
    the equality check below is measured against.
    """

    schema_version: str
    extractor_version: str
    censuses: tuple[M303AnnualOrdenSourceCensus, ...]


def m303_orden_census_artefact_path(root: Path) -> Path:
    """Return the census artefact's location under ``root``.

    Sits inside the generated ``m303_orden_anual`` directory beside the manifest,
    unlike the registry identity stamp, which must sit outside the tree it
    describes. The difference is deliberate: this artefact describes the BOE
    corpus rather than the registry tree, so being fingerprinted along with the
    rest of the tree is correct -- it is exactly what makes an edit to it
    invalidate the compiled cache.

    Returns:
        The ``censuses.json`` path inside the generated annual-Orden directory.
    """
    return root.resolve() / "m303_orden_anual" / M303_ORDEN_CENSUS_ARTEFACT_FILENAME


def render_m303_annual_orden_censuses(censuses: tuple[M303AnnualOrdenSourceCensus, ...]) -> str:
    """Render the census artefact's committed bytes.

    Indented and newline-terminated so a regeneration produces a reviewable diff
    rather than one enormous line -- these are regulatory extractions, and a
    reviewer has to be able to see what moved.

    Returns:
        The artefact text, exactly as the build commits it.
    """
    artefact = M303AnnualOrdenCensusArtefact(
        schema_version=M303_ORDEN_CENSUS_SCHEMA_VERSION,
        extractor_version=EXTRACTOR_VERSION,
        censuses=censuses,
    )
    return artefact.model_dump_json(indent=2) + "\n"


def load_m303_annual_orden_censuses(
    root: Path,
    *,
    sources: dict[SourceRefId, SourceReference] | None = None,
) -> dict[SourceRefId, M303AnnualOrdenSourceCensus] | None:
    """Load the shipped censuses for ``root``, or ``None`` to extract instead.

    ``None`` for an absent, unreadable, foreign, schema-mismatched or
    extractor-mismatched artefact, and for one whose censuses do not agree with
    the pinned sources -- every one of which means "extract in full", never
    "serve a degraded census". Strict-parsed, so an artefact carrying an
    unexpected field is refused rather than partially honoured.

    When ``sources`` is supplied, each census is additionally required to name a
    known source whose ``sha256`` equals the census's ``source_content_digest``.
    That is the check which makes the artefact safe without reading the HTML: the
    digest was computed by the build over the same bytes the registry pins, so
    agreement means the extraction describes the corpus this release carries.
    Passing no ``sources`` skips only that cross-check, never the shape and
    version gates.

    Returns:
        The censuses keyed by source ref, or ``None`` to fall back to extraction.
    """
    path = m303_orden_census_artefact_path(root)
    if not path.is_file():
        return None
    try:
        artefact = M303AnnualOrdenCensusArtefact.model_validate_json(path.read_text(encoding=UTF_8_ENCODING))
    except (OSError, ValidationError):
        _LOGGER.debug("Ignoring unreadable or foreign annual Orden census artefact at %s; extracting", path)
        return None
    if artefact.schema_version != M303_ORDEN_CENSUS_SCHEMA_VERSION:
        return None
    if artefact.extractor_version != EXTRACTOR_VERSION:
        return None
    censuses = {census.source_ref: census for census in artefact.censuses}
    if len(censuses) != len(artefact.censuses):
        return None
    if sources is not None and not _censuses_match_pinned_sources(censuses, sources):
        return None
    return censuses


def _censuses_match_pinned_sources(
    censuses: dict[SourceRefId, M303AnnualOrdenSourceCensus],
    sources: dict[SourceRefId, SourceReference],
) -> bool:
    """Whether every shipped census describes the source the registry pins."""
    for source_ref, census in censuses.items():
        source = sources.get(source_ref)
        if source is None:
            _LOGGER.debug("Annual Orden census artefact names unknown source %r; extracting", source_ref)
            return False
        if census.source_content_digest != source.sha256:
            _LOGGER.debug("Annual Orden census for %r does not match its pinned source digest; extracting", source_ref)
            return False
        if census.extractor_version != EXTRACTOR_VERSION:
            return False
    return True


__all__ = [
    "M303_ORDEN_CENSUS_ARTEFACT_FILENAME",
    "M303_ORDEN_CENSUS_SCHEMA_VERSION",
    "M303AnnualOrdenCensusArtefact",
    "load_m303_annual_orden_censuses",
    "m303_orden_census_artefact_path",
    "render_m303_annual_orden_censuses",
]
