"""Modelo refusals carry catalogue words, so the operator never reads developer English.

Each refusal below is raised by the owning code from a real trigger and rendered
through the error renderer in every supported locale. A second check reads the
source of every module whose refusals were moved to catalogue words and renders
each key it names with a context that fills every placeholder.
"""

from __future__ import annotations

import ast
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from ....core.aggregation import BindingSourceKind
from ....core.errors.error_codes import resolve_error_message
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.period import Period
from ....domain.attachments.errors import AttachmentValidationError
from ....domain.attachments.m303_filing_evidence import M303Exonerado390ApplicabilityAssertion
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.modelos.errors import Modelo036PriorAltaRequiredError, Modelo036TerminalStateError, ModeloError
from ....domain.modelos.row_models import Modelo210AgrupacionRentaRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.m210_income_classification import resolve_m210_payer_mode
from .. import casilla_help as casilla_help_module
from .. import source_policy as source_policy_module
from ..calculation_report_verification import ExistingSigningKeypairCapability
from ..casilla_help import CasillaHelpCatalogueError, _phrase
from ..dt12_advisory import DT12_TRABAJO_REDUCCION_ROLE
from ..dt12_antiquity_advisory import dt12_antiquity_advisory_finding
from ..invoice_withholding_capture_public import PublicAnnualRecipientDetail
from ..m036_lifecycle import M036DeclarationCommand, M036DeclarationResult, _require_m036_sequence_valid
from ..m210_agrupacion_renta import validate_m210_agrupacion_renta_rows_for_calculation
from ..m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
    M303Exonerado390ApplicabilityAttestationRequest,
)
from ..profile_derived_facts import (
    ProfileBindingResolutionError,
    inject_derived_state_attribution_facts,
    renta_family_profile_from_facts,
)
from ..registry_resources import reject_unknown_period_for_revision, reject_unknown_revision
from ..review_package_counter_sign import ReviewPackageCounterSigningError
from ..review_package_exchange_operation import _envelope, _receipt, _signed
from ..review_package_exchange_operation_ports import ReviewPackageExchangeOperationPorts
from ..review_package_recipient_encryption import RecipientEncryptionError
from ..review_package_signing import ReviewPackageSigningError
from ..review_package_verification_files import (
    verify_review_package_receipt_file,
    verify_review_package_signature_file,
)
from ..selectors import ModeloCalculationRevisionSelectorAmbiguousError
from ..semantic_role_resolution import (
    AmbiguousSemanticRoleCasillaError,
    casilla_id_for_unique_revision_semantic_role,
)
from ..source_policy import UnclassifiedSourceKindError, source_policy
from ..value_presentation import (
    UnknownValuePresentationError,
    ValuePresentationCatalogueError,
    _catalogue_text,
    value_presentation_kind,
)
from ..verification_predicates import ModeloApplicabilityFilterError, evaluate_applicability_filter
from .calculation_report_fixture import BUCKET_ID, EXPORTED_AT
from .review_package_signing_support import InMemoryReviewPackageSigningKeypairCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES = ("en", "es", "ca", "hu")
_MODELO_DIR = Path(__file__).resolve().parents[1]
_KEY_PREFIXES = ("application.modelo.errors.", "errors.refused.", "errors.integrity.")
_PLACEHOLDER = re.compile(r"%\{(\w+)\}")
_WORDED_MODULES = (
    "aggregate_operation.py",
    "art20_advisory.py",
    "art52_advisory.py",
    "autonomic_deduccion_advisory.py",
    "binding_resolution.py",
    "calculation_report_verification.py",
    "casilla_help.py",
    "dt12_advisory.py",
    "dt12_antiquity_advisory.py",
    "edit_execution.py",
    "invoice_withholding_capture_public.py",
    "iva_wallet_refusal.py",
    "m036_lifecycle.py",
    "m210_agrupacion_renta.py",
    "m210_convenio_lob_advisory.py",
    "m303_exonerado_390_applicability_attestation.py",
    "operation_definitions.py",
    "profile_derived_facts.py",
    "registry_resources.py",
    "review_package_exchange_operation.py",
    "review_package_verification_files.py",
    "selectors.py",
    "semantic_role_resolution.py",
    "source_policy.py",
    "value_presentation.py",
    "verification_actions.py",
    "verification_predicates.py",
    "work_form.py",
    "work_form_field_projection.py",
    "work_form_layout.py",
)
_YEAR = filing_year_envelope().horizon


def _assert_words(error: BaseException, key: str, *mentions: str) -> None:
    assert getattr(error, "translated_message", None) == key
    for locale in _LOCALES:
        words = resolve_error_message(error, locale=locale)
        assert words, (locale, key)
        assert words != key, (locale, key)
        assert "%{" not in words, (locale, words)
        assert not words.startswith(("application.", "errors.")), (locale, words)
        for mention in mentions:
            assert mention in words, (locale, mention, words)


