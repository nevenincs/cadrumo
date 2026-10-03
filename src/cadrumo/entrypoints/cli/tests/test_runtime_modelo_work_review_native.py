"""Native review CLI matches the canonical compact encrypted projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.work_review import build_modelo_work_review
from ....application.modelo.work_review_contracts import MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.config import override_settings
from ....core.period import Period
from ....core.redaction.rules import redact_structured_for_cli_output
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_error_document, unwrap_cli_result
from ...adapter_composition import build_modelo_history_ports
from ...tests import modelo_operation_test_support
from .._modelo_payloads import WorkReviewPayload, WorkReviewResult
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import native_api_cli_session
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_LABEL = "Native modelo review operator"


def _facts() -> dict[str, str]:
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": "Review",
        "activities.description": "consulting",
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }


def _invoke(fixture: NativeCliProfileFixture, *arguments: str) -> Result:
    assert fixture.label is not None
    with override_settings(cadrumo_cli_reveal_identifiers=False):
        result = invoke_cached_cli(
            (
                "--format",
                "json",
                "--profile",
                fixture.label,
                "--profile-secrets-stdin",
                "app",
                "modelo",
                "work",
                "review",
                *arguments,
            ),
            input=json.dumps({"profile_passphrase": fixture.passphrase}),
        )
    assert fixture.passphrase not in result.output
    return result


def test_native_review_matches_pinned_canonical_compact_result(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    with native_cli_profile_scope(tmp_path) as fixture:
        fixture.register(label=_LABEL, facts=_facts())
        bucket_id = resolve_login_target(_LABEL).bucket_id
        unit = modelo_operation_test_support.seeded_modelo_work_unit(UUID(bucket_id), operation=authority_operation)
        close_active_bucket_session()

        observed = _invoke(fixture, unit.work_unit_id)
        assert observed.exit_code == 0, observed.output
        payload = unwrap_cli_result(observed)

        close_active_bucket_session()
        login = login_profile(
            name=_LABEL,
            passphrase_callback=lambda: fixture.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        assert login.bucket_id == bucket_id
        try:
            ports = build_modelo_history_ports(bucket_id=bucket_id, operation=authority_operation)
            review = build_modelo_work_review(
                unit.bucket_id,
                unit.modelo,
                unit.filing_year,
                unit.period,
                operation=authority_operation,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
                verification_repository=ports.verification_repository,
            )
        finally:
            close_active_bucket_session()
        expected = WorkReviewResult(review=WorkReviewPayload.from_review(review))
        expected_payload = cast(
            "dict[str, object]",
            redact_structured_for_cli_output(expected.model_dump(mode="json"), reveal_identifiers=False),
        )
        assert payload == expected_payload
        assert expected.review.casilla_count == len(review.casillas)
        assert expected.review.row_source_fingerprint_count == len(review.row_source_fingerprints)

        foreign = _invoke(fixture, unit.work_unit_id, "--bucket-id", str(uuid4()))
        assert foreign.exit_code == 2, foreign.output
        error = require_error_document(foreign.output)["error"]
        assert error["context"] == {"reason": "profile_mismatch"}


def _finite_scope(client_id: UUID, *, period: Period) -> AccessScope:
    return AccessScope(
        operations=frozenset(
            {MODELO_WORK_METADATA_OPERATION_DEFINITION_ID, MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID}
        ),
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in (
                        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
                        MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
                    )
                ),
            }
        ),
        periods=frozenset({period}),
        allow_period_independent=False,
        allow_delegation=False,
    )


def test_native_review_denies_out_of_scope_period(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    def prepare(profile_id: UUID, _root: Path) -> str:
        unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=authority_operation)
        return unit.work_unit_id

    with native_api_cli_session(
        tmp_path / "adjacent",
        scope_for_destination=lambda client_id: _finite_scope(client_id, period=Period.from_year_and_code(2025, "2T")),
        prepare_profile=prepare,
    ) as session:
        refused = session.invoke_credential_reference("app", "modelo", "work", "review", session.prepared)
        assert refused.exit_code == 2, refused.output
        error = require_error_document(refused.output)["error"]
        assert error["context"] == {"reason": "period_denied"}
        assert "casilla_count" not in refused.output

    with native_api_cli_session(
        tmp_path / "matching",
        scope_for_destination=lambda client_id: _finite_scope(client_id, period=Period.from_year_and_code(2025, "1T")),
        prepare_profile=prepare,
    ) as session:
        accepted = session.invoke_credential_reference("app", "modelo", "work", "review", session.prepared)
        assert accepted.exit_code == 0, accepted.output
        result = unwrap_cli_result(accepted)
        assert result["operation"] == MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID
        review = cast("dict[str, object]", result["review"])
        assert review["work_unit_id"] == session.prepared
