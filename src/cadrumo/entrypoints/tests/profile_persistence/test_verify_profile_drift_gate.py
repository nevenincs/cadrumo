"""Real-path tests for the profile-drift gate over a Modelo 100 calculation.

A saved calculation records every profile fact path its calculation read, with a
digest of each value, and verify compares those reads with the profile as it
stands. The probe is the support floor's Modelo 100 for a filer with two
descendants: the Art. 58 mínimo is a derived selector computed from their stored
facts, so an edit to a descendant reaches the casillas only through that
derivation, never through a binding that names the descendant's path.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production edit executor, calculation and verification, with every year
taken from the published support envelope.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ....application.aggregation.tests.test_inventory_source import inventory_ledger
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ....application.modelo.edit_services import calculation_head_digest
from ....application.modelo.export_contracts import ModeloExportEvidenceMissingError
from ....application.modelo.profile_drift_gate import (
    PROFILE_DRIFT_KEY,
    PROFILE_READS_UNKNOWN_KEY,
    require_profile_reads_current_for_export,
)
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.verification_preconditions import VerificationFindingPreconditionProjection
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.contribuyente.inventory.records import InventoryLedgerDocument
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.calculation_repository import upsert_calculation_revision
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id_from_revision,
)
from ....domain.modelos.profile_read_fingerprint import ProfileReadScope, ProfileReadSource
from ....domain.modelos.verification_report import (
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.user_profile.registry_contract import profile_binding_selectors
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact, UserProfileFactValue
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The negative bases and savings balances pending from earlier ejercicios, which a Modelo 100 refuses to calculate
#: without a statement: the general base, then the net capital income and the net gains and losses of the savings base.
_PENDING_CARRIES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
    *(
        f"renta-saldo-negativo-{kind}-ahorro-{origin}-pendiente-inicio"
        for kind in ("rcm", "gyp")
        for origin in ("em1", "em2", "em3", "em4")
    ),
)
_ELDER = "renta_family.descendiente.0.birth_date"
_YOUNGER = "renta_family.descendiente.1.birth_date"
#: Read only by the renta ledger's home-office afectación (LIRPF art. 30.2.5ª), never by the profile resolver.
_LEDGER_ONLY = "vivienda_office.office_m2"
#: A profile fact no Modelo 100 calculation reads: the operator's contact email.
_UNREAD = "identity.email"


def _year() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return support.floor


def _descendant_facts(year: int) -> tuple[UserProfileFact, ...]:
    """Two Art. 58-eligible children, each with the surnames and name the design requires of a row."""
    descendants = (
        DescendantInfo(birth_date=date(year - 14, 3, 4)),
        DescendantInfo(birth_date=date(year - 10, 9, 18)),
    )
    return (
        *(UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_list(descendants)),
        UserProfileFact(path="renta_family.descendiente.0.apellidos_nombre", value="Ortega Navarro Pablo"),
        UserProfileFact(path="renta_family.descendiente.1.apellidos_nombre", value="Ortega Navarro Lucia"),
    )


@contextmanager
def _annual_work(tmp_path: Path) -> Generator[SeededOperatorWork]:
    """Seed the support floor's Modelo 100 and calculate it with the pending carries stated as none."""
    year = _year()
    facts = (
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        *RENTA_UNMARRIED_TAXPAYER_FACTS,
        *_descendant_facts(year),
    )
    with (
        profile_adapter_composition(),
        seeded_operator_work(tmp_path, modelo="100", filing_year=year, period_code="0A", extra_facts=facts) as work,
    ):
        InventoryLedgerRepository().save(InventoryLedgerDocument(ledgers=(inventory_ledger("actividad", year=year),)))
        stated = tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT,
                value=None,
            )
            for binding_id in _PENDING_CARRIES
        )
        assert work.apply(binding=stated).refusal is None
        yield work


def _edit(work: SeededOperatorWork, path: str, value: UserProfileFactValue) -> None:
    upsert_test_profile_facts(work.work_unit.bucket_id, (UserProfileFact(path=path, value=value),))


