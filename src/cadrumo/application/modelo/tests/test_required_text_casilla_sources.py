"""Required text casillas take their value from the profile or the filing context.

A required text casilla the calculation itself supplies has exactly two
canonical sources beyond the operator: the declarant's profile, through a
text-channel profile binding, and the declaration's filing context, through
the semantic roles the calculation projects from the work unit. These tests run
the real resolvers over the published registry with hand-built synthetic
profiles, so a registry edit that drops a binding or a role is felt here.

The last block is the gate: every required, calculation-supplied text casilla
of every calculable revision either has one of those sources or is listed below
with the reason it has none. A new gap, and an exemption that no longer applies,
both fail.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period, PeriodError
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_value_contract import BindingValueChannel
from ....domain.calculations.registry.errors import RegistryError
from ....domain.calculations.registry.profile_bindings import ProfileProvider
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_profile_schema,
    published_snapshot,
)
from ....domain.modelos.errors import ModeloError
from ....domain.modelos.filing_record import FilingDeclarationKind
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileFactValue
from ...filing.runtime import collection_from_snapshot
from ..binding_resolution import resolve_declaration_period_inputs
from ..calculation_resolution import resolve_calculation_inputs
from ..profile_export_binding import (
    profile_text_casilla_gap_diagnostics,
    resolve_profile_export_values,
    resolve_profile_text_casilla_inputs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "7e3c1a52-8f0d-4b6e-9a21-3c5d7e9f1b24"
_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_DECLARANTE_NIF: CasillaId = validated_casilla_id("DPNIF_D", surface="_DECLARANTE_NIF")
_DECLARANTE_NAME: CasillaId = validated_casilla_id("DP_APENOM_D", surface="_DECLARANTE_NAME")
_SPOUSE_NIF: CasillaId = validated_casilla_id("DPNIF_C", surface="_SPOUSE_NIF")
_TIPO_TRIBUTACION: CasillaId = validated_casilla_id("TIPOTRIBUTACION", surface="_TIPO_TRIBUTACION")
_DECLARANTE = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.surnames", value="GARCIA LOPEZ"),
    UserProfileFact(path="identity.name", value="MARIA"),
)


def _record(*facts: UserProfileFact):
    return _create_profile_record_for_test(
        profile_id=_BUCKET,
        setup_state=ProfileSetupState.COMPLETE,
        facts=facts,
        created_at=_T0,
        updated_at=_T0,
        context=_profile_creation_context_for_test(),
    )


def _fact_index(*facts: UserProfileFact) -> dict[str, UserProfileFactValue]:
    from ...user_profile.projections import profile_fact_index

    return profile_fact_index(_record(*facts), published_profile_schema())


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_the_declarant_identity_casillas_are_filled_from_the_profile(filing_year: int) -> None:
    """The real Modelo 100 identity casillas read the profile, not a placeholder."""
    revision = published_snapshot("100", filing_year=filing_year, period="0A").revision

    resolved = resolve_profile_text_casilla_inputs(revision, _fact_index(*_DECLARANTE))

    assert resolved.values[_DECLARANTE_NIF] == "12345678Z"
    assert resolved.values[_DECLARANTE_NAME] == "GARCIA LOPEZ MARIA"
    assert not {_DECLARANTE_NIF, _DECLARANTE_NAME} & {gap.casilla_id for gap in resolved.gaps}


def test_the_calculation_holds_what_the_filed_record_addresses(*, operation: PinnedAuthorityOperation) -> None:
    """Each identity casilla equals the export dictionary field its binding addresses.

    Both halves read one binding through one resolution, so the calculation and
    the XML declaration cannot state two names for the same declarant.
    """
    snapshot = published_snapshot("100", filing_year=2024, period="0A")
    revision = snapshot.revision
    record = _record(*_DECLARANTE)
    casilla_values = resolve_profile_text_casilla_inputs(
        revision,
        _fact_index(*_DECLARANTE),
    ).values
    bindings = {binding.id: binding for binding in revision.bindings}
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    exported = resolve_profile_export_values(
        tuple(bindings.values()),
        bucket_id=_BUCKET,
        operation=operation,
        profile_record=record,
        schema=published_profile_schema(),
    )

    for casilla_id in (_DECLARANTE_NIF, _DECLARANTE_NAME):
        binding_id = casillas[casilla_id].binding
        assert binding_id is not None
        provider = bindings[binding_id].provider
        assert isinstance(provider, ProfileProvider)
        assert provider.dictionary_field is not None
        assert exported[provider.dictionary_field] == casilla_values[casilla_id]


def test_a_gated_spouse_slot_is_neither_filled_nor_reported_for_an_individual_filing() -> None:
    """The spouse NIF exists only on a joint declaration; an individual one has no such slot."""
    revision = published_snapshot("100", filing_year=2024, period="0A").revision

    resolved = resolve_profile_text_casilla_inputs(
        revision,
        _fact_index(
            *_DECLARANTE,
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_spouse.tax_id", value="87654321X"),
        ),
    )

    assert _SPOUSE_NIF not in resolved.values
    assert _SPOUSE_NIF not in {gap.casilla_id for gap in resolved.gaps}


@pytest.mark.parametrize("filing_year", [2024, 2025])
def test_a_declaration_type_stored_as_a_number_still_fills_its_text_casilla(filing_year: int) -> None:
    """The individual declaration type ``"1"`` is restored as a number yet still fills TIPOTRIBUTACION."""
    revision = published_snapshot("100", filing_year=filing_year, period="0A").revision
    declaration_type = UserProfileFact(path="renta_filing.declaration_type", value="1")
    # The premise the resolver must survive: the record hands the text back as a Decimal.
    assert isinstance(declaration_type.value, Decimal)

    resolved = resolve_profile_text_casilla_inputs(revision, _fact_index(*_DECLARANTE, declaration_type))

    assert resolved.values[_TIPO_TRIBUTACION] == "1"
    assert _TIPO_TRIBUTACION not in {gap.casilla_id for gap in resolved.gaps}


def test_an_absent_profile_name_stays_absent_and_names_the_fields_to_declare() -> None:
    revision = published_snapshot("100", filing_year=2024, period="0A").revision

    resolved = resolve_profile_text_casilla_inputs(
        revision,
        _fact_index(UserProfileFact(path="identity.tax_id", value="12345678Z")),
    )

    assert _DECLARANTE_NAME not in resolved.values
    gaps = {gap.casilla_id: gap for gap in resolved.gaps}
    assert gaps[_DECLARANTE_NAME].profile_fields == ("identity.surnames", "identity.name")


def test_the_gap_reaches_the_operator_as_an_advisory_naming_the_profile_fields() -> None:
    revision = published_snapshot("100", filing_year=2024, period="0A").revision
    facts = _fact_index(UserProfileFact(path="identity.tax_id", value="12345678Z"))

    diagnostics = profile_text_casilla_gap_diagnostics(revision, facts, supplied_casilla_ids=frozenset())

    (advisory,) = (diagnostic for diagnostic in diagnostics if diagnostic.casilla_id == _DECLARANTE_NAME)
    assert (advisory.reason, advisory.source_kind) == ("unresolved_binding", "profile")
    assert advisory.remedy is not None
    for field in ("identity.surnames", "identity.name"):
        assert field in str(advisory.message)
        assert field in advisory.remedy
    assert advisory.legal_refs
    supplied = profile_text_casilla_gap_diagnostics(revision, facts, supplied_casilla_ids={_DECLARANTE_NAME})
    assert _DECLARANTE_NAME not in {diagnostic.casilla_id for diagnostic in supplied}


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    [("347", 2025, "0A"), ("720", 2025, "0A"), ("184", 2025, "0A"), ("390", 2025, "0A")],
)
@pytest.mark.parametrize("kind", list(FilingDeclarationKind))
def test_the_declaration_kind_fills_the_tipo_declaracion_casilla(
    modelo: str,
    filing_year: int,
    period: str,
    kind: FilingDeclarationKind,
) -> None:
    """The declaration's kind in its chain comes from the filing context, not from the operator."""
    revision = published_snapshot(modelo, filing_year=filing_year, period=period).revision
    (casilla,) = (casilla for casilla in revision.casillas if casilla.semantic_role == "tipo_declaracion")

    resolved = resolve_declaration_period_inputs(
        revision,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, period),
        declaration_kind=kind,
    )

    assert resolved.text_casilla_inputs[casilla.id] == kind.value


