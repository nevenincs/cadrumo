"""Real-behavior tests asserting canonical home and import purity for
cadrumo.core.setup_answers.SetupAnswers and the project_answers registration slot.

These tests verify:
- SetupAnswers is defined in cadrumo.core.setup_answers (not cadrumo.application.wizard).
- cadrumo.domain.deadlines.profiles projects through the core answer table and
  loads no application wizard module at all.
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
    :mod:`~domain.deadlines.profiles`
        Domain consumer that must import setup-answer projection objects from
        core, not from application wizard modules.
    :func:`~core.wizard_catalogue.get_setup_flow`
        Flow descriptor that binds setup answers to the canonical core class.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from ..directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# Canonical home
# ---------------------------------------------------------------------------


def test_setup_answers_canonical_module() -> None:
    """SetupAnswers.__module__ must be cadrumo.core.setup_answers."""
    from ..setup_answers import SetupAnswers

    assert SetupAnswers.__module__ == "cadrumo.core.setup_answers", (
        f"SetupAnswers is defined in {SetupAnswers.__module__!r}; expected 'cadrumo.core.setup_answers'"
    )


def test_setup_answers_catalogue_uses_core_class() -> None:
    """SETUP_FLOW.answers_model must be cadrumo.core.setup_answers.SetupAnswers.

    The wizard catalogue is the authoritative binding between the flow descriptor
    and the typed-answers class.  It must reference the core class so that
    project_answers returns instances that domain code (cadrumo.domain.deadlines.profiles)
    can check with ``isinstance(typed, SetupAnswers)`` where SetupAnswers is the
    core class.
    """
    from ...application.wizard import catalogue as catalogue
    from ..setup_answers import SetupAnswers
    from ..wizard_catalogue import get_setup_flow

    setup_flow = get_setup_flow()
    assert setup_flow is catalogue.SETUP_FLOW
    assert setup_flow.answers_model is SetupAnswers, (
        f"SETUP_FLOW.answers_model is {setup_flow.answers_model!r}; expected cadrumo.core.setup_answers.SetupAnswers"
    )


def test_profile_registration_error_names_have_distinct_canonical_declarations() -> None:
    """The callback-registration and taxpayer-registration refusals cannot share a class name."""
    source_root = Path(__file__).parents[2]
    declarations: dict[str, set[Path]] = {
        "ProfileRegistrationError": set(),
        "ProjectAnswersRegistrationError": set(),
    }
    for path in scan_directory(source_root, pattern="*.py", recursive=True):
        module = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(module):
            if isinstance(node, ast.ClassDef) and node.name in declarations:
                declarations[node.name].add(path.relative_to(source_root))

    assert declarations["ProfileRegistrationError"] == {Path("application/user_profile/registration.py")}
    assert declarations["ProjectAnswersRegistrationError"] == {Path("core/setup_answers.py")}

    from .. import setup_answers

    assert "ProfileRegistrationError" not in setup_answers.__all__
    assert "ProjectAnswersRegistrationError" in setup_answers.__all__


# ---------------------------------------------------------------------------
# No deferred upward imports in _profiles.py
# ---------------------------------------------------------------------------


def test_profiles_projects_through_the_core_answer_table() -> None:
    """The deadline projection must bind the core projector, not a registered slot.

    The slot existed so the domain could call back into an
    application-registered projector without importing it. The projection
    now reads the core answer table directly, which removes the callback
    rather than merely hiding it, so what this asserts is that the domain
    holds the core function itself.
    """
    from ...domain.deadlines import profiles as profiles_mod
    from ..setup_answers import project_setup_answers

    bound = getattr(profiles_mod, "project_setup_answers", None)
    assert bound is project_setup_answers, f"_profiles binds {bound!r}, not the core projector"


def test_profiles_import_purity_never_loads_the_wizard() -> None:
    """Importing _profiles must not drag in the application wizard package."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""\
        import importlib
        import sys

        profiles = importlib.import_module("cadrumo.domain.deadlines.profiles")
        from cadrumo.core.setup_answers import project_setup_answers

        assert profiles.project_setup_answers is project_setup_answers
        leaked = sorted(name for name in sys.modules if name.startswith("cadrumo.application.wizard"))
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
        from cadrumo.core.setup_answers import get_project_answers, ProjectAnswersNotRegisteredError
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


def test_project_answers_refuses_distinct_second_projector() -> None:
    """The core slot rejects a replacement projector through its exact registered error."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""\
        from collections.abc import Mapping
        from typing import Any

        from pydantic import BaseModel

        from cadrumo.core.errors.error_codes import build_error_envelope, get_registered_error_code
        from cadrumo.core.setup_answers import (
            ProjectAnswersRegistrationError,
            register_project_answers,
        )

        def initial_projector(flow: Any, values: Mapping[str, str]) -> BaseModel:
            del flow, values
            return BaseModel()

        def replacement_projector(flow: Any, values: Mapping[str, str]) -> BaseModel:
            del flow, values
            return BaseModel()

        register_project_answers(initial_projector)
        try:
            register_project_answers(replacement_projector)
        except ProjectAnswersRegistrationError as refusal:
            assert get_registered_error_code(refusal).code == "INTERNAL_PROFILE_REGISTRATION"
            assert build_error_envelope(refusal).code == "INTERNAL_PROFILE_REGISTRATION"
        else:
            raise AssertionError("the second project_answers registration was accepted")
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Second-projector refusal check failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_project_answers_registered_after_persistence_import() -> None:
    """Importing _persistence registers project_answers in the core slot."""
    # Importing persistence triggers the module-level registration call.
    importlib.import_module("cadrumo.application.wizard.persistence")

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
    from ...domain.deadlines.models import IVARegime
    from ...domain.contribuyente.entity_type import EntityType
    from ..setup_answers import SetupAnswers

    # Test iva_regime coercion
    setup_answers = SetupAnswers(
        tax_id="12345678A",
        tax_residence_jurisdiction_scope="common_regime",
        iva_regime="GENERAL",
        iva_redeme_enrolled=False,
        iva_m303_regime_composition="general",
        iva_cash_accounting_regime_enrolled=False,
        iva_voluntary_sii_enrolled=False,
        iva_hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )
    assert setup_answers.iva_regime == IVARegime.GENERAL

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