def _verify(
    work: SeededOperatorWork, revision: CalculationRevision
) -> tuple[VerificationFindingPreconditionProjection, ...]:
    result = verify_modelo_revision_with_preconditions(
        revision.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        actor="operator-test",
        workflow_profile=TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL")),
        operator_scope_ports=build_operator_scope_ports(),
        operation=work.operation,
    )
    return result.finding_preconditions


def _with_key(
    projections: tuple[VerificationFindingPreconditionProjection, ...], key: str
) -> list[VerificationFindingPreconditionProjection]:
    return [projection for projection in projections if projection.finding.message_locale_key == key]


def _read_paths(revision: CalculationRevision) -> frozenset[str]:
    fingerprint = revision.profile_read_fingerprint
    assert fingerprint is not None
    return frozenset(entry.selector for entry in fingerprint.entries if entry.scope is ProfileReadScope.PATH)


def _read_prefixes(revision: CalculationRevision) -> frozenset[str]:
    fingerprint = revision.profile_read_fingerprint
    assert fingerprint is not None
    return frozenset(entry.selector for entry in fingerprint.entries if entry.scope is ProfileReadScope.PREFIX)


def _read_paths_from(revision: CalculationRevision, source: ProfileReadSource) -> frozenset[str]:
    fingerprint = revision.profile_read_fingerprint
    assert fingerprint is not None
    return frozenset(
        entry.selector
        for entry in fingerprint.entries
        if entry.scope is ProfileReadScope.PATH and entry.source is source
    )


def _bound_selectors(work: SeededOperatorWork) -> frozenset[str]:
    """Every profile path a binding of the revision names directly."""
    revision = work.operation.revision(work.work_unit.modelo, work.work_unit.revision_id)
    return frozenset(
        selector for binding in revision.bindings for selector in profile_binding_selectors(binding.provider)
    )


