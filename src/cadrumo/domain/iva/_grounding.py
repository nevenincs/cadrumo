"""Runtime IVA citation checks against published authority evidence.

The tables under ``registry/aeat/iva/`` carry regulatory values -- rates, recargo
tiers, place-of-supply placements, territorial exclusions -- and each row names
the provision that establishes it. That citation is the only thing standing
between a value and a wrong filing, and until a table's loader resolves it the
citation is validated by nothing: an identifier naming a provision nobody defined
parses exactly like one naming a provision the BOE actually carries.

The published artifact projects the anchor-scoped legal text that publication
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

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from .errors import IvaCatalogueError

if TYPE_CHECKING:
    # Type-only: importing these at runtime would close the cycle the local
    # imports below exist to avoid. The registry's binding modules consume the
    # public IVA facade, and these loaders are part of that facade.
    from ..calculations.registry.authority import PinnedAuthorityOperation


def verify_table_legal_refs(
    table: str,
    citations: Sequence[tuple[str, Sequence[str]]],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Verify every citation a registry table's rows carry, or refuse the table.

    Each cited provision must be catalogued in the caller's pinned authority and
    its declared ``required_text`` and ``forbidden_text`` must hold in the anchor
    text the authority publishes for it. No corpus path is opened: the evidence
    is the publisher-validated text the artifact carries.

    Args:
        table: The table's name, used to head the refusal.
        citations: One ``(row_label, reference_ids)`` pair per row, in the order
            the rows were parsed.
        operation: The pinned authority operation supplying legal references and evidence.

    Raises:
        IvaCatalogueError: When any cited provision is absent from the legal
            catalogue, has no published evidence, or its published anchor text breaks
            one of its declared clauses. The message enumerates every failure
            rather than the first.
    """
    checked: set[str] = set()
    failures: list[str] = []
    for row, reference_ids in citations:
        failures.extend(_citation_failures(row, reference_ids, checked, operation=operation))
    if failures:
        raise IvaCatalogueError(
            f"{table}: legal grounding verification failed:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def _citation_failures(
    row: str,
    reference_ids: Iterable[str],
    checked: set[str],
    *,
    operation: PinnedAuthorityOperation,
) -> list[str]:
    """Return one message per citation of ``row`` that fails, memoising the ids that pass."""
    from ...core.corpus_text import normalise_corpus_text
    from ..calculations.registry.authority_artifact import AuthorityComponentCodecError

    failures: list[str] = []
    for ref_id in reference_ids:
        if ref_id in checked:
            continue
        try:
            reference = operation.legal_reference(ref_id)
        except Exception:
            reference = None
        if reference is None:
            failures.append(f"{row}: unknown legal_ref {ref_id!r}")
            continue
        try:
            anchored_text = operation.legal_evidence(ref_id).anchored_text
        except AuthorityComponentCodecError as exc:
            failures.append(f"{row}: legal_ref {ref_id!r} has no published evidence: {exc}")
            continue
        broken = [
            f"missing required text {required!r}"
            for required in reference.required_text
            if normalise_corpus_text(required) not in anchored_text
        ] + [
            f"contains forbidden text {forbidden!r}"
            for forbidden in reference.forbidden_text
            if normalise_corpus_text(forbidden) in anchored_text
        ]
        if broken:
            failures.append(f"{row}: invalid legal_ref {ref_id!r}: published evidence " + "; ".join(broken))
            continue
        checked.add(ref_id)
    return failures