def _registered_cause(raised: ValidationError) -> BaseException:
    cause = next(error["ctx"]["error"] for error in raised.errors() if "ctx" in error).__cause__
    assert isinstance(cause, BaseException)
    return cause


def _declaration(declaration_id: str, kind: CensoModeloEventKind) -> M036DeclarationResult:
    return M036DeclarationResult(
        declaration_id=declaration_id,
        bucket_id="13000000-0000-4000-8000-000000000452",
        profile_id="13000000-0000-4000-8000-000000000452",
        event_kind=kind,
        declared_on=date(_YEAR, 6, 4),
        recorded_at=EXPORTED_AT,
    )


def _command(kind: CensoModeloEventKind) -> M036DeclarationCommand:
    return M036DeclarationCommand(
        profile_id="13000000-0000-4000-8000-000000000452", event_kind=kind, declared_on=date(_YEAR, 7, 1)
    )


def test_a_declaration_after_a_baja_names_both_declarations() -> None:
    baja = _declaration("a" * 64, CensoModeloEventKind.BAJA)
    with pytest.raises(Modelo036TerminalStateError) as raised:
        _require_m036_sequence_valid(
            command=_command(CensoModeloEventKind.ALTA), declaration_id="b" * 64, existing=(baja,)
        )
    _assert_words(raised.value, "application.modelo.errors.m036_declaration_after_baja", "a" * 64, "b" * 64)


def test_a_modification_without_an_alta_names_the_event_kind() -> None:
    with pytest.raises(Modelo036PriorAltaRequiredError) as raised:
        _require_m036_sequence_valid(command=_command(CensoModeloEventKind.BAJA), declaration_id="c" * 64, existing=())
    _assert_words(raised.value, "application.modelo.errors.m036_declaration_without_alta", "c" * 64)


