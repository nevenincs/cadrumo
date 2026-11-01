"""Registry-build refusals for a binding's declared grade cap.

The schema already refuses an unknown grade or reason, a grade other than
``calculation`` and an empty ``legal_refs`` list when the row loads. The rules
here need the rest of the revision, the legal catalogue or the governed facts,
so they run at build:

* a cap on a binding whose revision reaches no further than ``calculation``.
  The cap narrows a revision's reach; a revision already at or below the cap's
  rung has nothing for it to narrow, so the cap would claim a demotion that
  does not happen;
* a cap on a binding whose provider kind is not routed to an executable
  resolver. A deferred or non-runtime kind produces no value for the cap to
  narrow, so the cap would read as a grounded limit on a value that never
  exists;
* a legal reference that does not resolve to a legal-authority catalogue entry.
  The references state the provisions that leave the value short of filing
  grade, and the note shown to the filer names them;
* a capped binding that reaches no casilla, through a ``BOUND`` casilla or a
  declared output redirect. A cap on a value no box receives withholds nothing;
* a reviewed alternate whose cap differs from its primary's. Alternates are one
  value contract, so a box would block or not depending on which one resolved.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.binding_grade_cap_reach import capped_binding_reach
from cadrumo.domain.calculations.registry.binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_references import LegalReference

from ._validate_helpers import missing_refs

_GRADES_A_CAP_CANNOT_NARROW: frozenset[RegistryAuthorityGrade] = frozenset(
    {RegistryAuthorityGrade.APPLICABILITY, RegistryAuthorityGrade.CALCULATION}
)


def validate_binding_grade_cap_section(
    *,
    prefix: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
) -> list[str]:
    """Return every grade-cap refusal for one modelo revision; empty when no binding is capped."""
    capped = [binding for binding in revision.bindings if binding.grade_cap is not None]
    if not capped:
        return []
    failures: list[str] = []
    revision_grade = revision.effective_authority_grade
    for binding in capped:
        cap = binding.grade_cap
        if cap is None:
            continue
        owner = f"binding {binding.id} grade_cap"
        if revision_grade in _GRADES_A_CAP_CANNOT_NARROW:
            failures.append(
                f"{prefix}: {owner} caps the value at {cap.grade.value!r}, but the revision already reaches "
                f"only {revision_grade.value!r}; a cap must narrow the revision's reach",
            )
        registration = BINDING_PROVIDER_REGISTRATIONS.get(binding.source)
        if registration is not None and registration.disposition != "filing_grade":
            failures.append(
                f"{prefix}: {owner} is declared on provider kind {binding.source.value!r}, whose disposition "
                f"{registration.disposition!r} routes no executable resolver, so no value exists for the cap "
                "to narrow",
            )
        failures.extend(missing_refs(prefix, owner, cap.legal_refs, legal_refs, "legal"))
    failures.extend(_unreached_cap_failures(prefix=prefix, revision=revision))
    failures.extend(_alternate_cap_failures(prefix=prefix, revision=revision))
    return failures


def _unreached_cap_failures(*, prefix: str, revision: ModeloRevision) -> list[str]:
    return [
        f"{prefix}: binding {binding_id} grade_cap reaches no casilla: no BOUND casilla names the binding and "
        "no declared output redirect writes it, so the cap withholds nothing"
        for binding_id, reach in capped_binding_reach(revision, authority=None).items()
        if not reach.casilla_ids
    ]


def _alternate_cap_failures(*, prefix: str, revision: ModeloRevision) -> list[str]:
    by_id = revision_bindings_by_id(revision)
    failures: list[str] = []
    for casilla in revision.casillas:
        if casilla.input_kind is not InputKind.BOUND or casilla.binding is None:
            continue
        primary = by_id.get(casilla.binding)
        if primary is None:
            continue
        for alternate_id in casilla.alternate_bindings:
            alternate = by_id.get(alternate_id)
            if alternate is None or alternate.grade_cap == primary.grade_cap:
                continue
            failures.append(
                f"{prefix}: casilla {casilla.id!r} alternate binding {alternate_id!r} declares grade cap "
                f"{alternate.grade_cap!r}, which differs from primary binding {primary.id!r} cap "
                f"{primary.grade_cap!r}; reviewed equivalents share one value contract",
            )
    return failures


__all__ = ["validate_binding_grade_cap_section"]