def test_a_descendant_edit_blocks_the_draft_and_calculating_again_clears_it(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        calculated = work.require_head()
        assert _ELDER in _read_paths(calculated)
        assert not _with_key(_verify(work, calculated), PROFILE_DRIFT_KEY)

        # Older than the Art. 58 age limit at the end of the ejercicio: the child no longer counts.
        _edit(work, _ELDER, date(_year() - 30, 3, 4))
        (drift,) = _with_key(_verify(work, calculated), PROFILE_DRIFT_KEY)

        recalculated = work.recalculate()
        cleared = _verify(work, recalculated)

    assert drift.finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert drift.finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert drift.precondition_failure is not None
    (evidence,) = drift.precondition_failure.verdict.evidence
    # The date itself and the descendant section it belongs to both moved.
    assert {_ELDER, "renta_family.descendiente."} <= set(str(evidence.values["changed_reads"]).split("|"))
    assert drift.finding.message_facts["changed_count"] == evidence.values["changed_read_count"]
    action = drift.precondition_failure.verdict.action
    assert action is not None
    assert action.action_id == "operator.modelo.work.calculate"
    assert recalculated.calculation_revision_id != calculated.calculation_revision_id
    assert not _with_key(cleared, PROFILE_DRIFT_KEY)


def test_an_edit_to_a_fact_the_calculation_did_not_read_does_not_fire(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        calculated = work.require_head()
        assert _UNREAD not in _read_paths(calculated)
        assert not any(_UNREAD.startswith(prefix) for prefix in _read_prefixes(calculated))

        _edit(work, _UNREAD, "otra.persona@example.test")
        findings = _verify(work, calculated)

    assert not _with_key(findings, PROFILE_DRIFT_KEY)


def test_an_edit_that_reaches_the_casillas_only_through_a_derived_selector_fires(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        calculated = work.require_head()
        # No binding names the descendant's date: only the Art. 58 derivation reads it.
        assert _YOUNGER not in _bound_selectors(work)
        assert _YOUNGER in _read_paths(calculated)

        # Under three at the end of the ejercicio: the derived mínimo gains its supplement.
        _edit(work, _YOUNGER, date(_year() - 1, 9, 18))
        findings = _verify(work, calculated)

    (drift,) = _with_key(findings, PROFILE_DRIFT_KEY)
    assert drift.finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION


def test_a_revision_without_recorded_reads_is_disclosed_not_refused(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        recorded = work.require_head()
        identity = derive_calculation_revision_id_from_revision(recorded)
        old = recorded.model_copy(update={"profile_read_fingerprint": None})
        assert derive_calculation_revision_id_from_revision(old) == identity
        assert "profile_read_fingerprint" not in old.model_dump(mode="json")
        with_key_dropped = recorded.model_dump(mode="json")
        del with_key_dropped["profile_read_fingerprint"]
        assert with_key_dropped == old.model_dump(mode="json")
        assert calculation_head_digest(old) == calculation_head_digest(
            recorded.model_copy(update={"profile_read_fingerprint": None})
        )

        repository = work.ports.calculation_repository
        repository.save(upsert_calculation_revision(repository.load(operation=work.operation), old))
        _edit(work, _ELDER, date(_year() - 30, 3, 4))
        findings = _verify(work, old)

    (unknown,) = _with_key(findings, PROFILE_READS_UNKNOWN_KEY)
    assert unknown.finding.kind is ModeloVerificationFindingKind.ADVISORY
    assert unknown.finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert not _with_key(findings, PROFILE_DRIFT_KEY)


def test_recorded_reads_round_trip_through_the_encrypted_store(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        head = work.require_head()
        stored = work.ports.calculation_repository.load(operation=work.operation).get(head.calculation_revision_id)

    assert stored is not None
    assert stored.profile_read_fingerprint == head.profile_read_fingerprint


def test_export_refuses_a_verified_revision_whose_read_facts_were_edited(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        # The gate's subject is the state a grant seals; the stored profile is the real one.
        verified = work.require_head().model_copy(update={"state": CalculationRevisionState.VERIFICADO_COMPLETO})
        unrecorded = verified.model_copy(update={"profile_read_fingerprint": None})
        require_profile_reads_current_for_export(verified, work.work_unit, operation=work.operation)

        _edit(work, _UNREAD, "otra.persona@example.test")
        require_profile_reads_current_for_export(verified, work.work_unit, operation=work.operation)

        _edit(work, _ELDER, date(_year() - 30, 3, 4))
        with pytest.raises(ModeloExportEvidenceMissingError) as refused:
            require_profile_reads_current_for_export(verified, work.work_unit, operation=work.operation)
        # Unknown reads were disclosed at verify; export does not refuse them.
        require_profile_reads_current_for_export(unrecorded, work.work_unit, operation=work.operation)
        # A draft is the verify gate's to block, and a filed revision is exported as filed.
        for state in (CalculationRevisionState.BORRADOR, CalculationRevisionState.PRESENTADO):
            require_profile_reads_current_for_export(
                verified.model_copy(update={"state": state}), work.work_unit, operation=work.operation
            )

    context = refused.value.context
    assert context is not None
    assert context["reason"] == "profile_read_drift"
    assert context["calculation_revision_id"] == verified.calculation_revision_id


def test_an_edit_to_a_fact_only_the_ledger_reads_fires(tmp_path: Path) -> None:
    with _annual_work(tmp_path) as work:
        calculated = work.require_head()
        # The profile resolver neither binds nor reads it; the calculation's ledger source does.
        assert _LEDGER_ONLY not in _bound_selectors(work)
        assert _LEDGER_ONLY not in _read_paths_from(calculated, ProfileReadSource.INDEX)
        assert _LEDGER_ONLY in _read_paths_from(calculated, ProfileReadSource.RECORD)

        _edit(work, _LEDGER_ONLY, Decimal("12.5"))
        findings = _verify(work, calculated)

    (drift,) = _with_key(findings, PROFILE_DRIFT_KEY)
    assert drift.precondition_failure is not None
    (evidence,) = drift.precondition_failure.verdict.evidence
    assert _LEDGER_ONLY in str(evidence.values["changed_reads"]).split("|")
