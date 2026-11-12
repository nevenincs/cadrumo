"""The form serves every carry whose figure the filer can state for an earlier return, and withdraws them by family.

A carry the registry reads from earlier returns, through a previous-filing
binding or a relation, takes a figure the filer states while the application
holds none of those returns. The form serves one entry per such carry its edit
takes, with the served words, the earlier returns it stands in for and its
family; once stated, the carry is marked as a stated figure of that family and
the family's statements are withdrawn together. Over an earlier return the
application holds, the statement is refused with its words and its door.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production admission, edit executor and form service, with every year taken
from the published support envelope.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from ....application.calculations.cross_period_clean_state import declared_attestable_carry_requirements
from ....application.modelo.action_errors import ModeloEditCarryWithdrawalKeepsEntriesError
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditAdmittedV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
)
from ....application.modelo.work_form_models import ModeloFormBindingAddressV1, ModeloFormField, ModeloWorkForm
from ....application.modelo.work_form_prior_value_models import (
    ModeloFormPriorValueAttestation,
    ModeloFormPriorValueRefusal,
    ModeloFormPriorValueWithdrawal,
    prior_value_family_id,
)
from ....application.modelo.work_form_service import load_modelo_work_form, modelo_form_snapshot
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ....domain.user_profile.tests.general_regime_facts import RENTA_UNMARRIED_TAXPAYER_FACTS
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_STATEMENT = "application.modelo.work_form.binding_statement.attest_prior_value"
_ENTRY = "application.modelo.work_form.prior_value_attestation"
_RENTA = (UserProfileFact(path="tax_residence.ccaa", value="madrid"), *RENTA_UNMARRIED_TAXPAYER_FACTS)
_PAYER = (
    UserProfileFact(path="withholding.has_employees", value=True),
    UserProfileFact(path="withholding.pays_rent_with_retencion", value=True),
    UserProfileFact(path="withholding.pays_capital_income_with_retencion", value=True),
)
_ENTITY = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="identity.legal_name", value="Test Company SL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
    UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="7000000"),
    UserProfileFact(path="iva.group_dominant_entity_enrolled", value=True),
)
_PRIOR_INCOME = "irpf.previous_year_economic_activity_net_income"
_PENDING_BASES = (
    "renta-base-liquidable-negativa-general-anterior",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio",
)
_M130_INSTALMENTS = "renta-modelo-130-pagos-fraccionados"
_M303_CARRY = "modelo-303-compensacion-pendiente-anteriores"


@dataclass(frozen=True, slots=True)
class _Declaration:
    """One declaration whose revision declares carries a stated figure can stand in for."""

    modelo: str
    period: str
    #: The carries the form serves, with the modelo of the earlier returns each reads.
    served: dict[str, str]
    facts: tuple[UserProfileFact, ...] = _RENTA
    regime: str | None = "directa_normal"
    #: Whether the edit is admitted on the declaration at all; a revision below calculation grade admits none.
    admitted: bool = True


_DECLARATIONS = (
    _Declaration("130", "1T", {_PRIOR_INCOME: "100"}),
    _Declaration(
        "100",
        "0A",
        {
            **dict.fromkeys(_PENDING_BASES, "100"),
            _M130_INSTALMENTS: "130",
            "renta-modelo-131-pagos-fraccionados": "131",
        },
    ),
    _Declaration("131", "4T", {"modelo-131-resultados-negativos-anteriores": "131"}, regime="objetiva"),
    _Declaration("303", "4T", {_M303_CARRY: "303"}),
    _Declaration(
        "390",
        "0A",
        dict.fromkeys(
            (
                "modelo-390-prev-303-compensaciones-reagp",
                "modelo-390-prev-303-regularizacion-cuotas-art-80-cinco-5",
                "modelo-390-prev-303-iva-importacion-aduana",
                "modelo-390-prev-303-cuota-deducible-total",
                "modelo-390-prev-303-cuota-devengada-total",
                "modelo-390-prev-303-resultado-regimen-general",
            ),
            "303",
        ),
    ),
    _Declaration(
        "180", "0A", dict.fromkeys(("modelo-180-115-base-anual", "modelo-180-115-retenciones-anual"), "115"), _PAYER
    ),
    _Declaration(
        "190",
        "0A",
        dict.fromkeys(
            (
                f"modelo-190-111-{kind}-{form}-importe-anual"
                for kind in ("trabajo", "actividades", "premios", "ganancias")
                for form in ("dinerario", "especie")
            ),
            "111",
        )
        | {"modelo-190-111-derechos-imagen-importe-anual": "111", "modelo-190-111-retenciones-anual": "111"},
        _PAYER,
    ),
    _Declaration(
        "193", "0A", dict.fromkeys(("modelo-193-123-base-anual", "modelo-193-123-retenciones-anual"), "123"), _PAYER
    ),
    _Declaration(
        "200",
        "0A",
        {
            "modelo-200-bin-pendiente-ejercicios-anteriores": "200",
            "modelo-200-dotaciones-deterioro-creditos-saldo-no-cumplido-anteriores": "200",
            "modelo-200-dotaciones-deterioro-creditos-saldo-cumplido-anteriores": "200",
            "modelo-200-pagos-fraccionados-anuales-40-2": "202",
            "modelo-200-pagos-fraccionados-anuales": "202",
        },
        _ENTITY,
        None,
    ),
    _Declaration("202", "1P", {"modelo-202-cuota-base-ejercicio-anterior": "200"}, _ENTITY, None),
    _Declaration(
        "353",
        "12",
        dict.fromkeys(
            (
                "modelo-353-prev-322-cuota-deducible-total",
                "modelo-353-prev-322-cuota-devengada-total",
                "modelo-353-prev-322-resultado-regimen-general",
            ),
            "322",
        ),
        _ENTITY,
        None,
    ),
    _Declaration(
        "714",
        "0A",
        dict.fromkeys(
            (
                f"m714-m100-{name}"
                for name in (
                    "base-imponible-general",
                    "base-imponible-ahorro",
                    "cuota-integra-estatal",
                    "cuota-integra-autonomica",
                )
            ),
            "100",
        ),
    ),
    # Declared, but the form offers none: a revision below calculation grade admits no edit, and the edit takes
    # no carry the calculation does not read.
    _Declaration("296", "0A", {}, admitted=False),
    _Declaration("720", "0A", {}),
)


def _horizon() -> int:
    support = published_supported_filing_years()
    assert support is not None
    return support.horizon


@contextmanager
def _declaration(tmp_path: Path, declaration: _Declaration) -> Generator[SeededOperatorWork]:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path,
            modelo=declaration.modelo,
            filing_year=_horizon(),
            period_code=declaration.period,
            extra_facts=declaration.facts,
            estimation_regime=declaration.regime,
        ) as work,
    ):
        yield work


def _form(work: SeededOperatorWork, language: OutputLanguage = OutputLanguage.EN) -> ModeloWorkForm:
    unit = work.work_unit
    return load_modelo_work_form(
        unit.bucket_id,
        unit.modelo,
        unit.filing_year,
        unit.period,
        operation=work.operation,
        work_unit_repository=work.ports.work_unit_repository,
        calculation_repository=work.ports.calculation_repository,
        verification_repository=work.ports.verification_repository,
        admission=work.admit(),
        language=language,
    ).form


def _entry(form: ModeloWorkForm, binding_id: str) -> ModeloFormPriorValueAttestation:
    (entry,) = [item for item in form.prior_value_attestations if item.binding_id == binding_id]
    return entry


def _field(form: ModeloWorkForm, binding_id: str) -> ModeloFormField:
    (field,) = [
        item
        for item in form.fields()
        if isinstance(item.edit_address, ModeloFormBindingAddressV1) and item.edit_address.binding_id == binding_id
    ]
    return field


def _words(key: str, language: OutputLanguage) -> str:
    words = lookup_translation(key, locale=language.value)
    assert words is not None
    return words


def _state(binding_ids: tuple[str, ...], value: str) -> tuple[ModeloBindingEditIntentV1, ...]:
    return tuple(
        ModeloBindingEditIntentV1(
            address=ModeloEditBindingAddressV1(binding_id=binding_id),
            kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
            value=Decimal(value),
        )
        for binding_id in binding_ids
    )


def _withdraw(withdrawal: ModeloFormPriorValueWithdrawal) -> tuple[ModeloBindingEditIntentV1, ...]:
    return tuple(
        ModeloBindingEditIntentV1(address=ModeloEditBindingAddressV1(binding_id=binding_id), kind=withdrawal.intent)
        for binding_id in withdrawal.binding_ids
    )


@pytest.mark.parametrize("declaration", _DECLARATIONS, ids=lambda item: f"{item.modelo}-{item.period}")
def test_every_declared_prior_value_carry_the_edit_takes_is_served_with_its_earlier_returns(
    tmp_path: Path, declaration: _Declaration
) -> None:
    with _declaration(tmp_path, declaration) as work:
        form = _form(work)
        admission = work.admit()
        snapshot = modelo_form_snapshot(
            work.operation, work.work_unit.modelo, work.work_unit.filing_year, work.work_unit.period
        )
    declared = declared_attestable_carry_requirements(snapshot)

    assert declared, "the revision declares carries a stated figure can stand in for"
    assert {entry.binding_id: entry.earlier_filings[0].modelo for entry in form.prior_value_attestations} == (
        declaration.served
    )
    for entry in form.prior_value_attestations:
        assert entry.admitted and not entry.stated
        assert entry.refusal is None and entry.withdrawal is None
        assert entry.edit_address == ModeloFormBindingAddressV1(binding_id=entry.binding_id)
        assert entry.intent is ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE
        assert [(filing.modelo, filing.period) for filing in entry.earlier_filings] == [
            (item.source_modelo, item.period) for item in declared[entry.binding_id]
        ]
        assert entry.family_id == prior_value_family_id(entry.earlier_filings)
        assert entry.action_words == _words(f"{_STATEMENT}.action", OutputLanguage.EN)
    assert isinstance(admission, ModeloEditAdmittedV1) is declaration.admitted
    assert form.edit_admitted is declaration.admitted
    if not declaration.served:
        assert "prior_value_attestations" not in form.model_dump(mode="json")
    if not declaration.served and isinstance(admission, ModeloEditAdmittedV1):
        surface = {getattr(item, "binding_id", None): item for item in admission.baseline.permitted_surface}
        assert all(
            isinstance(surface[binding_id], ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
            for binding_id in declared
        )


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_a_stated_figure_is_marked_by_its_family_and_the_family_withdrawal_returns_it_to_unstated(
    tmp_path: Path, language: OutputLanguage
) -> None:
    with _declaration(tmp_path, _DECLARATIONS[0]) as work:
        offered = _entry(_form(work, language), _PRIOR_INCOME)
        assert work.apply(binding=_state((_PRIOR_INCOME,), "12846.30")).refusal is None
        stated_form = _form(work, language)
        withdrawal = _entry(stated_form, _PRIOR_INCOME).withdrawal
        assert withdrawal is not None
        assert work.apply(binding=_withdraw(withdrawal)).refusal is None
        withdrawn_form = _form(work, language)

    assert offered.action_words == _words(f"{_STATEMENT}.action", language)
    assert offered.statement_words == _words(f"{_STATEMENT}.statement", language)
    assert offered.effect_words == _words(f"{_STATEMENT}.effect", language)
    assert str(_horizon() - 1) in offered.source_words

    stated = _entry(stated_form, _PRIOR_INCOME)
    assert stated.stated and stated.admitted
    assert withdrawal.family_id == offered.family_id
    assert withdrawal.binding_ids == (_PRIOR_INCOME,)
    assert withdrawal.action_words == _words(f"{_ENTRY}.withdrawal.action", language)
    assert withdrawal.effect_words == _words(f"{_ENTRY}.withdrawal.effect", language)
    marker = _field(stated_form, _PRIOR_INCOME).stated_prior_value
    assert marker is not None
    assert marker.family_id == offered.family_id
    assert marker.source_words == offered.source_words

    unstated = _entry(withdrawn_form, _PRIOR_INCOME)
    assert not unstated.stated and unstated.admitted and unstated.withdrawal is None
    assert _field(withdrawn_form, _PRIOR_INCOME).stated_prior_value is None


def test_one_family_is_withdrawn_alone_and_the_others_stay_stated(tmp_path: Path) -> None:
    with _declaration(tmp_path, _DECLARATIONS[1]) as work:
        applied = work.apply(binding=_state((*_PENDING_BASES, _M130_INSTALMENTS), "0"))
        assert applied.refusal is None, applied.refusal
        stated_form = _form(work)
        bases = _entry(stated_form, _PENDING_BASES[0]).withdrawal
        instalments = _entry(stated_form, _M130_INSTALMENTS).withdrawal
        assert bases is not None and instalments is not None
        # The carries that refuse the calculation unstated cannot be withdrawn while another statement stands.
        kept = work.apply(binding=_withdraw(bases))
        withdrawn = work.apply(binding=_withdraw(instalments))
        assert withdrawn.refusal is None, withdrawn.refusal
        withdrawn_form = _form(work)

    assert bases.binding_ids == tuple(sorted(_PENDING_BASES))
    assert {_entry(stated_form, binding_id).withdrawal for binding_id in _PENDING_BASES} == {bases}
    assert instalments.family_id != bases.family_id
    assert instalments.binding_ids == (_M130_INSTALMENTS,)
    assert all(_entry(withdrawn_form, binding_id).stated for binding_id in _PENDING_BASES)
    assert not _entry(withdrawn_form, _M130_INSTALMENTS).stated
    assert _entry(withdrawn_form, _M130_INSTALMENTS).withdrawal is None
    assert isinstance(kept.refusal, ModeloEditCarryWithdrawalKeepsEntriesError)


def test_withdrawing_the_figures_of_carries_the_calculation_needs_returns_the_declaration_to_no_calculation(
    tmp_path: Path,
) -> None:
    with _declaration(tmp_path, _DECLARATIONS[1]) as work:
        applied = work.apply(binding=_state(_PENDING_BASES, "0"))
        assert applied.refusal is None, applied.refusal
        bases = _entry(_form(work), _PENDING_BASES[0]).withdrawal
        assert bases is not None
        withdrawn = work.apply(binding=_withdraw(bases))
        head = work.head()
        withdrawn_form = _form(work)

    assert withdrawn.refusal is None, withdrawn.refusal
    assert head is None
    assert withdrawn_form.calculation_revision_id is None
    for binding_id in _PENDING_BASES:
        entry = _entry(withdrawn_form, binding_id)
        assert not entry.stated and entry.admitted and entry.withdrawal is None


def test_a_figure_over_an_earlier_return_the_application_holds_is_refused_with_its_words_and_door(
    tmp_path: Path,
) -> None:
    with _declaration(tmp_path, _DECLARATIONS[3]) as work:
        before = _entry(_form(work, OutputLanguage.ES), _M303_CARRY)
        (earlier,) = before.earlier_filings
        work.sibling(earlier.period.code)
        held = _entry(_form(work, OutputLanguage.ES), _M303_CARRY)

    assert before.admitted
    assert not held.admitted
    assert held.refusal_reason is ModeloFormPriorValueRefusal.SOURCE_HELD
    assert held.refusal_words == _words(f"{_ENTRY}.refusal.source_held", OutputLanguage.ES)
    assert held.refusal is not None
    assert held.refusal.action_id == "operator.modelo.work.list"
    assert held.refusal.action_words == _words(
        "application.operator_actions.served.action.modelo_work_list", OutputLanguage.ES
    )
    assert held.refusal.target_operation_ids
    assert held.family_id == before.family_id