@pytest.mark.parametrize(
    ("modelo", "period", "grade"),
    [
        ("222", "1P", RegistryAuthorityGrade.CALCULATION),
        ("122", "0A", RegistryAuthorityGrade.APPLICABILITY),
        ("576", "0A", RegistryAuthorityGrade.APPLICABILITY),
    ],
)
def test_a_result_clave_is_not_given_a_declaration_kind(
    modelo: str, period: str, grade: RegistryAuthorityGrade
) -> None:
    """A design's "Tipo de declaracion" that holds the result clave (I, U, G, N) is a different fact."""
    revision = published_snapshot(modelo, filing_year=2025, period=period, grade=grade).revision
    casilla_id = validated_casilla_id("decl.tipo-declaracion", surface="test")
    (casilla,) = (casilla for casilla in revision.casillas if casilla.id == casilla_id)

    resolved = resolve_declaration_period_inputs(
        revision,
        filing_year=2025,
        period=Period.from_year_and_code(2025, period),
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )

    assert casilla.semantic_role == "tipo_declaracion_resultado"
    assert casilla_id not in resolved.text_casilla_inputs


def test_the_modelo_341_period_casilla_takes_the_filing_period() -> None:
    """Modelo 341's "Periodo" (1T to 4T) is the solicitud's quarter, filled from the filing context.

    Both record designs print it as the period (@22+2, and campo 11 "Devengo -
    Periodo" @107+2); the "D" clave is a separate literal campo. No declaration
    kind may land on it.
    """
    revision = published_snapshot(
        "341", filing_year=2025, period="2T", grade=RegistryAuthorityGrade.APPLICABILITY
    ).revision
    casilla_id = validated_casilla_id("decl.periodo", surface="test")

    resolved = resolve_declaration_period_inputs(
        revision,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "2T"),
        declaration_kind=FilingDeclarationKind.COMPLEMENTARIA,
    )

    assert resolved.text_casilla_inputs == {casilla_id: "2T"}


