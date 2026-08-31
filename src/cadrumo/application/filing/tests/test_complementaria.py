"""Tests for complementaria registry-boundary behaviour."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from typing import TYPE_CHECKING

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.filing.errors import ModeloAmendmentError, ModeloBuilderError
from ....domain.filing.protocols import ModeloInputs
from ....domain.filing.schema import (
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)
from ....domain.submission._protocols import ModeloDraftStatus
from ....domain.submission.models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id
from .._complementaria import build_complementaria, load_amendment
from .._draft_construction import build_draft
from ..runtime import ModeloOperatorProfile, build_runtime_schema_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ..runtime import RegistrySchemaAccessor

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_PAGOS_PREVIOS_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_PAGOS_PREVIOS_CASILLA")
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("06", surface="_M130_RETENCIONES_CASILLA")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_AGRARIAN_VOLUME_CASILLA")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_AGRARIAN_WITHHELD_CASILLA")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_HOME_DEDUCTION_CASILLA")
_M130_PRIOR_RETURN_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_PRIOR_RETURN_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")
_UNREGISTERED_M037_SOURCE_CASILLA: CasillaId = validated_casilla_id("69", surface="_UNREGISTERED_M037_SOURCE_CASILLA")
_UNREGISTERED_M037_UPDATE_BASE_CASILLA: CasillaId = validated_casilla_id(
    "07",
    surface="_UNREGISTERED_M037_UPDATE_BASE_CASILLA",
)
_UNREGISTERED_M037_UPDATE_CUOTA_CASILLA: CasillaId = validated_casilla_id(
    "29",
    surface="_UNREGISTERED_M037_UPDATE_CUOTA_CASILLA",
)
_UNREGISTERED_M993_SOURCE_CASILLA: CasillaId = validated_casilla_id("109", surface="_UNREGISTERED_M993_SOURCE_CASILLA")
_UNREGISTERED_M993_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "01",
    surface="_UNREGISTERED_M993_EJERCICIO_CASILLA",
)


def _persist_original_draft(draft: ModeloDraft) -> None:
    from ....adapters.persistence.profile.filing_drafts import ModeloDraftRepository

    ModeloDraftRepository().save(draft)


def _persisted_amendment_ids() -> tuple[str, ...]:
    from ....adapters.persistence.profile.filing_amendments import ModeloAmendmentRepository

    return ModeloAmendmentRepository().list_amendment_ids()


def _snapshot_ref(*, modelo: str, period: Period, revision_id: str) -> RegistrySnapshotRef:
    return RegistrySnapshotRef(
        modelo=modelo,
        revision_id=revision_id,
        modelo_year=period.filing_year,
        period=period.registry_token,
    )


@cache
def _schema_provider() -> RegistrySchemaAccessor:
    return build_runtime_schema_provider()


#: A justificante CSV in the shape ``AeatCsv`` declares: uppercase alphanumerics,
#: 8 to 32 characters. AEAT's Código Seguro de Verificación carries no separators,
#: so a hyphenated placeholder is not a CSV the submission record can hold.
_ORIGINAL_JUSTIFICANTE_CSV = "CSVORIGINAL0001"

#: A checksum-VALID NIE naming somebody other than the drafts built here, whose
#: identity is ``00000000T``. Validity is load-bearing: the identity guard routes
#: the submitted side through the shared tax-id authority before comparing, so a
#: fabricated identifier would refuse as malformed and the divergence assertion
#: would pass without ever testing that the two sides name DIFFERENT taxpayers.
_OTHER_TAXPAYER_NIF = "X1234567L"

#: Correctly shaped for a NIF and belonging to nobody: ``00000000`` checks to the
#: letter ``T``, so this fails the checksum. It is also unequal to the draft's
#: identity, which is what makes it able to tell the malformed refusal apart from
#: the divergence refusal — only a guard that validates BEFORE comparing reports
#: it as malformed.
_MALFORMED_TAX_ID = "00000000X"


@dataclass(frozen=True)
class _ConformingSubmittedOriginal:
    """A submitted-filing record carrying the declared structural contract.

    :func:`build_complementaria` declares its input as a ``Protocol``, and
    ``ModeloPresentado`` — the sole concrete satisfier — validates
    ``profile_tax_id`` as a ``SubjectTaxId`` at its own model boundary. The
    absent and malformed identities the guard rules on are therefore
    unconstructible through that model and reachable only through the contract
    the function actually declares. This carries real values through that
    contract; it fakes no behaviour and stands in for no collaborator.
    """

    submission_id: str
    draft_id: str
    modelo: str
    period: Period
    profile_tax_id: str
    justificante_csv: str | None


def _conforming_submitted_filing(draft: ModeloDraft, *, profile_tax_id: str) -> _ConformingSubmittedOriginal:
    return _ConformingSubmittedOriginal(
        submission_id=make_submission_id("sub-identity", 1),
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=profile_tax_id,
        justificante_csv=_ORIGINAL_JUSTIFICANTE_CSV,
    )


def _submitted_filing(
    draft: ModeloDraft,
    *,
    submission_id: str = "sub-1",
    justificante_csv: str | None = _ORIGINAL_JUSTIFICANTE_CSV,
    profile_tax_id: str | None = None,
) -> ModeloPresentado:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    # ``submission_id`` names the case, not the stored identity: the record's
    # identity is the content-derived coordinate the submission domain mints.
    resolved_submission_id = make_submission_id(submission_id, 1)
    return ModeloPresentado(
        submission_id=resolved_submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id if profile_tax_id is None else profile_tax_id,
        status=SubmissionStatus.PRESENTADA,
        justificante_csv=justificante_csv,
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{resolved_submission_id}.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


def _draft(modelo: str, period: Period, casillas: dict[CasillaId, Decimal]) -> ModeloDraft:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    # The draft names a revision the registry does not carry; its schema marker
    # must still be the marker for THAT revision, not a second, differently
    # shaped string.
    revision_id = "missing"
    schema_version = registry_schema_version(modelo=modelo, revision_id=revision_id)
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=value,
            kind=ModeloValueKind.LITERAL,
            source="input",
        )
        for casilla_id, value in sorted(casillas.items())
    )
    snapshot_ref = _snapshot_ref(modelo=modelo, period=period, revision_id=revision_id)
    return ModeloDraft(
        draft_id=compute_modelo_draft_id(
            modelo=modelo,
            period=period,
            profile_tax_id="00000000T",
            snapshot_ref=snapshot_ref,
            values=values,
        ),
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        subject_tax_id="00000000T",
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.PRESENTADA,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=schema_version,
    )


def _registry_draft(*, inputs: ModeloInputs) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=Period.from_year_and_code(2024, "1T"),
        profile=ModeloOperatorProfile(
            tax_id="00000000T",
            display_name="Complementaria registry test",
        ),
        inputs=inputs,
        schema_provider=_schema_provider(),
    )


class TestBuildComplementaria:
    def test_modelo_130_builds_and_persists_complementaria(self) -> None:
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                _M130_PAGOS_PREVIOS_CASILLA: Decimal("250"),
                _M130_RETENCIONES_CASILLA: Decimal("100"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("2000"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("10"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-pagos-fraccionados-anteriores": Decimal("250"),
                # Casilla 15 omitted: M130 carry-forward must flow
                # through binding_values via
                # `modelo-130-resultados-negativos-anteriores`, not as
                # a direct casilla input. Same pattern as the M130
                # binding-id fix from #71/#95.
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_CASILLA: Decimal("0"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft)

        amendment = build_complementaria(
            original,
            {
                _M130_INGRESOS_CASILLA: Decimal("13000"),
                _M130_GASTOS_CASILLA: Decimal("3500"),
                _M130_PAGOS_PREVIOS_CASILLA: Decimal("400"),
                _M130_RETENCIONES_CASILLA: Decimal("0"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                "modelo-130-pagos-fraccionados-anteriores": Decimal("400"),
            },
            schema_provider=_schema_provider(),
        )

        changed = {change.casilla_id: change for change in amendment.delta}
        assert amendment.original_model == "130"
        assert amendment.amendment_kind.value == "complementaria"
        assert changed[_M130_RESULTADO_FINAL_CASILLA].new_value == Decimal("1530.00")
        assert load_amendment(amendment.amendment_id).amendment_id == amendment.amendment_id

    def test_load_amendment_rejects_traversal_id(self) -> None:
        with pytest.raises(ModeloAmendmentError, match="path separators"):
            load_amendment("../escape")

    def test_complementaria_requires_official_justificante_csv(self) -> None:
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, justificante_csv=None)

        with pytest.raises(
            ModeloBuilderError, match=r"^application\.filing\.complementaria\.errors\.original_submission_csv_blank$"
        ):
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_complementaria_requires_original_registry_snapshot(self) -> None:
        built = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        # Restate the draft as one built against a NON-ACTIVE registry revision.
        # Both identity fields move together: a draft whose schema marker names
        # one revision while its snapshot_ref names another is incoherent and no
        # longer persists, so moving only the marker would exercise the
        # persistence refusal instead of the stale-snapshot refusal under test.
        stale_revision = "wrong-revision"
        stale_snapshot_ref = built.snapshot_ref.model_copy(update={"revision_id": stale_revision})
        original_draft = built.model_copy(
            update={
                "snapshot_ref": stale_snapshot_ref,
                "schema_version": registry_schema_version(modelo=built.modelo, revision_id=stale_revision),
                # The id is the draft's content address, and the snapshot is part
                # of that content, so restating the snapshot restates the id.
                "draft_id": compute_modelo_draft_id(
                    modelo=built.modelo,
                    period=built.period,
                    profile_tax_id=built.profile_tax_id,
                    snapshot_ref=stale_snapshot_ref,
                    values=built.values,
                    binding_values=built.binding_values,
                ),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft)

        with pytest.raises(
            ModeloBuilderError, match=r"^application\.filing\.complementaria\.errors\.original_draft_snapshot_stale$"
        ):
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_unknown_modelo_requires_registry_definition(self) -> None:
        original_draft = _draft(
            # A real AEAT code the calculation registry deliberately does not carry.
            "037",
            Period.from_year_and_code(2024, "2T"),
            {_UNREGISTERED_M037_SOURCE_CASILLA: Decimal("1900.00")},
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-999")

        with pytest.raises(ModeloBuilderError, match=r"^application\.filing\.runtime\.errors\.modelo_not_in_registry$"):
            build_complementaria(
                original,
                {
                    _UNREGISTERED_M037_UPDATE_BASE_CASILLA: Decimal("11000.00"),
                    _UNREGISTERED_M037_UPDATE_CUOTA_CASILLA: Decimal("200.00"),
                },
                schema_provider=_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_matching_taxpayer_identity_across_submission_and_draft_builds(self) -> None:
        """The submitted filing and the draft it amends name one taxpayer, so the build proceeds.

        Paired with the divergence case below: a guard that refuses everything
        would satisfy that one alone, so the agreeing direction is asserted
        explicitly and the built amendment is confirmed to carry that one
        identity through to the rebuilt draft.
        """
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-identity-ok")

        amendment = build_complementaria(
            original,
            {_M130_INGRESOS_CASILLA: Decimal("11000")},
            schema_provider=_schema_provider(),
        )

        assert original.profile_tax_id == original_draft.profile_tax_id
        assert amendment.amended_draft.profile_tax_id == original_draft.profile_tax_id
        assert amendment.amendment_id in _persisted_amendment_ids()

    def test_divergent_taxpayer_identity_refuses_before_the_amendment_is_built(self) -> None:
        """A submitted filing naming another taxpayer cannot amend this draft.

        Both identities are individually valid, which is the whole point: the
        draft's own cross-field invariant and the ``SubjectTaxId`` checksum both
        pass, and only a comparison ACROSS the two separately loaded objects
        sees the divergence.
        """
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(
            original_draft,
            submission_id="sub-identity-diverges",
            profile_tax_id=_OTHER_TAXPAYER_NIF,
        )

        with pytest.raises(
            ModeloBuilderError, match=r"^application\.filing\.errors\.complementaria_taxpayer_identity_mismatch$"
        ) as raised:
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=_schema_provider(),
            )

        assert str(raised.value) == "application.filing.errors.complementaria_taxpayer_identity_mismatch"
        context = raised.value.context
        assert isinstance(context, dict)
        assert _OTHER_TAXPAYER_NIF in str(context["submitted_tax_id"])
        assert original_draft.profile_tax_id in str(context["draft_tax_id"])
        assert _persisted_amendment_ids() == ()

    def test_absent_submitted_taxpayer_identity_refuses_rather_than_passing_through(self) -> None:
        """A blank declared identity is corruption of a non-optional field, not an exemption."""
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _conforming_submitted_filing(original_draft, profile_tax_id="   ")

        with pytest.raises(
            ModeloBuilderError, match=r"^application\.filing\.errors\.complementaria_taxpayer_identity_absent$"
        ):
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_malformed_submitted_taxpayer_identity_refuses_as_unconfirmable(self) -> None:
        """Equality of characters is not the question; naming a taxpayer at all is prior to it.

        Pins the canonicalisation ruling: the submitted side is routed through
        the shared tax-id authority BEFORE the comparison, so a value that names
        nobody is reported as malformed rather than as a different taxpayer. A
        guard that compared the raw strings would report this as a divergence.
        """
        original_draft = _registry_draft(
            inputs={
                _M130_INGRESOS_CASILLA: Decimal("10000"),
                _M130_GASTOS_CASILLA: Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _conforming_submitted_filing(original_draft, profile_tax_id=_MALFORMED_TAX_ID)

        with pytest.raises(
            ModeloBuilderError, match=r"^application\.filing\.errors\.complementaria_taxpayer_identity_malformed$"
        ):
            build_complementaria(
                original,
                {_M130_INGRESOS_CASILLA: Decimal("11000")},
                schema_provider=_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_unknown_annual_modelo_requires_registry_definition(self) -> None:
        original_draft = _draft(
            # A real AEAT code the calculation registry deliberately does not carry.
            "993",
            Period.from_year_and_code(2024, "0A"),
            {_UNREGISTERED_M993_SOURCE_CASILLA: Decimal("8400.00")},
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-998")

        with pytest.raises(ModeloBuilderError, match=r"^application\.filing\.runtime\.errors\.modelo_not_in_registry$"):
            build_complementaria(
                original,
                {_UNREGISTERED_M993_EJERCICIO_CASILLA: 2024},
                schema_provider=_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()
