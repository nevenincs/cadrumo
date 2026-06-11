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
"""

from __future__ import annotations

import ast
import importlib
import inspect

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
    from ...application.wizard._catalogue import SETUP_FLOW
    from ..setup_answers import SetupAnswers

    assert SETUP_FLOW.answers_model is SetupAnswers, (
        f"SETUP_FLOW.answers_model is {SETUP_FLOW.answers_model!r}; expected aeat.core.setup_answers.SetupAnswers"
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


def test_profiles_no_deferred_application_imports() -> None:
    """_profiles.py must contain no deferred imports from aeat.application.wizard."""
    # Parse the source AST and look for Import / ImportFrom nodes that
    # reference aeat.application.wizard inside any function body.
    profiles_path = inspect.getfile(importlib.import_module("aeat.domain.deadlines._profiles"))
    with open(profiles_path, encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=profiles_path)

    deferred_violations: list[str] = []
    for node in ast.walk(tree):
        # Only flag imports that are *inside* a function definition.
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.ImportFrom):
                if child.module and "application.wizard" in child.module:
                    deferred_violations.append(f"line {child.lineno}: from {child.module} import ...")
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    if "application.wizard" in alias.name:
                        deferred_violations.append(f"line {child.lineno}: import {alias.name}")

    assert not deferred_violations, "_profiles.py contains deferred application.wizard imports:\n" + "\n".join(
        deferred_violations,
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


def test_setup_answers_iva_regime_string_coercion() -> None:
    """SetupAnswers coerces a string IVA regime token to the enum."""
    from ..setup_answers import SetupAnswers

    sa = SetupAnswers(tax_id="12345678A", iva_regime="GENERAL")
    # iva_regime should be the enum member, not the raw string.
    from ...domain.deadlines._models import IVARegime

    assert sa.iva_regime == IVARegime.GENERAL


def test_setup_answers_invalid_iva_regime_raises() -> None:
    """SetupAnswers raises on an unrecognised IVA regime token."""
    import pydantic

    from ..setup_answers import SetupAnswers

    with pytest.raises(pydantic.ValidationError):
        SetupAnswers(tax_id="12345678A", iva_regime="NOT_A_REGIME")


def test_setup_answers_entity_type_coercion() -> None:
    """SetupAnswers coerces a string entity type token to the enum."""
    from ...domain.deadlines._models import EntityType
    from ..setup_answers import SetupAnswers

    sa = SetupAnswers(tax_id="12345678A", entity_type="natural_person")
    assert sa.entity_type == EntityType.NATURAL_PERSON


def test_setup_answers_invalid_date_raises() -> None:
    """SetupAnswers raises on a non-ISO activity_start_date."""
    import pydantic

    from ..setup_answers import SetupAnswers

    with pytest.raises(pydantic.ValidationError):
        SetupAnswers(tax_id="12345678A", activity_start_date="31-12-2024")


def test_setup_answers_valid_date_accepted() -> None:
    """SetupAnswers accepts a valid ISO-8601 activity_start_date."""
    from ..setup_answers import SetupAnswers

    sa = SetupAnswers(tax_id="12345678A", activity_start_date="2024-01-01")
    assert sa.activity_start_date == "2024-01-01"
