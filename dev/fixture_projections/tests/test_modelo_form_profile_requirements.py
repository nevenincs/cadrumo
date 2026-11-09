"""The scenario forms ask for the profile facts their declaration still needs, as the window's read does.

The envelope producer reads every form through the workbench read; a form whose
declaration the readiness gate would refuse for an unanswered profile fact names
that fact among its profile requirements, so the to-do rail the scenarios show
is the one an operator sees.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from cadrumo.core.i18n.render import tr
from cadrumo.domain.user_profile.labels import profile_field_label_key

from ...paths import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_PRODUCER = REPO_ROOT / "native" / "desktop" / "frontend" / "scripts" / "modelo_fixtures.py"
#: The schedule condition a quarterly Modelo 303 cannot be calculated without (LIVA art. 121, RIVA art. 71).
_SCHEDULE_FACT = "censo.large_company"


@pytest.fixture
def producer() -> ModuleType:
    """A fresh load of the producer, so no name minted by one test reaches another."""
    spec = importlib.util.spec_from_file_location("modelo_fixtures_under_test", _PRODUCER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def _recorded_profile_requirements(producer: ModuleType, tmp_path: Path, *, unanswered: bool) -> list[str]:
    """Record the persona's first-quarter Modelo 303 form, its schedule fact taken back first where asked."""
    from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
    from cadrumo.core.time.clock import frozen_clock
    from cadrumo.domain.user_profile.values import UserProfileFact
    from cadrumo.entrypoints.tests.persona_materialisation import load_profile_record

    directory = tmp_path / "envelopes"
    directory.mkdir(parents=True)
    with (
        frozen_clock(producer.scenario_as_of()),
        producer._persona_profile(tmp_path / "profile", producer.ACTIVITY_PERSONA) as persona,
    ):
        # Created while the profile still answers the schedule, which the creation itself requires.
        work = producer._declaration(persona, "303", producer.declarations_year(), "1T")
        if unanswered:
            world = persona.world
            apply_profile_fact_changes(
                profile_id=str(world.profile_id),
                changes=(UserProfileFact(path=_SCHEDULE_FACT, value=None),),
                door=ProfileFactWriteDoor.MANAGER_FIELD,
                expected_record=load_profile_record(world),
                profile_decode_context=world.operation.profile_decode_context(),
            )
        producer._write_form(directory, work, "modelo-303-1T")
    form = json.loads((directory / "modelo-303-1T-en.json").read_text("utf-8"))
    return list(form["profile_requirements"])


def test_a_form_whose_schedule_fact_is_unanswered_asks_for_it(producer: ModuleType, tmp_path: Path) -> None:
    answered = _recorded_profile_requirements(producer, tmp_path / "answered", unanswered=False)
    unanswered = _recorded_profile_requirements(producer, tmp_path / "unanswered", unanswered=True)

    # ANTI-VACUITY: the persona answers the schedule, so its own form asks for nothing more.
    assert answered == []
    # Taking the answer back leaves exactly one more requirement: the schedule condition, by its catalogue label.
    section, field = _SCHEDULE_FACT.split(".")
    assert unanswered == [tr(profile_field_label_key(section, field), locale="en")]
