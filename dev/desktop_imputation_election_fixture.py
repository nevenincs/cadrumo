"""Generate the desktop's imputation election fixture from the real profile operations.

Each state is a synthetic profile whose facts are stated the way the setup flow
dates them, read through ``read_imputation_election`` in every language. The
refusals are the registered error details a refused change settles with, and the
stored profile is moved by ``apply_imputation_election`` for the change a story
makes. No stored user profile is read; run after publishing a changed profile
schema or wizard wording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import TypeAdapter

from dev.temporary_output import prepare_temp_root

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.user_profile.values import UserProfileFact

LANGUAGES = ("en", "es", "ca", "hu")
#: The ejercicio every state is read for.
TAX_YEAR = 2025
PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_BUCKET_ID = "13000000-0000-4000-8000-000000000731"
_CRITERION = "irpf.activity_income_imputation_criterion"
_ACCOUNTING = "irpf.codigo_comercio_accounting"
#: What each state's profile states: path, ejercicio and token.
STATES: dict[str, tuple[tuple[str, int, str], ...]] = {
    # An earlier ejercicio is stated and 2025 is not: nothing is read as devengo.
    "undeclared": ((_CRITERION, 2024, "devengo"),),
    "devengo": ((_CRITERION, 2024, "devengo"), (_CRITERION, 2025, "devengo")),
    "cobros_y_pagos": (
        (_CRITERION, 2023, "cobros_y_pagos"),
        (_CRITERION, 2024, "cobros_y_pagos"),
        (_CRITERION, 2025, "cobros_y_pagos"),
        (_ACCOUNTING, 2025, "false"),
    ),
    # Two statements for 2025 that disagree.
    "contradictory": ((_CRITERION, 2025, "devengo"), (_CRITERION, 2025, "cobros_y_pagos")),
}


def _json_object(text: str) -> dict[str, object]:
    return TypeAdapter(dict[str, object]).validate_json(text)


def _facts(statements: tuple[tuple[str, int, str], ...]) -> tuple[UserProfileFact, ...]:
    from cadrumo.domain.user_profile.values import UserProfileFact

    return tuple(
        UserProfileFact(
            path=path,
            value=(value == "true") if path == _ACCOUNTING else value,
            valid_from=date(year, 1, 1),
            valid_to=date(year, 12, 31),
        )
        for path, year, value in statements
    )


def _seed(statements: tuple[tuple[str, int, str], ...]) -> None:
    from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
        profile_authority_contexts,
        seed_test_profile_record,
    )
    from cadrumo.application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
    from cadrumo.domain.user_profile.values import ProfileSetupState, create_user_profile_record

    create_context, _ = profile_authority_contexts()
    moment = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
    seed_test_profile_record(
        create_user_profile_record(
            context=create_context,
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(*MODELO_READY_PROFILE_FACTS, *_facts(statements)),
            created_at=moment,
            updated_at=moment,
        )
    )


def _read(operation: PinnedAuthorityOperation, language: str) -> dict[str, object]:
    from cadrumo.application.user_profile.imputation_election_contracts import (
        ProfileImputationElectionReadProjection,
        ProfileImputationElectionReadRequest,
    )
    from cadrumo.application.user_profile.imputation_election_service import read_imputation_election
    from cadrumo.core.external_constants import OutputLanguage

    request = ProfileImputationElectionReadRequest(
        profile_id=UUID(_BUCKET_ID), tax_year=TAX_YEAR, output_language=OutputLanguage(language)
    )
    result = read_imputation_election(request, authority_operation=operation)
    projection = ProfileImputationElectionReadProjection.model_validate(result.model_dump(mode="python"))
    return _json_object(projection.model_dump_json())


def _normalised(read: dict[str, object], state: str) -> dict[str, object]:
    """Make the revision witness the same on every run; the words and statements stay as read."""
    read["profile_id"] = PROFILE_ID
    read["content_digest"] = hashlib.sha256(f"imputation-election-{state}".encode()).hexdigest()
    return read


def _refusal(operation: PinnedAuthorityOperation, language: str, name: str) -> dict[str, object]:
    """Settle one refused change as the registered executor does, and keep its recorded detail."""
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.application.user_profile.imputation_election_contracts import ProfileImputationElectionSetRequest
    from cadrumo.application.user_profile.imputation_election_service import apply_imputation_election
    from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
    from cadrumo.core.config import override_settings
    from cadrumo.core.errors.hierarchy import CadrumoError

    decode = operation.profile_decode_context()
    current = ProfileRecordRepository.for_current_session(_BUCKET_ID, profile_decode_context=decode).load(_BUCKET_ID)
    answers = {"criterion": "monthly"} if name == "unknown_choice" else {"criterion": "devengo"}
    stale = current.record_revision + 1 if name == "stale" else current.record_revision
    request = ProfileImputationElectionSetRequest(
        profile_id=UUID(_BUCKET_ID),
        expected_revision=stale,
        expected_content_digest=current.content_digest,
        tax_year=TAX_YEAR,
        **answers,
    )
    try:
        with override_settings(cadrumo_output_language=language):
            apply_imputation_election(request, authority_operation=operation)
    except CadrumoError as error:
        with override_settings(cadrumo_output_language=language):
            detail = build_operation_error_detail(error)
        if detail is None:
            raise SystemExit(f"{name} records no error detail") from error
        return _json_object(detail.model_dump_json())
    raise SystemExit(f"{name} was not refused")


def render_fixture(root: Path) -> str:
    """Read every state and every refusal through the application, in every language."""
    from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
    from cadrumo.core.config import override_settings
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

    reads: dict[str, dict[str, object]] = {}
    refusals: dict[str, dict[str, object]] = {}
    with (
        profile_adapter_composition(),
        isolated_runtime_profile(tmp_path=root, bucket_id=_BUCKET_ID),
        bundled_indexed_authority().operation() as operation,
    ):
        for state, statements in STATES.items():
            _seed(statements)
            reads[state] = {}
            for language in LANGUAGES:
                with override_settings(cadrumo_output_language=language):
                    reads[state][language] = _normalised(_read(operation, language), state)
        _seed(STATES["undeclared"])
        for name in ("unknown_choice", "stale"):
            refusals[name] = {language: _refusal(operation, language, name) for language in LANGUAGES}
    return json.dumps({"reads": reads, "refusals": refusals}, ensure_ascii=False, indent=2) + "\n"


def _comparable(text: str) -> Mapping[str, object]:
    return _json_object(text)


def main() -> None:
    """Write or verify the checked-in, synthetic browser fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = Path(__file__).resolve().parents[1] / "native/desktop/frontend/src/dev/fixtures/imputationElection.json"
    with tempfile.TemporaryDirectory(dir=prepare_temp_root()) as tmp:
        rendered = render_fixture(Path(tmp))
    if args.check:
        if _comparable(target.read_text(encoding="utf-8")) != _comparable(rendered):
            raise SystemExit(
                "Imputation election demo is stale; run "
                "uv run --no-sync python -m dev.desktop_imputation_election_fixture"
            )
    else:
        target.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
