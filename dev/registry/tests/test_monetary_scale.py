"""Real-behaviour tests for the monetary scale screen.

The detector cases mutate a copy of a real revision through the typed model the
loader produces, so the screen walks the same objects it walks in production.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from cadrumo.domain.calculations.registry.export import resolved_export_endpoints
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition

from ..analysis.monetary_scale import _SELF_SCALING_WIRE_TYPES, CENTS_SCALE, scale_findings, screen_authority

#: The amount width modelo 353 declares for every importe of its declaration
#: record, and the width both cents spellings appear at side by side.
_WIDTH_17 = 17

#: Floor for the monetary endpoints the absence claim below is measured over.
#: Live m303's 2025 revision resolves 150 of 174 endpoints to a monetary
#: casilla; two thirds of that, so ordinary revision movement never fires it.
_MINIMUM_MONETARY_ENDPOINTS = 100

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def test_a_self_scaling_wire_type_is_not_reported_as_unscaled(authority: ValidatedRegistryAuthority) -> None:
    """A self-scaling wire type settles the scale question itself, so it is not reported.

    Reporting one would be reporting a rule that already exists, and would have
    inflated this screen's finding count roughly twentyfold.

    The claim is an ABSENCE, so it needs the population it is absent from. This
    revision yields zero findings of ANY kind, and a screen that had stopped
    reading it would yield zero too -- the assertion below cannot tell those
    apart on its own. So the monetary endpoints are counted first: live m303's
    2025 revision carries 150 of them, every one on the ``decimal`` wire.

    Named for the self-scaling family rather than for ``money``. The test read
    ``a_money_wire_type`` while the revision it loads carries no ``money`` wire
    at all; both types are self-scaling so the assertion passed either way, and
    the name described a case it never exercised.
    """
    revision = authority.modelo("303").revisions["2025"]
    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}
    monetary = [
        endpoint
        for endpoint in resolved_export_endpoints(revision)
        if endpoint.field is not None and declared.get(endpoint.casilla_id) == "money"
    ]
    assert len(monetary) >= _MINIMUM_MONETARY_ENDPOINTS, (
        f"only {len(monetary)} monetary endpoint(s) resolved for m303 2025; below this the screen "
        "examined almost nothing and the absence below says nothing about scaling"
    )
    unscaled_wires = {str(endpoint.field.data_type) for endpoint in monetary} - _SELF_SCALING_WIRE_TYPES
    assert not unscaled_wires, f"this revision no longer exercises a self-scaling wire: {sorted(unscaled_wires)}"

    findings = scale_findings(revision, modelo_id="303")
    assert not [item for item in findings if item.kind == "money_without_scale"]


def test_money_rendered_by_an_unscaled_wire_type_is_reported(authority: ValidatedRegistryAuthority) -> None:
    """A monetary casilla rendered as an integer or text has no scale anywhere."""
    revision = authority.modelo("184").revisions["2025-y-siguientes"]
    findings = [item for item in scale_findings(revision, modelo_id="184") if item.kind == "money_without_scale"]
    assert findings
    assert all("applies no scale" in item.detail for item in findings)


def test_the_unusual_decimal_count_is_reported_as_an_exception(authority: ValidatedRegistryAuthority) -> None:
    """A money field rendered at four decimals is surfaced, not accepted silently."""
    revision = authority.modelo("189").revisions["2025"]
    kinds = {item.kind for item in scale_findings(revision, modelo_id="189")}
    assert "money_unexpected_scale" in kinds


def test_the_unscaled_fields_are_concentrated_and_bounded(authority: ValidatedRegistryAuthority) -> None:
    """The condition is a bounded work item, not a corpus-wide property.

    This pins the shape of the finding rather than its count: if it ever spreads
    beyond a handful of modelos the remedy stops being per-field review.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    unscaled = [item for item in screen_authority(authority, modelo_ids) if item.kind == "money_without_scale"]
    assert unscaled
    assert len({item.modelo for item in unscaled}) <= 6


