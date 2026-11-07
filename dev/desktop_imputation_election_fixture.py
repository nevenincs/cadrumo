"""Generate the desktop's imputation election fixture from the real profile operations.

Each state starts from the ``autonomo-fontanero`` persona of the canonical
catalogue, replayed through the production profile operations, and is read for
the persona's fiscal year. Its elections are then stated per ejercicio through
the profile fact writer, the way the setup flow dates them, and read through
``read_imputation_election`` in every language. The refusals are the registered
error details a refused change settles with, and the stored profile is moved by
``apply_imputation_election`` for the change a story makes. No stored user
profile is read; run after publishing a changed profile schema, wizard wording
or persona.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter

from dev.fixture_projections.location import family_directory, scratch_tree
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

if TYPE_CHECKING:
    from cadrumo.domain.user_profile.values import UserProfileFact
    from cadrumo.entrypoints.tests.persona_materialisation import MaterialisedPersona

LANGUAGES = ("en", "es", "ca", "hu")
_OBJECT = TypeAdapter(dict[str, object])
PERSONA_ID = "autonomo-fontanero"
"""The catalogue persona whose elections every state starts from: devengo for its fiscal year."""
PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_CRITERION = "irpf.activity_income_imputation_criterion"
_ACCOUNTING = "irpf.codigo_comercio_accounting"
#: What each state states over the persona's own elections: path, ejercicio as years before the fiscal year read,
#: and token. ``None`` takes the persona's statement for that ejercicio back.
STATES: dict[str, tuple[tuple[str, int, str | None], ...]] = {
    # An earlier ejercicio is stated and the year read is not: nothing is read as devengo.
    "undeclared": ((_CRITERION, 0, None), (_ACCOUNTING, 0, None), (_CRITERION, 1, "devengo")),
    "devengo": ((_CRITERION, 1, "devengo"),),
    "cobros_y_pagos": (
        (_CRITERION, 2, "cobros_y_pagos"),
        (_CRITERION, 1, "cobros_y_pagos"),
        (_CRITERION, 0, "cobros_y_pagos"),
        (_ACCOUNTING, 0, "false"),
    ),
    # Two statements for the year read that disagree.
    "contradictory": ((_CRITERION, 0, "devengo"), (_CRITERION, 0, "cobros_y_pagos")),
}


def _facts(statements: tuple[tuple[str, int, str | None], ...], tax_year: int) -> tuple[UserProfileFact, ...]:
    from cadrumo.domain.user_profile.values import UserProfileFact

    def value(path: str, stated: str | None) -> object:
        return stated == "true" if path == _ACCOUNTING and stated is not None else stated

    return tuple(
        UserProfileFact(
            path=path,
            value=value(path, stated),
            valid_from=date(tax_year - before, 1, 1),
            valid_to=date(tax_year - before, 12, 31),
        )
        for path, before, stated in statements
    )


def _tax_year(persona: MaterialisedPersona) -> int:
    return persona.persona.fiscal_year.resolve(persona.world.envelope)


def _state(persona: MaterialisedPersona, statements: tuple[tuple[str, int, str | None], ...]) -> None:
    """State ``statements`` over the persona's elections through the profile fact writer."""
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.entrypoints.tests.persona_materialisation import load_profile_record

    apply_profile_fact_changes(
        profile_id=str(persona.world.profile_id),
        changes=_facts(statements, _tax_year(persona)),
        door=ProfileFactWriteDoor.MANAGER_IMPUTATION_ELECTION,
        expected_record=load_profile_record(persona.world),
        profile_decode_context=persona.world.operation.profile_decode_context(),
    )


