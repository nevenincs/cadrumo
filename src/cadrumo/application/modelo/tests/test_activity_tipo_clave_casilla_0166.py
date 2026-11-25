"""Casilla 0166 states the censal tipo de actividad of a direct-estimation filer.

The box (TACT) is required in every estimacion directa block of the Modelo 100
XML. These tests read it through the real published registry and profile schema,
in every supported filing year the envelope admits: a declared tipo fills it, an
undeclared one leaves it empty with an advisory naming the profile facts to
declare, and a filer outside direct estimation has no such box at all.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_profile_schema,
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ..profile_export_binding import (
    profile_text_casilla_gap_diagnostics,
    profile_text_fact_index,
    resolve_profile_export_values,
    resolve_profile_text_casilla_inputs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "10000000-0000-4000-8000-000000000166"
_CLOCK = datetime.now(tz=UTC)
_PERIOD = "0A"
_TACT: CasillaId = validated_casilla_id("0166", surface="_TACT")
_TACT_FIELD = "TACT"
_DIRECT_FILER = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
)


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=facts,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=leased_profile_create_context(),
    )


def _activity(row: int, description: str, tipo: str | None) -> tuple[UserProfileFact, ...]:
    facts = [UserProfileFact(path=f"activities.{row}.description", value=description)]
    if tipo is not None:
        facts.append(UserProfileFact(path=f"activities.{row}.tipo_actividad", value=tipo))
    return tuple(facts)


def _supported_revisions() -> tuple[tuple[int, ModeloRevision], ...]:
    support = published_supported_filing_years()
    assert support is not None
    revisions: list[tuple[int, ModeloRevision]] = []
    for year in sorted(support.years):
        try:
            revisions.append((year, published_snapshot("100", filing_year=year, period=_PERIOD).revision))
        except FilingYearOutsideSupportEnvelopeError:
            continue
    assert revisions
    return tuple(revisions)


def _gap_remedies(
    revision: ModeloRevision, record: UserProfileRecord, *, operation: PinnedAuthorityOperation
) -> list[str | None]:
    schema = published_profile_schema()
    diagnostics = profile_text_casilla_gap_diagnostics(
        revision,
        profile_text_fact_index(record, schema, operation=operation),
        supplied_casilla_ids=frozenset(),
        derived_selectors=schema.derived_selectors,
    )
    return [diagnostic.remedy for diagnostic in diagnostics if diagnostic.casilla_id == _TACT]


@pytest.mark.parametrize("tipo", ["A03", "A05"])
def test_a_declared_tipo_de_actividad_fills_casilla_0166_and_its_tact_field_in_every_supported_year(
    authority_operation: PinnedAuthorityOperation, tipo: str
) -> None:
    record = _record(*_DIRECT_FILER, *_activity(0, "Instalaciones de fontaneria", tipo))
    schema = published_profile_schema()
    for year, revision in _supported_revisions():
        resolved = resolve_profile_text_casilla_inputs(
            revision, profile_text_fact_index(record, schema, operation=authority_operation)
        )
        exported = resolve_profile_export_values(
            revision.bindings,
            bucket_id=_PROFILE_ID,
            filing_year=year,
            operation=authority_operation,
            profile_record=record,
            schema=schema,
        )

        assert resolved.values[_TACT] == tipo, year
        assert exported[_TACT_FIELD] == tipo, year
        assert _TACT not in {gap.casilla_id for gap in resolved.gaps}, year


@pytest.mark.parametrize(
    "activities",
    [
        (),
        _activity(0, "Instalaciones de fontaneria", None),
        (*_activity(0, "Instalaciones de fontaneria", "A03"), *_activity(1, "Traduccion", None)),
        (*_activity(0, "Instalaciones de fontaneria", "A03"), *_activity(1, "Traduccion", "A05")),
    ],
)
def test_an_undeclared_or_divided_tipo_leaves_casilla_0166_empty_and_names_the_facts_to_declare(
    authority_operation: PinnedAuthorityOperation, activities: tuple[UserProfileFact, ...]
) -> None:
    record = _record(*_DIRECT_FILER, *activities)
    schema = published_profile_schema()
    for year, revision in _supported_revisions():
        resolved = resolve_profile_text_casilla_inputs(
            revision, profile_text_fact_index(record, schema, operation=authority_operation)
        )

        assert _TACT not in resolved.values, year
        (remedy,) = _gap_remedies(revision, record, operation=authority_operation)
        assert remedy is not None, year
        assert "activities.tipo_actividad" in remedy, year
        assert "irpf.estimation_directa_actividad_tipo_clave" not in remedy, year


@pytest.mark.parametrize("regime", ["objetiva", None])
def test_a_filer_outside_direct_estimation_has_no_casilla_0166_to_answer(
    authority_operation: PinnedAuthorityOperation, regime: str | None
) -> None:
    facts = [
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
        *_activity(0, "Comercio al por menor", "A03"),
    ]
    if regime is not None:
        facts.append(UserProfileFact(path="irpf.estimation_regime", value=regime))
    record = _record(*facts)
    schema = published_profile_schema()
    for year, revision in _supported_revisions():
        resolved = resolve_profile_text_casilla_inputs(
            revision, profile_text_fact_index(record, schema, operation=authority_operation)
        )

        assert _TACT not in resolved.values, year
        assert _gap_remedies(revision, record, operation=authority_operation) == [], year
