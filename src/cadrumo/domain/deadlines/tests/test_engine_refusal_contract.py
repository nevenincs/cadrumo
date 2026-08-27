"""The deadline engine's refusals carry a registered key, never authored prose.

Both engine refusal classes resolve their operator-facing text from a
registered message key, but ``str(exc)`` prefers ``args[0]``.  A raise site
that passes an authored sentence positionally *alongside* the key therefore
stays green under a key-and-context assertion while the English sentence keeps
reaching tracebacks, logs, and every boundary that renders the exception
directly -- in every locale.  The assertions here are deliberately
*absence* assertions: they require ``str(exc)`` to be exactly the key, which is
false the moment a positional argument returns.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core import Period
from ...calculations.registry.schema_verification import ProfilePredicateDefinition
from .. import (
    DeadlineEngine,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    NoDeadlineWindowsError,
    ScheduleComputationError,
    TaxpayerProfile,
)
from .. import _engine as _engine_module
from .._engine import (
    _MISSING_WINDOWS_MESSAGE_KEY,
    _SCHEDULE_COMPUTATION_MESSAGE_KEY,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The two engine refusal classes whose recovery authority this module pins.
#: ``DeadlineValidationError`` is deliberately absent: it guards caller-supplied
#: construction arguments and registry shape invariants rather than an
#: operator-facing refusal, and it carries no registered recovery.
_PINNED_ERROR_NAMES = ("NoDeadlineWindowsError", "ScheduleComputationError")

#: The engine functions that must still raise a pinned refusal.  Without this
#: anchor a rename would empty the AST sweep and let it pass vacuously.
_EXPECTED_RAISING_FUNCTIONS = frozenset(
    {
        "DeadlineEngine.__init__",
        "DeadlineEngine.compute",
        "DeadlineEngine.explain",
        "DeadlineEngine._deadline_windows",
        "DeadlineEngine._evaluate_conditions",
    },
)

assert _engine_module.__file__ is not None
_ENGINE_SOURCE = Path(_engine_module.__file__)


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X1234567L",
            "iva_regime": IVARegime.GENERAL,
            "iva": ModeloIVAProfile(
                tax_territory=M303TaxTerritory.COMMON_REGIME,
                regime_composition=M303RegimeComposition.GENERAL,
                redeme_enrolled=False,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            ),
            "professional_income_withholding_ge_70pct": False,
            "art109_activity_income_withholding_ge_70pct": False,
        },
    )


def _write_unloadable_registry(root: Path) -> Path:
    """Materialise a real registry tree whose modelo manifest cannot be parsed."""
    modelo_root = root / "modelos" / "130"
    modelo_root.mkdir(parents=True)
    (modelo_root / "manifest.toml").write_text("[modelo\nid = ", encoding="utf-8")
    return root


class TestMessageKeysMatchTheRegistry:
    """The stated keys are the classes' own registered keys."""

    def test_missing_windows_key_is_the_registered_key(self) -> None:
        assert NoDeadlineWindowsError.code.message_key == _MISSING_WINDOWS_MESSAGE_KEY

    def test_schedule_computation_key_is_the_registered_key(self) -> None:
        assert ScheduleComputationError.code.message_key == _SCHEDULE_COMPUTATION_MESSAGE_KEY