# ---------------------------------------------------------------------------
# Gate: every required, calculation-supplied text casilla has a source.
# ---------------------------------------------------------------------------

#: Required text casillas the calculation has no canonical source for yet, each
#: with the reason. Keyed narrowly by (modelo, casilla); an entry that stops
#: applying fails the gate as surely as a new gap does.
_CLASSIFIED_UNSUPPLIED: Mapping[tuple[str, str], str] = {
    (
        "100",
        "DPFNAC_D",
    ): "profile birth date travels on the date channel; its text spelling is the owning registry's call",
    ("100", "ZCCAD"): "profile CCAA travels on the enum channel; its text spelling is the owning registry's call",
    ("184", "decl.tipo-soporte"): "aeat-dr-184 fixes 'T' at @58; a design constant, not a calculation input",
    ("184", "decl.numero-justificante"): "the declaration's identifying number is assigned at presentation",
    ("222", "decl.tipo-declaracion"): "result clave I/U/G/N is the filing's result disposition, elected at filing",
    ("232", "decl.cnae"): "the CNAE lives on the repeatable profile activities section with no principal-activity rule",
    ("308", "decl.tipo-solicitud"): "the refund case is the operator's choice, declared informational",
    ("309", "decl.tipo-trigger"): "the non-periodic trigger is the operator's choice, declared informational",
    ("360", "decl.estado-miembro"): "the refund member state is the operator's choice, declared informational",
}
#: Revisions whose calculation refuses before any text casilla is assembled.
_CLASSIFIED_ASSEMBLY_REFUSALS: Mapping[str, str] = {
    "189": "filing_year role declared on the non-informational casilla ejercicio-declaracion",
}
_NUMERIC_CHANNELS = frozenset({BindingValueChannel.DECIMAL, BindingValueChannel.INTEGER})


