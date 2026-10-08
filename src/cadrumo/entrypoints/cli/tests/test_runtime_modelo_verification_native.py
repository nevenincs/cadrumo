"""Installed modelo verify/file commands use the exact native profile worker."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_cli_profile
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.modelo.operation_definitions import (
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from cadrumo.application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
)
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.core.config import load_settings
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.tests.cli_envelope import require_schema_envelope, unwrap_envelope_notices

from ..config.tests.isolated_storage_fixture import native_profile_view_server
from ._modelo_work_ux_support import _create_m130_work_unit, operator_profile_facts
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import native_api_cli_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_LABEL = "Native modelo operator"


def _protected(*args: str):
    secret = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    result = invoke_cached_cli(
        ("--format", "json", "--profile", _LABEL, "--profile-secrets-stdin", "app", "modelo", "work", *args),
        input=json.dumps({"profile_passphrase": secret}),
    )
    if secret in result.output:
        pytest.fail("profile credential appeared in CLI output", pytrace=False)
    return result


def test_native_cli_verify_and_file_preserve_settled_results_and_noop_notices(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        register_cli_profile(
            label=_LABEL,
            facts=operator_profile_facts(activity_start_date="2025-10-01"),
            log_in=False,
        )
        work_unit_id = _create_m130_work_unit(period="4T")
        close_active_bucket_session()

        with native_profile_view_server(root):
            calculated = _protected(
                "calculate",
                work_unit_id,
                "--casilla",
                "05=0.00",
                "--casilla",
                "06=0.00",
                "--binding",
                "irpf.previous_year_economic_activity_net_income=13000",
                "--binding",
                "modelo-130-resultados-negativos-anteriores=0",
            )
            assert calculated.exit_code == 0, calculated.output
            calculation_revision_id = require_schema_envelope(calculated.output)["calculation_revision_id"]
            verified = _protected("verify", work_unit_id)
            assert verified.exit_code == 0, verified.output
            report = require_schema_envelope(verified.output)
            assert report["calculation_revision_id"] == calculation_revision_id
            assert report["granted_verificado_completo"] is True
            report_id = report["verification_report_id"]

            repeated_verify = _protected("verify", work_unit_id)
            assert repeated_verify.exit_code == 0, repeated_verify.output
            assert require_schema_envelope(repeated_verify.output)["verification_report_id"] == report_id
            assert "modelo.work.verify.idempotent_noop" in {
                notice["code"] for notice in unwrap_envelope_notices(repeated_verify.output)
            }

            filed = _protected("file", work_unit_id)
            assert filed.exit_code == 0, filed.output
            filing = require_schema_envelope(filed.output)
            assert filing["calculation_revision_id"] == calculation_revision_id
            assert filing["work_unit_id"] == work_unit_id
            assert filing["filing_record_id"]
            assert "aeat_register" not in filing or filing["aeat_register"] is None

            repeated_file = _protected("file", work_unit_id, "--select", "filed")
            assert repeated_file.exit_code == 0, repeated_file.output
            assert require_schema_envelope(repeated_file.output)["filing_record_id"] == filing["filing_record_id"]
            assert "modelo.work.file.idempotent_noop" in {
                notice["code"] for notice in unwrap_envelope_notices(repeated_file.output)
            }


def test_native_cli_api_key_obeys_exact_enrolled_modelo_scope(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    def prepare_profile(profile_id: UUID, root: Path) -> str:
        facts = complete_profile_facts(
            authority_operation.profile_schema(),
            facts=tuple(
                UserProfileFact(path=path, value=value)
                for path, value in operator_profile_facts(activity_start_date="2025-10-01").items()
            ),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE
        return _create_m130_work_unit(period="4T")

    def scope_for_destination(client_id: UUID) -> AccessScope:
        scope = AccessScope(
            operations=frozenset(
                (
                    MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
                    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
                    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
                )
            ),
            actions=frozenset(
                (
                    AccessAction.SUBMIT,
                    AccessAction.START,
                    AccessAction.RESUME,
                    AccessAction.COMMIT,
                    AccessAction.OBSERVE,
                    AccessAction.RESULT,
                )
            ),
            disclosures=frozenset(
                (
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    *(
                        DisclosurePermission(
                            destination_id=client_id,
                            projection_id=definition_id + ".result",
                            category=DisclosureCategory.TAX_VALUES,
                        )
                        for definition_id in (
                            MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
                            MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
                            MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
                        )
                    ),
                )
            ),
            periods=frozenset((Period.from_year_and_code(2025, "4T"),)),
            allow_period_independent=False,
            allow_delegation=False,
        )
        assert MODELO_WORK_REVISION_OPERATION_DEFINITION_ID in scope.operations
        assert MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID not in scope.operations
        return scope

    with native_api_cli_session(
        tmp_path,
        scope_for_destination=scope_for_destination,
        prepare_profile=prepare_profile,
    ) as api:
        work_unit_id = api.prepared
        calculated = api.invoke_password(
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--casilla",
            "05=0.00",
            "--casilla",
            "06=0.00",
            "--binding",
            "irpf.previous_year_economic_activity_net_income=13000",
            "--binding",
            "modelo-130-resultados-negativos-anteriores=0",
        )
        assert calculated.exit_code == 0, calculated.output
        calculation_revision_id = require_schema_envelope(calculated.output)["calculation_revision_id"]

        api_revision = api.invoke_api_key("app", "modelo", "work", "revision", calculation_revision_id)
        assert api_revision.exit_code != 0
        assert "casilla_values" not in api_revision.output
        assert "observations" not in api_revision.output

        human_revision = api.invoke_password("app", "modelo", "work", "revision", calculation_revision_id)
        assert human_revision.exit_code == 0, human_revision.output
        calculated_payload = require_schema_envelope(calculated.output)
        revision_payload = require_schema_envelope(human_revision.output)
        assert revision_payload["calculation_revision_id"] == calculation_revision_id
        assert revision_payload["work_unit_id"] == work_unit_id
        assert revision_payload["casilla_values"] == calculated_payload["casilla_values"]
        assert revision_payload["observations"] == calculated_payload["observations"]
        observation_07 = next(row for row in revision_payload["observations"] if row["casilla_id"] == "07")
        assert observation_07["formula_id"] == "modelo-130-resultado-apartado-i"
        assert observation_07["op"] == "subtract"
        assert observation_07["operand_refs"] == ["04", "05", "06"]
        assert len(observation_07["operand_values"]) == 3

        verbose_revision = api.invoke_password(
            "app",
            "modelo",
            "work",
            "revision",
            calculation_revision_id,
            "--verbose",
            output_format="text",
        )
        assert verbose_revision.exit_code == 0, verbose_revision.output
        trace_line = next(
            line for line in verbose_revision.output.splitlines() if line.lstrip().startswith("trace\t07\t")
        )
        assert "op=subtract" in trace_line
        assert "formula_id=modelo-130-resultado-apartado-i" in trace_line
        assert f"operand_refs={','.join(observation_07['operand_refs'])}" in trace_line
        assert f"operand_values={','.join(observation_07['operand_values'])}" in trace_line

        verified = api.invoke_api_key("app", "modelo", "work", "verify", work_unit_id)
        assert verified.exit_code == 0, verified.output
        result = require_schema_envelope(verified.output)
        assert result["calculation_revision_id"] == calculation_revision_id
        assert result["granted_verificado_completo"] is True
        repeated = api.invoke_api_key("app", "modelo", "work", "verify", work_unit_id)
        assert repeated.exit_code == 0, repeated.output
        assert require_schema_envelope(repeated.output)["verification_report_id"] == result["verification_report_id"]
        assert "modelo.work.verify.idempotent_noop" in {
            notice["code"] for notice in unwrap_envelope_notices(repeated.output)
        }
        foreign = api.invoke_api_key("app", "modelo", "work", "verify", work_unit_id, "--bucket-id", str(uuid4()))
        assert foreign.exit_code != 0