def test_an_undeclared_revision_lists_the_declared_ones(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as raised:
        reject_unknown_revision(modelo="303", revision_id="no-such-revision", operation=operation)
    _assert_words(raised.value, "application.modelo.errors.registry_revision_not_declared", "no-such-revision", "303")


def test_an_unknown_modelo_has_no_readable_revision_list(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as raised:
        reject_unknown_revision(modelo="998", revision_id="x", operation=operation)
    _assert_words(raised.value, "application.modelo.errors.registry_modelo_revisions_unreadable", "998")


def test_an_undeclared_period_lists_the_declared_ones(operation: PinnedAuthorityOperation) -> None:
    revision = operation.revision_for_context("303", filing_year=_YEAR, period="1T")
    with pytest.raises(ModeloError) as raised:
        reject_unknown_period_for_revision(
            modelo="303", revision_id=revision.id, period=Period.from_year_and_code(_YEAR, "0A"), operation=operation
        )
    _assert_words(raised.value, "application.modelo.errors.registry_period_not_declared", "0A", revision.id)


def test_an_unreadable_revision_is_worded(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as raised:
        reject_unknown_period_for_revision(
            modelo="303", revision_id="no-such", period=Period.from_year_and_code(_YEAR, "1T"), operation=operation
        )
    _assert_words(raised.value, "application.modelo.errors.registry_revision_unreadable", "no-such")


def _two_casillas_claiming(role: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="rev",
        casillas=(SimpleNamespace(id="0001", semantic_role=role), SimpleNamespace(id="0002", semantic_role=role)),
    )


def test_a_role_two_casillas_claim_names_the_role_and_the_casillas() -> None:
    with pytest.raises(AmbiguousSemanticRoleCasillaError) as raised:
        casilla_id_for_unique_revision_semantic_role(_two_casillas_claiming("shared.role"), "shared.role")
    _assert_words(raised.value, "application.modelo.errors.semantic_role_ambiguous", "shared.role", "0001", "0002")


def test_an_advisory_refuses_with_words_when_a_role_is_ambiguous(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as raised:
        dt12_antiquity_advisory_finding(
            _two_casillas_claiming(DT12_TRABAJO_REDUCCION_ROLE),
            {},
            operation=operation,
            modelo="100",
            effective_date=date(_YEAR, 12, 31),
        )
    _assert_words(
        raised.value, "application.modelo.errors.semantic_role_ambiguous", DT12_TRABAJO_REDUCCION_ROLE, "0002"
    )


def test_a_selector_that_matches_several_revisions_is_worded() -> None:
    error = ModeloCalculationRevisionSelectorAmbiguousError(())
    _assert_words(error, "errors.refused.modelo_calculation_revision_selector_ambiguous")


def _annual_m210_unit(operation: PinnedAuthorityOperation) -> WorkUnit:
    period = Period.from_year_and_code(_YEAR, "0A")
    revision_id = operation.revision_for_context("210", filing_year=_YEAR, period="0A").id
    bucket_id = "13000000-0000-4000-8000-000000000452"
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id, modelo="210", filing_year=_YEAR, period=period, revision_id=revision_id
        ),
        bucket_id=bucket_id,
        modelo="210",
        filing_year=_YEAR,
        period=period,
        revision_id=revision_id,
        name="grouped-renta",
        created_at=EXPORTED_AT,
        updated_at=EXPORTED_AT,
    )


def _lease_row(source_id: str) -> Modelo210AgrupacionRentaRow:
    return Modelo210AgrupacionRentaRow(
        source_id=source_id,
        tipo_renta_code="01",
        importe=Decimal("100.00"),
        tipo_gravamen=Decimal("0.24"),
        pagador_mode=resolve_m210_payer_mode(effective_date=date(_YEAR, 1, 1)),
        pagador_id="ES-PAGADOR-1",
        deriva_de_bien_derecho=True,
        bien_derecho_id="ES-INMUEBLE-1",
    )


def test_an_empty_grouped_renta_set_is_worded(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as raised:
        validate_m210_agrupacion_renta_rows_for_calculation(
            work_unit=_annual_m210_unit(operation), detail_rows=(), m210_official_tipo_renta_code="01"
        )
    _assert_words(raised.value, "application.modelo.errors.m210_agrupacion_empty_group")


def test_two_grouped_rows_with_one_source_id_are_worded(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ModeloError) as raised:
        validate_m210_agrupacion_renta_rows_for_calculation(
            work_unit=_annual_m210_unit(operation),
            detail_rows=(_lease_row("same"), _lease_row("same")),
            m210_official_tipo_renta_code="01",
        )
    _assert_words(raised.value, "application.modelo.errors.m210_agrupacion_duplicate_source_id")


def test_an_attachment_identity_that_contradicts_its_digest_is_worded() -> None:
    with pytest.raises(AttachmentValidationError) as raised:
        M303Exonerado390ApplicabilityAttestationAdmission(attachment_id="a" * 64, sha256="b" * 64)
    _assert_words(raised.value, "application.modelo.errors.m390_attestation_attachment_digest_differs")


def test_a_period_of_another_year_than_the_attestation_is_worded() -> None:
    with pytest.raises(AttachmentValidationError) as raised:
        M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR - 1, "1T"),
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=EXPORTED_AT,
        )
    _assert_words(
        raised.value, "application.modelo.errors.m390_attestation_period_year_differs", str(_YEAR), str(_YEAR - 1)
    )


def test_an_order_number_above_the_form_ceiling_is_worded() -> None:
    with bundled_indexed_authority().operation(), pytest.raises(ValidationError) as raised:
        PublicAnnualRecipientDetail.model_validate({"numero_orden": 10**9})
    _assert_words(
        _registered_cause(raised.value),
        "application.modelo.errors.withholding_order_number_above_form_ceiling",
        str(10**9),
    )


def test_an_unset_tax_territory_is_worded(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ProfileBindingResolutionError) as raised:
        inject_derived_state_attribution_facts({}, operation=operation)
    _assert_words(raised.value, "application.modelo.errors.profile_jurisdiction_scope_required")


def test_an_unsupported_tax_territory_is_named(operation: PinnedAuthorityOperation) -> None:
    with pytest.raises(ProfileBindingResolutionError) as raised:
        inject_derived_state_attribution_facts(
            {"tax_residence.jurisdiction_scope": "no-such-territory"}, operation=operation
        )
    _assert_words(raised.value, "application.modelo.errors.profile_jurisdiction_scope_unsupported", "no-such-territory")


def test_a_stored_birth_date_that_is_not_a_date_names_the_descendant() -> None:
    with pytest.raises(ProfileBindingResolutionError) as raised:
        renta_family_profile_from_facts({"renta_family.descendiente.0.birth_date": "not-a-date"})
    _assert_words(raised.value, "application.modelo.errors.profile_descendant_birth_date_invalid", "1")


def test_an_unreadable_signature_file_is_worded(tmp_path: Path) -> None:
    unreadable = tmp_path / "signature.json"
    unreadable.write_text("not json", encoding="utf-8")
    package = tmp_path / "package.zip"
    package.write_bytes(b"")
    with pytest.raises(ReviewPackageSigningError) as raised:
        verify_review_package_signature_file(package, unreadable, public_key="0" * 64)
    _assert_words(raised.value, "application.modelo.errors.review_package_signature_file_unreadable")


def test_an_unreadable_receipt_file_is_worded(tmp_path: Path) -> None:
    unreadable = tmp_path / "receipt.json"
    unreadable.write_text("not json", encoding="utf-8")
    package = tmp_path / "package.zip"
    package.write_bytes(b"")
    with pytest.raises(ReviewPackageCounterSigningError) as raised:
        verify_review_package_receipt_file(
            package, unreadable, operator_public_key="0" * 64, counter_signer_public_key="1" * 64
        )
    _assert_words(raised.value, "application.modelo.errors.review_package_receipt_file_unreadable")


class _TextFiles:
    """A file port that serves one fixed text, whatever path is asked."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read_text(self, path: Path) -> str:
        return self._text


class _FilePorts:
    """The only capability the file readers use: the file port."""

    def __init__(self, files: _TextFiles) -> None:
        self.files = files


def test_the_exchange_operation_words_each_unreadable_file(tmp_path: Path) -> None:
    ports = cast("ReviewPackageExchangeOperationPorts", _FilePorts(_TextFiles("not json")))
    with pytest.raises(ReviewPackageSigningError) as signed:
        _signed(tmp_path / "file.json", ports)
    _assert_words(signed.value, "application.modelo.errors.review_package_signature_file_unreadable")
    with pytest.raises(ReviewPackageCounterSigningError) as receipt:
        _receipt(tmp_path / "file.json", ports)
    _assert_words(receipt.value, "application.modelo.errors.review_package_receipt_file_unreadable")
    with pytest.raises(RecipientEncryptionError) as envelope:
        _envelope(tmp_path / "file.json", ports)
    _assert_words(envelope.value, "application.modelo.errors.review_package_envelope_file_unreadable")


def test_a_signing_capability_of_another_profile_is_worded() -> None:

    keypair = InMemoryReviewPackageSigningKeypairCapability().ensure_keypair(
        bucket_id=BUCKET_ID, generated_at=EXPORTED_AT
    )
    with pytest.raises(ReviewPackageSigningError) as raised:
        ExistingSigningKeypairCapability(keypair).ensure_keypair(bucket_id="33333333-3333-4333-8333-333333333333")
    _assert_words(raised.value, "application.modelo.errors.signing_capability_other_profile")


def test_a_data_type_without_a_presentation_is_named() -> None:
    with pytest.raises(UnknownValuePresentationError) as raised:
        value_presentation_kind("no-such-data-type")
    _assert_words(
        raised.value, "application.modelo.errors.value_presentation_data_type_undeclared", "no-such-data-type"
    )


def test_a_value_text_missing_in_a_language_is_named() -> None:
    with pytest.raises(ValuePresentationCatalogueError) as raised:
        _catalogue_text("application.modelo.no_such_text", OutputLanguage.EN)
    _assert_words(
        raised.value,
        "application.modelo.errors.catalogue_text_missing_for_language",
        "application.modelo.no_such_text",
    )


def test_a_help_phrase_missing_in_a_language_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(casilla_help_module, "_HELP_LOCALE_KEYS", {"probe": "application.modelo.help.no_such_probe"})
    with pytest.raises(CasillaHelpCatalogueError) as raised:
        _phrase(OutputLanguage.EN, "probe")
    _assert_words(
        raised.value,
        "application.modelo.errors.catalogue_text_missing_for_language",
        "application.modelo.help.no_such_probe",
    )


def test_a_source_kind_without_a_family_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source_policy_module, "_FAMILY_AND_SURFACE", {})
    with pytest.raises(UnclassifiedSourceKindError) as raised:
        source_policy(BindingSourceKind.MANUAL_INPUT)
    _assert_words(
        raised.value, "application.modelo.errors.binding_source_kind_unclassified", BindingSourceKind.MANUAL_INPUT.value
    )


def test_an_unknown_applicability_filter_is_named(operation: PinnedAuthorityOperation) -> None:
    profile = TaxpayerProfile(tax_id="X0001500M", iva_regime=IVARegime("GENERAL"))
    with pytest.raises(ModeloApplicabilityFilterError) as raised:
        evaluate_applicability_filter("no-such-filter", profile)
    _assert_words(raised.value, "application.modelo.errors.applicability_filter_unknown", "no-such-filter")


def _string_constants(tree: ast.AST) -> set[str]:
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(_KEY_PREFIXES)
    }


@pytest.mark.parametrize("module_name", _WORDED_MODULES)
def test_every_key_a_worded_module_names_renders_words_in_all_locales(module_name: str) -> None:
    keys = _string_constants(ast.parse((_MODELO_DIR / module_name).read_text(encoding="utf-8")))
    assert keys, module_name
    for key in sorted(keys):
        english = tr(key, locale="en")
        assert english != key, key
        fill = {name: "x" for name in _PLACEHOLDER.findall(english)}
        for locale in _LOCALES:
            words = tr(key, locale=locale, **fill)
            assert words and words != key, (locale, key)
            assert "%{" not in words, (locale, key, words)