def _every_profile_fact(snapshot: RegistrySnapshot) -> dict[str, UserProfileFactValue]:
    """A synthetic profile that answers every profile fact the revision reads."""
    facts: dict[str, UserProfileFactValue] = {}
    for binding in snapshot.revision.bindings:
        provider = binding.provider
        if not isinstance(provider, ProfileProvider):
            continue
        facts.update(dict.fromkeys(profile_binding_selectors(provider), "X"))
        if provider.required_when_profile_key is not None and provider.required_when_value is not None:
            facts[provider.required_when_profile_key] = provider.required_when_value
    return facts


def _unsupplied_required_text_casillas(snapshot: RegistrySnapshot) -> frozenset[CasillaId]:
    """Required text casillas the calculation supplies but no canonical source answers.

    Runs the calculation's own assembly: the filing-context projection, every
    numeric binding resolved, and the profile projection over a profile that
    declares every fact the revision reads.
    """
    revision = snapshot.revision
    supplied = resolve_calculation_inputs(
        revision=revision,
        filing_year=snapshot.filing_year,
        period=Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        backend_casilla_inputs=None,
        resolved_bindings={
            binding.id: Decimal("1") for binding in revision.bindings if binding.value.channel in _NUMERIC_CHANNELS
        },
        casilla_inputs={},
        profile_text_casilla_inputs=resolve_profile_text_casilla_inputs(revision, _every_profile_fact(snapshot)).values,
    ).text_casilla_inputs
    return frozenset(
        schema.casilla_id
        for schema in collection_from_snapshot(snapshot).casillas
        if schema.required
        and schema.value_type == "str"
        and not schema.operator_supplied
        and schema.casilla_id not in supplied
    )


def _calculable_snapshots(operation: PinnedAuthorityOperation) -> list[RegistrySnapshot]:
    """Every (modelo, supported year, period) the calculation rung admits.

    A revision below the calculation rung, or a period token no work unit can
    carry, is refused by the same selection the calculate action uses, and is
    not a calculation this gate can speak for.
    """
    snapshots: list[RegistrySnapshot] = []
    for modelo in operation.modelo_ids():
        directory = operation.modelo_directory(modelo)
        for filing_year in operation.supported_filing_years().years:
            periods = {
                period for meta in directory.revisions for period in meta.period_selector.periods_for_year(filing_year)
            }
            for period in sorted(periods):
                try:
                    Period.from_year_and_code(filing_year, period)
                    snapshots.append(
                        operation.snapshot(
                            modelo,
                            filing_year=filing_year,
                            period=period,
                            grade=RegistryAuthorityGrade.CALCULATION,
                        ),
                    )
                except (PeriodError, RegistryError):
                    continue
    return snapshots


def test_every_required_calculation_supplied_text_casilla_has_a_source(*, operation: PinnedAuthorityOperation) -> None:
    gaps: set[tuple[str, str]] = set()
    refusals: set[str] = set()
    for snapshot in _calculable_snapshots(operation):
        try:
            unsupplied = _unsupplied_required_text_casillas(snapshot)
        except ModeloError:
            refusals.add(str(snapshot.modelo.id))
            continue
        gaps.update((str(snapshot.modelo.id), str(casilla_id)) for casilla_id in unsupplied)

    assert sorted(gaps - set(_CLASSIFIED_UNSUPPLIED)) == [], "unclassified required text casillas with no source"
    assert sorted(set(_CLASSIFIED_UNSUPPLIED) - gaps) == [], "classified gaps that now have a source"
    assert refusals == set(_CLASSIFIED_ASSEMBLY_REFUSALS)


def test_an_identity_casilla_left_unbound_is_caught() -> None:
    """Detector teeth: the gate reports a declarant NIF that no binding answers any more."""
    snapshot = published_snapshot("100", filing_year=2024, period="0A")
    unbound = tuple(
        casilla.model_copy(update={"input_kind": InputKind.INFORMATIONAL, "binding": None})
        if casilla.id == _DECLARANTE_NIF
        else casilla
        for casilla in snapshot.revision.casillas
    )
    defective = snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"casillas": unbound})})

    assert _DECLARANTE_NIF not in _unsupplied_required_text_casillas(snapshot)
    assert _DECLARANTE_NIF in _unsupplied_required_text_casillas(defective)
