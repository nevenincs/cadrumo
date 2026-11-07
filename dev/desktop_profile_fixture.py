"""Generate the desktop demo from the real profile schema and overview projection.

The profile is the ``asalariada-familia`` persona of the canonical catalogue,
replayed through the production profile operations into a throwaway profile,
and projected by the overview the installed runtime serves. No stored user
profile is read. Run after publishing a changed profile schema or persona.
"""

from __future__ import annotations

from pathlib import Path

from dev.fixture_projections.location import family_directory, scratch_tree
from dev.fixture_projections.producer_output import emit, producer_arguments
from dev.prettier_json import dump_json

PERSONA_ID = "asalariada-familia"
"""The catalogue persona whose profile the demo shows."""
PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
"""The profile id the browser fixtures name, in place of the id a registration mints afresh."""
LANGUAGES = ("en", "es", "ca", "hu")
UNANSWERED = ("identity.tax_id", "tax_residence.jurisdiction_scope")
"""The required answers the demo's setup has not reached yet."""


def render_fixture(root: Path) -> str:
    """Project the persona's replayed profile through the same schema walk as the installed runtime."""
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.application.user_profile.overview import build_profile_overview
    from cadrumo.application.wizard.catalogue import build_setup_flow
    from cadrumo.core.config import override_settings
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.domain.user_profile.values import UserProfileFact
    from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
    from cadrumo.entrypoints.tests.persona_materialisation import (
        ReplayScope,
        load_profile_record,
        materialised_persona,
    )

    fixtures = {}
    with (
        profile_adapter_composition(),
        bundled_indexed_authority().operation(),
        materialised_persona(PERSONA_ID, root, ReplayScope.HOUSEHOLD, complete_setup=False) as persona,
    ):
        operation = persona.world.operation
        # The demo is a setup in progress: the answers a new profile has not given yet are taken back through the
        # manager's field door, so the page shows what the taxpayer still has to state.
        record = apply_profile_fact_changes(
            profile_id=str(persona.world.profile_id),
            changes=tuple(UserProfileFact(path=path, value=None) for path in UNANSWERED),
            door=ProfileFactWriteDoor.MANAGER_FIELD,
            expected_record=load_profile_record(persona.world),
            profile_decode_context=operation.profile_decode_context(),
        )
        schema = operation.profile_decode_context().schema
        flow = build_setup_flow(operation)
        for language in LANGUAGES:
            with override_settings(cadrumo_output_language=language):
                data = build_profile_overview(record, schema=schema, flow=flow).model_dump(mode="json")
            data.pop("label")
            data.update(profile_id=PROFILE_ID, valid=True, pages=1, content_digest="a" * 64)
            fixtures[language] = data
    return dump_json(fixtures)


def main() -> None:
    """Write, verify or redirect the synthetic browser fixture."""
    arguments = producer_arguments(__doc__)
    target = family_directory("desktop-profile") / "userProfile.json"
    with scratch_tree() as tmp:
        rendered = render_fixture(Path(tmp))
    emit({target: rendered}, arguments, remedy="uv run --no-sync python -m dev.desktop_profile_fixture")


if __name__ == "__main__":
    main()