def test_the_official_part_split_is_not_reported_as_missing_scale(
    authority: ValidatedRegistryAuthority,
) -> None:
    """One casilla carried by an integer part and a decimal part is scaled by construction.

    The official design for several informativas splits an amount across two
    positional fields. Neither field declares a decimal count because the split
    is the encoding, so a per-field reading calls both unscaled when the pair is
    complete. This pins the distinction that separates the real defect from the
    shape, and it is why the reported defect count is 24 rather than 156.
    """
    revision = authority.modelo("347").revisions["2025-y-siguientes"]
    findings = scale_findings(revision, modelo_id="347")
    split = [item for item in findings if item.kind == "money_split_representation"]
    assert split, "modelo 347 carries the official part split"
    assert all("part split" in item.detail for item in split)
    assert not {item.casilla_id for item in split} & {
        item.casilla_id for item in findings if item.kind == "money_without_scale"
    }


def test_a_self_scaling_wire_type_wins_over_the_split_shape(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A money-typed field carried by several fields is already scaled by the codec.

    Checking the split before the wire type reported 156 split fields including
    ones the codec already scales; precedence has to put self-scaling first.
    """
    revision = authority.modelo("390").revisions["2025"]
    findings = scale_findings(revision, modelo_id="390")
    assert not [item for item in findings if item.kind == "money_split_representation"]


def test_sibling_amounts_of_one_record_are_compared_by_outcome_not_spelling(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Money and decimal-with-two-places both emit cents and must not read as a disagreement.

    The modelo 353 record carries both spellings side by side. A comparison on
    the declared wire type rather than on the emitted magnitude would report
    every one of them as disagreeing with its neighbours.

    The claim is an ABSENCE, so the population it is absent from is measured
    first: this record must actually carry both spellings, or the silence below
    would prove nothing about how they are compared.
    """
    from ..analysis.monetary_scale import scale_outcome, sibling_findings

    assert scale_outcome("money", None) == scale_outcome("decimal", 2) == "cents"
    assert scale_outcome("integer", None) == "unscaled"

    revision = authority.modelo("353").revisions["2026-desde-02"]
    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}
    spellings = {
        str(endpoint.field.data_type)
        for endpoint in resolved_export_endpoints(revision)
        if endpoint.field is not None
        and endpoint.field.length == _WIDTH_17
        and declared.get(endpoint.casilla_id) == "money"
    }
    assert spellings == {"money", "decimal"}, (
        f"this record no longer carries both cents spellings side by side: {sorted(spellings)}"
    )
    assert sibling_findings(revision, modelo_id="353") == ()