class TestRefusalsCarryNoAuthoredSentence:
    """Every reachable refusal renders as its key, never as English."""

    def test_compute_without_registered_windows_renders_the_key(self) -> None:
        with pytest.raises(NoDeadlineWindowsError) as excinfo:
            DeadlineEngine().compute(_profile(), 1999)

        assert str(excinfo.value) == "errors.error.error_deadlines_missing_windows"
        assert excinfo.value.context == {"filing_year": 1999}

    def test_explain_without_registered_windows_renders_the_key(self) -> None:
        with pytest.raises(NoDeadlineWindowsError) as excinfo:
            DeadlineEngine().explain(_profile(), "999", year=1999)

        assert str(excinfo.value) == "errors.error.error_deadlines_missing_windows"
        assert excinfo.value.context == {"modelo": "999", "filing_year": 1999}

    def test_unparseable_registry_renders_the_key(self, tmp_path: Path) -> None:
        with pytest.raises(ScheduleComputationError) as excinfo:
            DeadlineEngine(registry_root=_write_unloadable_registry(tmp_path))

        assert str(excinfo.value) == "errors.error.error_deadlines_schedule_computation"
        assert excinfo.value.context is not None
        assert excinfo.value.context["registry_stage"] == "load"
        assert excinfo.value.__cause__ is not None

    def test_unresolvable_profile_condition_renders_the_key(self) -> None:
        condition = ProfilePredicateDefinition(
            field="no_such_declared_profile_fact",
            op="equals",
            value=True,
            explanation="Condition naming a fact the taxpayer profile does not declare.",
            legal_refs=("rd-439-2007:art-110",),
            source_refs=("aeat-dr-130-2019-v12",),
        )

        with pytest.raises(ScheduleComputationError) as excinfo:
            DeadlineEngine().evaluate_conditions(_profile(), (condition,), mode="all")

        assert str(excinfo.value) == "errors.error.error_deadlines_schedule_computation"
        assert excinfo.value.context is not None
        assert excinfo.value.context["registry_stage"] == "profile_condition_evaluation"
        assert excinfo.value.context["condition_count"] == 1
        assert excinfo.value.context["condition_mode"] == "all"


def _pinned_raise_sites() -> tuple[tuple[str, ast.Call], ...]:
    """Return ``(enclosing_qualname, call)`` for each pinned engine refusal."""
    tree = ast.parse(_ENGINE_SOURCE.read_text(encoding="utf-8"))
    found: list[tuple[str, ast.Call]] = []

    def walk(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                walk(child, (*scope, child.name))
                continue
            if (
                isinstance(child, ast.Raise)
                and isinstance(child.exc, ast.Call)
                and isinstance(child.exc.func, ast.Name)
                and child.exc.func.id in _PINNED_ERROR_NAMES
            ):
                found.append((".".join(scope), child.exc))
            walk(child, scope)

    walk(tree, ())
    return tuple(found)


class TestEveryPinnedRaiseSiteIsStructurallyClean:
    """No pinned raise site may reintroduce a positional sentence.

    The runtime assertions above reach four of the five sites.  The
    validation-stage refusal in ``_deadline_windows`` is not reachable from a
    test: ``ValidatedRegistryAuthority.load`` validates eagerly, so a registry
    that would fail per-modelo validation is refused at the load stage instead.
    This sweep is what covers it, and it covers any site added later.
    """

    def test_the_expected_functions_still_raise(self) -> None:
        assert {qualname for qualname, _ in _pinned_raise_sites()} == _EXPECTED_RAISING_FUNCTIONS

    def test_no_pinned_raise_site_passes_a_positional_argument(self) -> None:
        offenders = [qualname for qualname, call in _pinned_raise_sites() if call.args]

        assert offenders == []

    def test_every_pinned_raise_site_states_a_registered_key(self) -> None:
        registered = {
            "_MISSING_WINDOWS_MESSAGE_KEY": NoDeadlineWindowsError.code.message_key,
            "_SCHEDULE_COMPUTATION_MESSAGE_KEY": ScheduleComputationError.code.message_key,
        }
        stated = {}
        for qualname, call in _pinned_raise_sites():
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            assert "translated_message" in keywords, qualname
            value = keywords["translated_message"]
            assert isinstance(value, ast.Name), qualname
            assert value.id in registered, qualname
            stated[qualname] = registered[value.id]

        assert set(stated) == _EXPECTED_RAISING_FUNCTIONS

    def test_no_pinned_raise_site_carries_command_prose_in_its_facts(self) -> None:
        for qualname, call in _pinned_raise_sites():
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            context = keywords.get("context")
            assert isinstance(context, ast.Dict), qualname
            for value in context.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    assert "aeat" not in value.value, qualname


class TestPeriodBoundariesStayCanonical:
    """The refused year is the canonical filing year, not a re-derived span."""

    def test_reported_filing_year_matches_the_canonical_period_year(self) -> None:
        with pytest.raises(NoDeadlineWindowsError) as excinfo:
            DeadlineEngine().compute(_profile(), 1999)

        assert excinfo.value.context is not None
        reported = excinfo.value.context["filing_year"]
        assert reported == Period.from_year_and_code(1999, "1T").filing_year
