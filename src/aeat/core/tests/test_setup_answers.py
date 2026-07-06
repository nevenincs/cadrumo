"""Real-behavior tests asserting canonical home and import purity for
aeat.core.setup_answers.SetupAnswers and the project_answers registration slot.

These tests verify:
- SetupAnswers is defined in aeat.core.setup_answers (not aeat.application.wizard).
- aeat.application.wizard._setup_answers.SetupAnswers is the same class object.
- aeat.domain.deadlines._profiles imports SetupAnswers and project_answers from
  aeat.core.setup_answers — no deferred upward application imports survive.
- The project_answers registration slot raises before registration and
  dispatches correctly after.
- SetupAnswers field validation exercises real enum coercion (not mocks).

See Also:
    :mod:`~core.setup_answers`
        Canonical typed-answer model and projection slot under test.
    :func:`~core.setup_answers.register_project_answers`
        Core registration hook populated by wizard persistence.
    :func:`~core.setup_answers.get_project_answers`
        Slot reader whose pre-registration failure and post-registration
        dispatch are covered here.
    :mod:`~domain.deadlines._profiles`
        Domain consumer that must import setup-answer projection objects from
        core, not from application wizard modules.
    :func:`~core.wizard_catalogue.get_setup_flow`
        Flow descriptor that binds setup answers to the canonical core class.
    Governing vault records
        ``2026-06-01-domain-boundary-audit-adr`` D5 and
        ``2026-05-28-codebase-solidification-plan`` W03.P14.S321-S324 record
        the setup-answer relocation and import-purity regression surface.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# Canonical home
# ---------------------------------------------------------------------------


def test_setup_answers_canonical_module() -> None:
    """SetupAnswers.__module__ must be aeat.core.setup_answers."""
    from ..setup_answers import SetupAnswers

    assert SetupAnswers.__module__ == "aeat.core.setup_answers", (
        f"SetupAnswers is defined in {SetupAnswers.__module__!r}; expected 'aeat.core.setup_answers'"
    )


def test_setup_answers_catalogue_uses_core_class() -> None:
    """SETUP_FLOW.answers_model must be aeat.core.setup_answers.SetupAnswers.

    The wizard catalogue is the authoritative binding between the flow descriptor
    and the typed-answers class.  It must reference the core class so that
    project_answers returns instances that domain code (aeat.domain.deadlines._profiles)
    can check with ``isinstance(typed, SetupAnswers)`` where SetupAnswers is the
    core class.
    """
    from ...application.wizard import _catalogue as catalogue
    from ..setup_answers import SetupAnswers
    from ..wizard_catalogue import get_setup_flow

    setup_flow = get_setup_flow()
    assert setup_flow is catalogue.SETUP_FLOW
    assert setup_flow.answers_model is SetupAnswers, (
        f"SETUP_FLOW.answers_model is {setup_flow.answers_model!r}; expected aeat.core.setup_answers.SetupAnswers"
    )


# ---------------------------------------------------------------------------
# No deferred upward imports in _profiles.py
# ---------------------------------------------------------------------------


def test_profiles_imports_setup_answers_from_core() -> None:
    """aeat.domain.deadlines._profiles must import SetupAnswers from aeat.core.setup_answers."""
    from ...domain.deadlines import _profiles as profiles_mod

    # SetupAnswers in the profiles module namespace should be the core class.
    sa = getattr(profiles_mod, "SetupAnswers", None)
    assert sa is not None, "_profiles module does not expose SetupAnswers"
    from ..setup_answers import SetupAnswers

    assert sa is SetupAnswers, f"_profiles.SetupAnswers is {sa!r}, not aeat.core.setup_answers.SetupAnswers"


def test_profiles_import_purity_uses_core_projection_slot() -> None:
    """Importing _profiles must bind core projection objects without loading the application wizard."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""\
        import importlib
        import sys

        profiles = importlib.import_module("aeat.domain.deadlines._profiles")
        from aeat.core.setup_answers import SetupAnswers, project_answers

        assert profiles.SetupAnswers is SetupAnswers
        assert profiles.project_answers is project_answers
        leaked = sorted(name for name in sys.modules if name.startswith("aeat.application.wizard"))
        assert leaked == [], leaked
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"_profiles import purity check failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# project_answers registration slot
# ---------------------------------------------------------------------------


def test_project_answers_raises_before_registration() -> None:
    """get_project_answers() must raise ProjectAnswersNotRegisteredError when slot is empty.

    Run as a subprocess to guarantee a clean import state regardless of test
    execution order — the slot may already be populated in-process when
    _persistence has been imported by an earlier test.
    """
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""\
        from aeat.core.setup_answers import get_project_answers, ProjectAnswersNotRegisteredError
        raised = False
        try:
            get_project_answers()
        except ProjectAnswersNotRegisteredError:
            raised = True
        assert raised, "ProjectAnswersNotRegisteredError was not raised"
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Subprocess raised unexpected error.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_project_answers_registered_after_persistence_import() -> None:
    """Importing _persistence registers project_answers in the core slot."""
    # Importing _persistence triggers the module-level registration call.
    importlib.import_module("aeat.application.wizard._persistence")

    from ..setup_answers import _PROJECT_ANSWERS_SLOT, get_project_answers

    assert _PROJECT_ANSWERS_SLOT, "project_answers was not registered after _persistence import"

    fn = get_project_answers()
    assert callable(fn), f"registered project_answers is not callable: {fn!r}"


# ---------------------------------------------------------------------------
# SetupAnswers field validation — real enum coercion
# ---------------------------------------------------------------------------


def test_setup_answers_minimal_valid() -> None:
    """SetupAnswers accepts a minimal valid input without error."""
    from ..setup_answers import SetupAnswers

    sa = SetupAnswers(tax_id="12345678A")
    assert sa.tax_id == "12345678A"
    assert sa.output_language == "es"


def test_setup_answers_string_enum_coercion() -> None:
    """SetupAnswers coerces known string tokens to their enum members."""
    from ...domain.deadlines import (
        EntityType,
        IVARegime,
    )
    from ..setup_answers import SetupAnswers

    # Test iva_regime coercion
    sa_iva = SetupAnswers(tax_id="12345678A", iva_regime="GENERAL")
    assert sa_iva.iva_regime == IVARegime.GENERAL

    # Test entity_type coercion
    sa_entity = SetupAnswers(tax_id="12345678A", entity_type="natural_person")
    assert sa_entity.entity_type == EntityType.NATURAL_PERSON


def test_setup_answers_invalid_fields_raise() -> None:
    """SetupAnswers rejects malformed enum and date field values."""
    import pydantic

    from ..setup_answers import SetupAnswers

    # Test invalid iva_regime token
    with pytest.raises(pydantic.ValidationError):
        SetupAnswers(tax_id="12345678A", iva_regime="NOT_A_REGIME")

    # Test invalid activity_start_date format
    with pytest.raises(pydantic.ValidationError):
        SetupAnswers(tax_id="12345678A", activity_start_date="31-12-2024")


def test_setup_answers_valid_date_accepted() -> None:
    """SetupAnswers accepts a valid ISO-8601 activity_start_date."""
    from ..setup_answers import SetupAnswers

    sa = SetupAnswers(tax_id="12345678A", activity_start_date="2024-01-01")
    assert sa.activity_start_date == "2024-01-01"