def test_a_record_whose_amounts_all_scale_alike_reports_nothing(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Consistent sibling amounts are the normal case and yield no finding."""
    from ..analysis.monetary_scale import sibling_findings

    revision = authority.modelo("303").revisions["2025"]
    assert sibling_findings(revision, modelo_id="303") == ()


def test_the_corpus_reports_no_sibling_scale_disagreement(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Nothing in the live corpus emits a magnitude its own run contradicts.

    This condition used to have live members and was proven by naming them.
    Modelo 200's casilla 03594 left the set when its DP200020B slot's note was
    read and found to state the wire form outright. Modelo 353's casilla 10 left
    it when its slot's note was read and found to state APPLICABILITY and no
    wire form, which sent the field to the reviewed render profile that already
    governed its twenty-eight structurally identical siblings.

    With the population empty the screen is gateable at zero, so this asserts
    zero. It carries no detector evidence of its own by design: the proof that
    the comparison still fires lives in the constructed case below, which is
    what keeps this assertion from passing because the screen stopped looking.
    """
    from cadrumo.application.modelo.registry_discovery import registry_modelo_codes

    from ..analysis.monetary_scale import screen_authority as scale_screen

    modelo_ids = tuple(sorted(str(code) for code in registry_modelo_codes()))
    disagreements = [item for item in scale_screen(authority, modelo_ids) if item.kind == "sibling_scale_disagrees"]
    reported = sorted((item.modelo, item.revision, str(item.casilla_id)) for item in disagreements)
    assert reported == [], f"a sibling-scale disagreement is reported: {reported}"


def test_the_sibling_comparison_fires_on_a_constructed_unscaled_field(
    authority: ValidatedRegistryAuthority,
) -> None:
    """One amount of a correct run, re-declared unscaled, is reported.

    The live corpus no longer carries this defect, so the detector's proof is
    constructed - and a detector with no proof is the failure this module exists
    to avoid. The defect is injected into a copy of a real revision through the
    typed model the loader produces, so the screen walks the objects it walks in
    production and the injection cannot drift from the real surface.

    The unmutated revision is asserted clean first. Without that, a comparison
    that had stopped reading this record would fail the same way as one that
    over-fires, and this test would say which only by accident.
    """
    from ..analysis.monetary_scale import sibling_findings

    revision = authority.modelo("353").revisions["2026-desde-02"]
    assert sibling_findings(revision, modelo_id="353") == (), "the constructed defect must be the only one"

    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}

    def is_cents_amount(field: ExportFieldDefinition) -> bool:
        return bool(
            field.casilla_id is not None
            and declared.get(field.casilla_id) == "money"
            and field.length == _WIDTH_17
            and str(field.data_type) == "decimal"
            and field.decimals == CENTS_SCALE,
        )

    layout = revision.export_layouts[0]
    record = next(item for item in layout.records if any(is_cents_amount(field) for field in item.fields))
    victim = next(field for field in record.fields if is_cents_amount(field))
    unscaled = victim.model_copy(update={"data_type": "integer", "decimals": None})
    mutated = revision.model_copy(
        update={
            "export_layouts": (
                layout.model_copy(
                    update={
                        "records": tuple(
                            item.model_copy(
                                update={
                                    "fields": tuple(
                                        unscaled if field.id == victim.id else field for field in item.fields
                                    ),
                                },
                            )
                            if item.id == record.id
                            else item
                            for item in layout.records
                        ),
                    },
                ),
                *revision.export_layouts[1:],
            ),
        },
    )

    findings = sibling_findings(mutated, modelo_id="353")
    assert [item.field_id for item in findings] == [str(victim.id)]
    assert findings[0].kind == "sibling_scale_disagrees"
    assert "unscaled" in findings[0].detail
    assert "cents" in findings[0].detail


def _cents_amount_predicate(revision):
    """Return a predicate matching a width-17 field that emits cents via a money casilla."""
    declared = {casilla.id: str(casilla.data_type) for casilla in revision.casillas}

    def is_cents_amount(field: ExportFieldDefinition) -> bool:
        return bool(
            field.casilla_id is not None
            and declared.get(field.casilla_id) == "money"
            and field.length == _WIDTH_17
            and str(field.data_type) == "decimal"
            and field.decimals == CENTS_SCALE,
        )

    return is_cents_amount


def _amount_run(revision):
    """Return the layout, record and one cents amount of a real width-17 run."""
    is_cents_amount = _cents_amount_predicate(revision)
    layout = revision.export_layouts[0]
    record = next(item for item in layout.records if any(is_cents_amount(field) for field in item.fields))
    return layout, record, next(field for field in record.fields if is_cents_amount(field))


def _revision_with(revision, layout, record, victim, replacement):
    """Return a copy of ``revision`` with exactly ``victim`` replaced."""
    return revision.model_copy(
        update={
            "export_layouts": (
                layout.model_copy(
                    update={
                        "records": tuple(
                            item.model_copy(
                                update={
                                    "fields": tuple(
                                        replacement if field.id == victim.id else field for field in item.fields
                                    ),
                                },
                            )
                            if item.id == record.id
                            else item
                            for item in layout.records
                        ),
                    },
                ),
                *revision.export_layouts[1:],
            ),
        },
    )