def _read(persona: MaterialisedPersona, language: str) -> dict[str, object]:
    from cadrumo.application.user_profile.imputation_election_contracts import (
        ProfileImputationElectionReadProjection,
        ProfileImputationElectionReadRequest,
    )
    from cadrumo.application.user_profile.imputation_election_service import read_imputation_election
    from cadrumo.core.external_constants import OutputLanguage

    request = ProfileImputationElectionReadRequest(
        profile_id=persona.world.profile_id, tax_year=_tax_year(persona), output_language=OutputLanguage(language)
    )
    result = read_imputation_election(request, authority_operation=persona.world.operation)
    projection = ProfileImputationElectionReadProjection.model_validate(result.model_dump(mode="python"))
    return _OBJECT.validate_json(projection.model_dump_json())


def _normalised(read: dict[str, object], state: str) -> dict[str, object]:
    """Make the revision witness the same on every run; the words and statements stay as read."""
    read["profile_id"] = PROFILE_ID
    read["content_digest"] = hashlib.sha256(f"imputation-election-{state}".encode()).hexdigest()
    return read


def _refusal(persona: MaterialisedPersona, language: str, name: str) -> dict[str, object]:
    """Settle one refused change as the registered executor does, and keep its recorded detail."""
    from cadrumo.application.operations.error_detail import build_operation_error_detail
    from cadrumo.application.user_profile.imputation_election_contracts import ProfileImputationElectionSetRequest
    from cadrumo.application.user_profile.imputation_election_service import apply_imputation_election
    from cadrumo.core.config import override_settings
    from cadrumo.core.errors.hierarchy import CadrumoError
    from cadrumo.entrypoints.tests.persona_materialisation import load_profile_record

    current = load_profile_record(persona.world)
    answers = {"criterion": "monthly"} if name == "unknown_choice" else {"criterion": "devengo"}
    stale = current.record_revision + 1 if name == "stale" else current.record_revision
    request = ProfileImputationElectionSetRequest(
        profile_id=persona.world.profile_id,
        expected_revision=stale,
        expected_content_digest=current.content_digest,
        tax_year=_tax_year(persona),
        **answers,
    )
    try:
        with override_settings(cadrumo_output_language=language):
            apply_imputation_election(request, authority_operation=persona.world.operation)
    except CadrumoError as error:
        with override_settings(cadrumo_output_language=language):
            detail = build_operation_error_detail(error)
        if detail is None:
            raise SystemExit(f"{name} records no error detail") from error
        return _OBJECT.validate_json(detail.model_dump_json())
    raise SystemExit(f"{name} was not refused")


@contextmanager
def _persona(root: Path, name: str) -> Generator[MaterialisedPersona]:
    """A copy of the persona's replayed profile, for one state to state its elections into."""
    from cadrumo.entrypoints.tests.persona_materialisation import ReplayScope, materialised_persona

    with materialised_persona(PERSONA_ID, root / name, ReplayScope.PROFILE, reuse=True) as persona:
        yield persona


def render_fixture(root: Path) -> str:
    """Read every state and every refusal through the application, in every language."""
    from cadrumo.core.config import override_settings
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition

    reads: dict[str, dict[str, object]] = {}
    refusals: dict[str, dict[str, object]] = {}
    with profile_adapter_composition(), bundled_indexed_authority().operation():
        for state, statements in STATES.items():
            with _persona(root, state) as persona:
                _state(persona, statements)
                reads[state] = {}
                for language in LANGUAGES:
                    with override_settings(cadrumo_output_language=language):
                        reads[state][language] = _normalised(_read(persona, language), state)
        with _persona(root, "refusals") as persona:
            _state(persona, STATES["undeclared"])
            for name in ("unknown_choice", "stale"):
                refusals[name] = {language: _refusal(persona, language, name) for language in LANGUAGES}
    return dump_json({"reads": reads, "refusals": refusals})


def main() -> None:
    """Write, verify or redirect the synthetic browser fixture."""
    arguments = producer_arguments(__doc__)
    target = family_directory("desktop-imputation-election") / "imputationElection.json"
    with scratch_tree() as tmp:
        rendered = render_fixture(Path(tmp))
    emit({target: rendered}, arguments, remedy="uv run --no-sync python -m dev.desktop_imputation_election_fixture")


if __name__ == "__main__":
    main()
