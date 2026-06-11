"""Tests for complementaria registry-boundary behaviour."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....domain.filing import (
    ModeloAmendmentError,
    ModeloBuilderError,
    ModeloDraft,
    ModeloValue,
    ModeloValueKind,
)
from ....domain.submission import ModeloDraftStatus, ModeloPresentado, SubmissionAttempt, SubmissionStatus
from .. import (
    build_complementaria,
    build_draft,
    build_runtime_schema_provider,
    load_amendment,
)
from ..testing import ModeloTestProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _persist_original_draft(draft: ModeloDraft) -> None:
    from ....domain.filing import ModeloDraftRepository

    ModeloDraftRepository().save(draft)


def _persisted_amendment_ids() -> tuple[str, ...]:
    from ....domain.filing import ModeloAmendmentRepository

    return ModeloAmendmentRepository().list_amendment_ids()


def _submitted_filing(
    draft: ModeloDraft,
    *,
    submission_id: str = "sub-1",
    justificante_csv: str | None = None,
) -> ModeloPresentado:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id=draft.draft_id,
        modelo=draft.modelo,
        period=draft.period,
        profile_tax_id=draft.profile_tax_id,
        status=SubmissionStatus.PRESENTADA,
        justificante_csv=justificante_csv if justificante_csv is not None else f"CSV-{submission_id}",
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


def _draft(modelo: str, period: Period, casillas: dict[str, Decimal]) -> ModeloDraft:
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=value,
            kind=ModeloValueKind.LITERAL,
            source="input",
        )
        for casilla_id, value in sorted(casillas.items())
    )
    return ModeloDraft(
        draft_id=f"unsupported-{modelo}-{period.registry_token}",
        modelo=modelo,
        period=period,
        profile_tax_id="00000000T",
        status=ModeloDraftStatus.PRESENTADA,
        values=values,
        created_at=now,
        updated_at=now,
        schema_version=f"registry:{modelo}:missing",
    )


def _registry_draft(*, casillas: dict[str, Decimal]) -> ModeloDraft:
    return build_draft(
        modelo="130",
        period=Period.from_year_and_code(2024, "1T"),
        profile=ModeloTestProfile(
            tax_id="00000000T",
            display_name="Complementaria registry test",
        ),
        inputs=casillas,
        schema_provider=build_runtime_schema_provider(),
    )


class TestBuildComplementaria:
    def test_modelo_130_builds_and_persists_complementaria(self) -> None:
        original_draft = _registry_draft(
            casillas={
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "05": Decimal("250"),
                "06": Decimal("100"),
                "08": Decimal("2000"),
                "10": Decimal("10"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
                # Casilla 15 omitted: M130 carry-forward must flow
                # through binding_values via
                # `modelo-130-resultados-negativos-anteriores`, not as
                # a direct casilla input. Same pattern as the M130
                # binding-id fix from #71/#95.
                "16": Decimal("0"),
                "18": Decimal("0"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft)

        amendment = build_complementaria(
            original,
            {
                "01": Decimal("13000"),
                "02": Decimal("3500"),
                "05": Decimal("400"),
                "06": Decimal("0"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
            schema_provider=build_runtime_schema_provider(),
        )

        changed = {change.casilla_code: change for change in amendment.delta}
        assert amendment.original_model == "130"
        assert amendment.amendment_kind.value == "complementaria"
        assert changed["19"].new_value == Decimal("1530.00")
        assert load_amendment(amendment.amendment_id).amendment_id == amendment.amendment_id

    def test_load_amendment_rejects_traversal_id(self) -> None:
        with pytest.raises(ModeloAmendmentError, match="path separators"):
            load_amendment("../escape")

    def test_complementaria_requires_official_justificante_csv(self) -> None:
        original_draft = _registry_draft(
            casillas={
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        )
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, justificante_csv="")

        with pytest.raises(ModeloBuilderError, match="official justificante CSV"):
            build_complementaria(
                original,
                {"01": Decimal("11000")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_complementaria_requires_original_registry_snapshot(self) -> None:
        original_draft = _registry_draft(
            casillas={
                "01": Decimal("10000"),
                "02": Decimal("4000"),
                "irpf.previous_year_economic_activity_net_income": Decimal("13000"),
            },
        ).model_copy(update={"schema_version": "registry:130:wrong-revision"})
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft)

        with pytest.raises(ModeloBuilderError, match="active registry snapshot"):
            build_complementaria(
                original,
                {"01": Decimal("11000")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_unknown_modelo_requires_registry_definition(self) -> None:
        original_draft = _draft("999", Period.from_year_and_code(2024, "2T"), {"69": Decimal("1900.00")})
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-999")

        with pytest.raises(ModeloBuilderError, match="not present in the calculation registry"):
            build_complementaria(
                original,
                {"07": Decimal("11000.00"), "29": Decimal("200.00")},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()

    def test_unknown_annual_modelo_requires_registry_definition(self) -> None:
        original_draft = _draft("998", Period.from_year_and_code(2024, "0A"), {"109": Decimal("8400.00")})
        _persist_original_draft(original_draft)
        original = _submitted_filing(original_draft, submission_id="sub-998")

        with pytest.raises(ModeloBuilderError, match="not present in the calculation registry"):
            build_complementaria(
                original,
                {"01": 2024},
                schema_provider=build_runtime_schema_provider(),
            )
        assert _persisted_amendment_ids() == ()
