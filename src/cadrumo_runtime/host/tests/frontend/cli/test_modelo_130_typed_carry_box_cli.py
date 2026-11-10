"""CLI and worker reproduction: a Modelo 130 box typed over an unanswered carry calculates.

Box 05 carries the earlier quarters' pagos fraccionados from the Modelo 130
returns filed for them. A profile with none filed leaves that carry unanswered,
and the filer types box 05 instead. ``aeat app modelo work calculate`` runs the
calculation in the profile worker and publishes its result; the JSON carries the
typed figure in box 05 and names no unanswered binding for it, because a box
with a value is not a gap.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from cadrumo.application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.operation_shared import MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_create_operation import MODELO_WORK_CREATE_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_fact_strings
from cadrumo.application.user_profile.tests.profile_values import complete_profile_facts
from cadrumo.core.time.clock import today_madrid
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import (
    published_selected_revision_id,
    published_supported_filing_years,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from .native_api_cli_support import native_api_cli_session, operation_lifecycle_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

# A quarter after the first, so the prior-quarter carry into box 05 has quarters to read.
_PERIOD = "3T"
_CARRY_BOX = "05"
_TYPED_CARRY = Decimal("150.00")

_OPERATIONS = frozenset(
    {
        MODELO_WORK_CREATE_OPERATION_DEFINITION_ID,
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    }
)


def _filing_year() -> int:
    """The latest supported filing year that has begun, read from the registry envelope."""
    supported = published_supported_filing_years()
    assert supported is not None
    return max(year for year in supported.years if year <= today_madrid().year)


def _prepare_profile(profile_id: UUID, root: Path, authority_operation: PinnedAuthorityOperation) -> None:
    """Complete the canonical natural-person taxpayer, who has filed no Modelo 130 this ejercicio."""
    facts = complete_profile_facts(
        authority_operation.profile_schema(),
        tuple(UserProfileFact(path=path, value=value) for path, value in persona_fact_strings().items()),
    )
    populated = upsert_test_profile_facts(profile_id, facts, root=root)
    with bound_test_profile_record(profile_id, root=root) as repository:
        ready = repository.complete_setup(
            profile_id,
            expected_revision=populated.record_revision,
            expected_content_digest=populated.content_digest,
        )
    assert ready.setup_state is ProfileSetupState.COMPLETE


def test_m130_cli_calculate_publishes_a_box_typed_over_an_unanswered_carry(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
    run_cadrumo_cli,
) -> None:
    filing_year = _filing_year()
    with native_api_cli_session(
        tmp_path,
        scope_for_destination=operation_lifecycle_scope(_OPERATIONS),
        prepare_profile=lambda profile_id, root: _prepare_profile(profile_id, root, authority_operation),
        invoke_cli=run_cadrumo_cli,
    ) as session:
        created = session.invoke_password(
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", str(filing_year), "--period", _PERIOD,
            "--revision", published_selected_revision_id("130", filing_year=filing_year, period=_PERIOD),
        )  # fmt: skip
        assert created.exit_code == 0, f"{created.output}\n{session.runtime_failure_observations!r}"
        work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
        assert isinstance(work_unit_id, str) and work_unit_id, created.output
        result = session.invoke_password(
            "app", "modelo", "work", "calculate", work_unit_id,
            "--casilla", f"{_CARRY_BOX}={_TYPED_CARRY}",
            "--casilla", "06=0.00",
            "--binding", "irpf.previous_year_economic_activity_net_income=13000",
            "--binding", "modelo-130-resultados-negativos-anteriores=0",
        )  # fmt: skip
        assert result.exit_code == 0, f"{result.output}\n{session.runtime_failure_observations!r}"

    payload = unwrap_schema_envelope(result.output)
    assert Decimal(payload["casilla_values"][_CARRY_BOX]) == _TYPED_CARRY
    named_boxes = {row["casilla_id"] for row in payload["unresolved_bindings"]} | {
        row["casilla_id"] for row in payload["unresolved_casillas"]
    }
    assert _CARRY_BOX not in named_boxes
    # Whatever is named has no value in the result.
    assert not (named_boxes & set(payload["casilla_values"]))
