"""Runtime IVA citation checks against signed authority evidence.

The tables under ``registry/aeat/iva/`` carry regulatory values -- rates, recargo
tiers, place-of-supply placements, territorial exclusions -- and each row names
the provision that establishes it. That citation is the only thing standing
between a value and a wrong filing, and until a table's loader resolves it the
citation is validated by nothing: an identifier naming a provision nobody defined
parses exactly like one naming a provision the BOE actually carries.

The signed artifact projects the anchor-scoped legal text that publication
validated.  Runtime consumes that projection only: authoring corpus readers and
their repair or fallback paths stay in development tooling.

WHY VERIFICATION HAPPENS AT LOAD RATHER THAN IN A TEST. A table whose grounding
is asserted only by a test ships its rows to every caller that imports it and
fails afterwards, in a lane nobody is looking at. Refusing at the loader means an
ungrounded regulatory value cannot be read at all, which is the same posture the
registry takes for binding validation: invariants are enforced when the data is
built, and resolve-time helpers are backstops rather than the gate.

WHY CITATIONS ARE COLLECTED BY THE CALLER. The tables do not agree on a field
name -- the rate and recargo tables write ``legal_refs`` while the
place-of-supply table writes ``legal_references`` alongside an
``establishing_reference`` -- so a sweep here that discovered citations by
searching for one field name would silently examine none of the other table and
pass. Each loader hands over the citations it has already parsed into its own
typed rows, so a table cannot be covered by accident and cannot be skipped by
one.

See Also:
    :meth:`~domain.calculations.registry.authority.ValidatedRegistryAuthority.legal_quotation_is_grounded`
        The artifact authority query every runtime quotation uses.
    :class:`~domain.iva.IvaRateRecord`
        The rate row whose ``legal_refs`` were the first to be routed this way.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

from .errors import IvaCatalogueError

if TYPE_CHECKING:
    # Type-only: importing these at runtime would close the cycle the local
    # imports below exist to avoid. The registry's binding modules consume the
    # public IVA facade, and these loaders are part of that facade.
    from ..calculations.registry.schema_references import LegalReference, SourceReference


def registry_catalogues() -> tuple[Mapping[str, LegalReference], Mapping[str, SourceReference]]:
    """Return catalogue facts from the one signed runtime authority.

    Source trees are compiler input, never a product-time verification source.
    """
    from ..calculations.registry.authority import bundled_authority

    authority = bundled_authority()
    return authority.catalogues.legal, authority.catalogues.sources


def legal_ref_failures(
    row: str,
    reference_ids: Iterable[str],
    legal: Mapping[str, LegalReference],
    verified: set[str],
) -> list[str]:
    """Resolve signed legal evidence for one runtime row, memoising passed ids.

    Accumulating rather than raising, so one load reports every ungrounded row
    it found instead of the first. A caller that raises on the first failure
    turns a table with four broken citations into four successive debugging
    rounds.

    Args:
        row: A label identifying the row, quoted verbatim into each failure.
        reference_ids: The provision identifiers the row cites.
        legal: The legal catalogue the identifiers must resolve in.
        verified: Ids already verified in this load, extended in place. Shared
            across rows because evidence resolution is deterministic per signed
            authority artifact.

    Returns:
        One message per failure, empty when every citation verified.
    """
    from ..calculations.registry.authority import bundled_authority

    authority = bundled_authority()
    failures: list[str] = []
    for ref_id in reference_ids:
        if ref_id in verified:
            continue
        reference = legal.get(ref_id)
        if reference is None:
            failures.append(f"{row}: unknown legal_ref {ref_id!r}")
            continue
        try:
            authority.legal_evidence_text(ref_id)
        except Exception as exc:
            failures.append(f"{row}: invalid legal_ref {ref_id!r}: {exc}")
            continue
        verified.add(ref_id)
    return failures


def verify_table_legal_refs(table: str, citations: Sequence[tuple[str, Sequence[str]]]) -> None:
    """Verify every citation a registry table's rows carry, or refuse the table.

    Args:
        table: The table's name, used to head the refusal.
        citations: One ``(row_label, reference_ids)`` pair per row, in the order
            the rows were parsed.

    Raises:
        IvaCatalogueError: When any cited provision is absent from the legal
            catalogue, or is present but does not resolve to bundled legal text
            carrying its declared ``required_text`` at its declared anchor. The
            message enumerates every failure rather than the first.
    """
    legal, _sources = registry_catalogues()
    verified: set[str] = set()
    failures: list[str] = []
    for row, reference_ids in citations:
        failures.extend(legal_ref_failures(row, reference_ids, legal, verified))
    if failures:
        raise IvaCatalogueError(
            f"{table}: legal grounding verification failed:\n" + "\n".join(f" - {failure}" for failure in failures),
        )
