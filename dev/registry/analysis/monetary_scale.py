"""Screen: whether every monetary export field declares the scale its digits carry.

A fixed-width record has no decimal point. A monetary amount is emitted as
digits, and how many of those digits are cents is a convention held in the
official record design. When the export field declares a decimal count the
convention is recorded and the writer can be checked against it. When it does
not, the magnitude of the emitted amount depends on a rule that exists nowhere
in this registry.

That is not a formatting blemish. A money field read as euros when the design
means cents, or the reverse, is a filing wrong by two orders of magnitude, and
nothing in the project can currently detect it because there is nothing to
compare the writer against.

Two wire types already settle the question and are not reported. The ``money``
wire type carries an implicit scale: the codec multiplies by one hundred when
rendering and parses at two decimal places, so the cents convention is encoded
in the renderer rather than in the declaration. The ``decimal`` wire type
requires a decimal count and refuses without one. Reporting either would be
reporting a rule that already exists.

A third shape settles it structurally. Some designs split one amount across two
positional fields, an integer part and a decimal part, and the registry points
both at the same casilla. The scale is then encoded by the split itself and
neither field declares it, so a per-field reading calls both unscaled when the
pair together is complete. Those are reported as their own kind, not as missing
scale.

What is left unsettled is a monetary casilla rendered by a single field of a
wire type that performs no scaling. Three conditions are reported:

- ``money_without_scale`` - a monetary casilla rendered as an integer, text or
  another unscaled wire type. The renderer emits the value as it stands, so
  whether the digits mean euros or cents is decided nowhere in this registry.
- ``money_unexpected_scale`` - a monetary field rendered as a decimal with a
  count other than the two the cents convention uses. Four decimals on a unit
  security value may well be right, but it is an exception and nothing records
  it as one.
- ``money_split_representation`` - one monetary casilla carried by several
  fields of one record, which is the official integer-part and decimal-part
  split. Reported so the shape is visible and countable, not because it is
  wrong.
- ``sibling_scale_disagrees`` - a monetary field emitting a different magnitude
  from the amounts of the same width beside it in the same record. Official
  designs declare runs of amount fields distinguished only by meaning, so a
  field scaling differently from its run has no reason in the design and one of
  them is wrong. This is the only condition here that no per-field rule can
  reach, because every field involved is individually valid; it is found by
  comparing declarations against each other rather than against a rule, and it
  is what surfaced the corpus's one known filing-correctness defect.

Scale is read from the resolved surface, so binding-derived fields are included.
Row-mapped endpoints are excluded: they carry no field of their own and so
declare no scale to check.

The screen exits 0 whatever it finds. It reports; it does not gate. A gate
belongs here once every monetary field carries a scale.
"""

from __future__ import annotations

import collections
import sys
from dataclasses import dataclass

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
from cadrumo.domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "CENTS_SCALE",
    "MonetaryScaleFinding",
    "scale_findings",
    "screen_authority",
]

#: The decimal count the cents convention uses, and the only one the corpus
#: treats as ordinary. Any other count is reported as an exception rather than
#: silently accepted, and this constant is not a permitted-values list: it is
#: the single ordinary case against which exceptions are named.
CENTS_SCALE = 2

_MONETARY = "money"

#: Wire types that settle scale on their own: ``money`` scales by the cents
#: factor inside the codec, and ``decimal`` refuses without a declared count.
#: A monetary casilla rendered by either is not under-declared.
_SELF_SCALING_WIRE_TYPES = frozenset({"money", "decimal"})


@dataclass(frozen=True, slots=True)
class MonetaryScaleFinding:
    """One export field whose declared scale does not account for its casilla."""

    modelo: str
    revision: str
    casilla_id: CasillaId
    field_id: str
    kind: str
    detail: str


def scale_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[MonetaryScaleFinding, ...]:
    """Report every monetary field of ``revision`` whose scale is missing or unusual."""
    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}
    endpoints = resolved_export_endpoints(revision)
    per_record: collections.Counter[tuple[str, CasillaId]] = collections.Counter(
        (endpoint.record_id, endpoint.casilla_id) for endpoint in endpoints if endpoint.field is not None
    )
    findings: list[MonetaryScaleFinding] = []
    for endpoint in endpoints:
        field = endpoint.field
        if field is None:
            continue
        casilla_type = declared.get(endpoint.casilla_id)
        if casilla_type is None:
            continue
        if casilla_type != _MONETARY:
            continue
        decimals = getattr(field, "decimals", None)
        wire = str(field.data_type)
        carried_by = per_record[(endpoint.record_id, endpoint.casilla_id)]
        if wire in _SELF_SCALING_WIRE_TYPES:
            if wire == "decimal" and decimals != CENTS_SCALE:
                kind = "money_unexpected_scale"
                detail = f"rendered as decimal with {decimals} decimals, not the usual {CENTS_SCALE}"
            else:
                continue
        elif carried_by > 1:
            kind = "money_split_representation"
            detail = f"carried by {carried_by} fields of record {endpoint.record_id}, which is the part split"
        else:
            kind = "money_without_scale"
            detail = f"rendered as {wire}, which applies no scale, and declares no decimals"
        findings.append(
            MonetaryScaleFinding(
                modelo=modelo_id,
                revision=str(revision.id),
                casilla_id=endpoint.casilla_id,
                field_id=str(field.id),
                kind=kind,
                detail=detail,
            )
        )
    return tuple(findings)