def _unhomed(record, victim):
    """Return ``victim`` re-homed to a producer key, carrying no casilla.

    The producer key is borrowed from a header field of the same record rather
    than invented, so the copy keeps a shape this record really publishes.
    """
    donor = next(field for field in record.fields if str(getattr(field.kind, "value", field.kind)) == "header")
    return victim.model_copy(
        update={"casilla_id": None, "kind": "header", "producer_key": donor.producer_key},
    )


def test_an_unscaled_amount_carrying_no_casilla_is_reported(
    authority: ValidatedRegistryAuthority,
) -> None:
    """A width-matched amount is compared whether or not it reaches a casilla.

    This is the gap the screen actually had. An endpoint exists only where a
    field names a casilla, so a filing-grade amount homed to a producer key
    instead - which is how the official designs carry several rectificativa
    importes - yielded no endpoint and was never compared with anything. Modelo
    200's DP200014B carried two such fields unscaled beside twenty-three scaled
    siblings while this screen reported that modelo clean.

    The defect is constructed rather than taken from the corpus, because the
    corpus no longer holds one: the victim is stripped of its casilla AND
    re-declared unscaled, so it reproduces both halves of the real condition at
    once. Stripping the casilla alone must not silence the run either, which is
    what the intermediate assertion pins - without it this test could pass
    because the field went invisible rather than because it was caught.
    """
    from ..analysis.monetary_scale import sibling_findings

    revision = authority.modelo("353").revisions["2026-desde-02"]
    assert sibling_findings(revision, modelo_id="353") == (), "the constructed defect must be the only one"

    layout, record, victim = _amount_run(revision)
    unhomed = _unhomed(record, victim)

    assert sibling_findings(_revision_with(revision, layout, record, victim, unhomed), modelo_id="353") == ()

    unscaled = unhomed.model_copy(update={"data_type": "integer", "decimals": None})
    findings = sibling_findings(_revision_with(revision, layout, record, victim, unscaled), modelo_id="353")

    assert [item.field_id for item in findings] == [str(victim.id)]
    assert findings[0].kind == "sibling_scale_disagrees"
    assert findings[0].casilla_id is None, "the field carries no casilla; the finding must not invent one"
    assert "unscaled" in findings[0].detail
    assert "cents" in findings[0].detail


def test_a_casilla_less_non_amount_is_not_admitted_to_an_amount_run(
    authority: ValidatedRegistryAuthority,
) -> None:
    """Widening the walk must not start reporting counts, codes, years or enumerations.

    A casilla-less field joins a proven amount run only on its shape. A closed
    value domain, a value policy or a date format each state that the slot is
    NOT an amount, and each must keep it out of the comparison even though its
    width matches the run beside it. Asserted against the same field so the only
    thing separating the admitted case from the refused ones is the statement
    under test.
    """
    from ..analysis.monetary_scale import amount_shaped_without_casilla, sibling_findings

    revision = authority.modelo("353").revisions["2026-desde-02"]
    _layout, record, victim = _amount_run(revision)
    admitted = _unhomed(record, victim).model_copy(update={"data_type": "integer", "decimals": None})

    assert amount_shaped_without_casilla(admitted), "the unscaled casilla-less amount is the case that IS reported"
    assert not amount_shaped_without_casilla(admitted.model_copy(update={"allowed_values": ("0", "1")}))
    assert not amount_shaped_without_casilla(admitted.model_copy(update={"date_format": "aaaammdd"}))
    assert not amount_shaped_without_casilla(admitted.model_copy(update={"kind": "literal"}))
    assert not amount_shaped_without_casilla(admitted.model_copy(update={"kind": "filler"}))
    assert not amount_shaped_without_casilla(admitted.model_copy(update={"data_type": "text"}))

    assert sibling_findings(revision, modelo_id="353") == ()
