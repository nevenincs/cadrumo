"""A carry from earlier years that nobody stated is refused in words, each family by its own door.

A carry the registry lets the filer state as holding nothing is unknown, never
zero, while no earlier return supplies it. Each statement family has its
refusal words in every output language. The negative general bases are stated
for the declaration as a whole; a let property's pending interest and repairs
(LIRPF art. 23.1.a.1.º) are stated on that property's own row, so their
refusal names the per-property command and never the declaration-wide one.

Real behaviour: the published Modelo 100 revision of every year of the support
envelope and the real refusal builder; the engine refusal is the one it raises
for a binding without a value.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...aggregation.renta_inmueble_findings import RentaInmuebleDoor
from ..printed_boxes import snapshot_printed_boxes
from ..work_missing_input import (
    ModeloPriorCarryAbsenceUnstatedError,
    ModeloWorkMissingInputError,
    prior_carry_absence_unstated,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "prior-carry-words"
_AT = datetime.fromtimestamp(0, tz=UTC)


def _work_unit(snapshot: RegistrySnapshot, year: int) -> WorkUnit:
    period = Period.from_year_and_code(year, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID, modelo="100", filing_year=year, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=year,
        period=period,
        revision_id=snapshot.revision.id,
        name="prior-carry-words",
        created_at=_AT,
        updated_at=_AT,
    )


def _refusal(year: int, family: AbsenceAttestationFamily) -> ModeloPriorCarryAbsenceUnstatedError:
    operation = governed_facts_in_scope()
    assert isinstance(operation, PinnedAuthorityOperation)
    snapshot = published_snapshot("100", filing_year=year, period="0A")
    binding_id = next(binding.id for binding in snapshot.revision.bindings if binding.absence_attestation is family)
    missing = ModeloWorkMissingInputError.from_registry_error(
        RegistryValidationError(
            f"binding {binding_id!r} has no supplied value",
            translated_message="errors.calc.binding_value_missing",
            context={"binding_id": binding_id},
        )
    )
    assert missing is not None
    refusal = prior_carry_absence_unstated(
        missing,
        work_unit=_work_unit(snapshot, year),
        snapshot=snapshot,
        boxes=snapshot_printed_boxes(operation, snapshot),
        unresolved_binding_ids=(),
    )
    assert refusal is not None
    return refusal


def _words(refusal: ModeloPriorCarryAbsenceUnstatedError, language: OutputLanguage) -> str:
    key = refusal.translated_message
    assert key is not None
    return lookup_translation(key, locale=language.value) or ""


def _families_in(year: int) -> tuple[AbsenceAttestationFamily, ...]:
    revision = published_snapshot("100", filing_year=year, period="0A").revision
    declared = {binding.absence_attestation for binding in revision.bindings}
    return tuple(family for family in AbsenceAttestationFamily if family in declared)


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_every_family_s_refusal_reads_in_every_language(year: int) -> None:
    families = _families_in(year)
    assert AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES in families
    for family in families:
        refusal = _refusal(year, family)
        assert refusal.family is family
        authored = {language: _words(refusal, language) for language in OutputLanguage}
        assert all(words for words in authored.values()), (family, authored)
        assert len(set(authored.values())) == len(authored), (family, authored)


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_a_property_s_pending_carry_is_refused_with_its_row_door_not_the_declaration_wide_one(year: int) -> None:
    refusal = _refusal(year, AbsenceAttestationFamily.RENTA_CAPITAL_INMOBILIARIO_GASTOS_PENDIENTES)
    context = refusal.context or {}

    assert context["command"] == RentaInmuebleDoor.ATTEST_NO_AMOUNT.value
    assert context["boxes"] == "0103", context
    for language in OutputLanguage:
        words = _words(refusal, language)
        assert "%{command}" in words and "%{boxes}" in words, (language, words)
    assert "attest_prior_carries" not in repr(refusal.terminal_precondition_verdict)


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_the_negative_general_bases_keep_the_declaration_wide_door(year: int) -> None:
    refusal = _refusal(year, AbsenceAttestationFamily.RENTA_NEGATIVE_GENERAL_BASES_PENDING)

    assert "command" not in (refusal.context or {})
    assert "operator.modelo.work.attest_prior_carries" in repr(refusal.terminal_precondition_verdict)