def scale_outcome(wire_type: str, decimals: int | None) -> str:
    """Return what the emitted digits mean, not how the field is spelled.

    Two fields can be written differently and mean the same thing: the money
    wire type scales inside the codec and a decimal declaring two places scales
    in the declaration, and both emit cents. Comparing spellings would report
    that pair as a disagreement; comparing outcomes does not, which is the
    distinction that separates a cosmetic inconsistency from a wrong magnitude.
    """
    if wire_type == "money":
        return "cents"
    if wire_type == "decimal":
        return "cents" if decimals == CENTS_SCALE else f"scale_{decimals}"
    return "unscaled"


def sibling_findings(revision: ModeloRevision, *, modelo_id: str) -> tuple[MonetaryScaleFinding, ...]:
    """Report monetary fields of one record and width whose siblings scale differently.

    The official designs declare runs of amount fields that are the same kind of
    field at the same width, distinguished only by what they mean. When one of
    them scales differently from the others, the design gives no reason for it
    and one of them is wrong. This comparison is between declarations rather
    than against a rule, which is why no per-field gate can make it.
    """
    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}
    groups: dict[tuple[str, int], list[tuple[str, str, CasillaId]]] = collections.defaultdict(list)
    for endpoint in resolved_export_endpoints(revision):
        field = endpoint.field
        if field is None or declared.get(endpoint.casilla_id) != _MONETARY:
            continue
        if field.length is None:
            # A field with no declared width cannot be compared against siblings
            # by width; it is reported by the per-field checks instead.
            continue
        outcome = scale_outcome(str(field.data_type), getattr(field, "decimals", None))
        groups[(endpoint.record_id, field.length)].append((outcome, str(field.id), endpoint.casilla_id))

    findings: list[MonetaryScaleFinding] = []
    for (record_id, length), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        outcomes = {outcome for outcome, _, _ in members}
        if len(outcomes) < 2:
            continue
        majority = collections.Counter(outcome for outcome, _, _ in members).most_common(1)[0][0]
        for outcome, field_id, casilla_id in members:
            if outcome == majority:
                continue
            findings.append(
                MonetaryScaleFinding(
                    modelo=modelo_id,
                    revision=str(revision.id),
                    casilla_id=casilla_id,
                    field_id=field_id,
                    kind="sibling_scale_disagrees",
                    detail=(
                        f"emits {outcome} where {len(members) - 1} sibling amounts of width {length} "
                        f"in record {record_id} emit {majority}"
                    ),
                )
            )
    return tuple(findings)


def screen_authority(
    authority: ValidatedRegistryAuthority, modelo_ids: tuple[str, ...]
) -> tuple[MonetaryScaleFinding, ...]:
    """Screen every revision of the named modelos through the validated authority."""
    findings: list[MonetaryScaleFinding] = []
    for modelo_id in modelo_ids:
        definition = authority.modelo(modelo_id)
        for revision in definition.revisions.values():
            findings.extend(scale_findings(revision, modelo_id=modelo_id))
            findings.extend(sibling_findings(revision, modelo_id=modelo_id))
    return tuple(findings)


def _bundled_modelo_ids() -> tuple[str, ...]:
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    return tuple(sorted(str(code) for code in registry_modelo_codes()))


def main() -> int:
    """Print one greppable row per finding and a closing census; always exit 0."""
    authority = bundled_authority()
    findings = screen_authority(authority, _bundled_modelo_ids())
    by_kind: collections.Counter[str] = collections.Counter(finding.kind for finding in findings)
    by_modelo: collections.Counter[str] = collections.Counter(
        finding.modelo for finding in findings if finding.kind == "money_without_scale"
    )
    for finding in findings:
        sys.stdout.write(
            f"monetary_scale modelo={finding.modelo} revision={finding.revision} "
            f"casilla={finding.casilla_id} field={finding.field_id} kind={finding.kind} detail={finding.detail!r}\n"
        )
    kinds = " ".join(f"{kind}={count}" for kind, count in sorted(by_kind.items()))
    unscaled = " ".join(f"{modelo}={count}" for modelo, count in sorted(by_modelo.items()))
    sys.stdout.write(f"summary findings={len(findings)} {kinds} unscaled_by_modelo=[{unscaled}]\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
