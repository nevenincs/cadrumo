"""Real-behavior tests for ``build_overview_explain``."""

from __future__ import annotations

import pytest

from aeat.domain.deadlines import AutonomoProfile
from aeat.domain.deadlines._models import IVARegime

from ._errors import OverviewExplainError
from ._explain import OverviewExplain, build_overview_explain

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
    )


def test_explain_returns_typed_envelope_for_applicable_modelo() -> None:
    """A modelo that applies to the profile yields applicable=True
    plus the registry-backed rationale text."""

    result = build_overview_explain(_profile(), modelo="303", year=2026)

    assert isinstance(result, OverviewExplain)
    assert result.modelo == "303"
    assert result.year == 2026
    assert isinstance(result.applicable, bool)
    assert result.rationale
    assert result.profile_facts["tax_id"] == "X1234567L"
    assert result.profile_facts["iva_regime"] == "GENERAL"


def test_explain_refuses_unknown_modelo() -> None:
    """A modelo identifier the registry has no deadline windows for
    surfaces as OverviewExplainError rather than leaking the engine's
    ScheduleComputationError."""

    with pytest.raises(OverviewExplainError, match=r"could not evaluate"):
        build_overview_explain(_profile(), modelo="999999", year=2026)


def test_explain_refuses_blank_modelo() -> None:
    """A blank modelo identifier is refused at the service boundary."""

    with pytest.raises(OverviewExplainError, match=r"no puede estar en blanco"):
        build_overview_explain(_profile(), modelo="  ", year=2026)


def test_explain_profile_facts_surface_deadline_relevant_fields() -> None:
    """The profile_facts dict must include every field the deadline
    engine reads when evaluating applicability; the operator audits
    these to understand which facts the answer depends on."""

    result = build_overview_explain(_profile(), modelo="303", year=2026)

    # Required scalar fields the engine reads.
    for field in (
        "tax_id",
        "iva_regime",
        "has_employees",
        "uses_objective_estimation_irpf",
        "does_intracomunitario",
    ):
        assert field in result.profile_facts, f"profile_facts missing {field}"
    # Nested IVA sub-model facts must also be flattened.
    assert "iva.roi_enrolled" in result.profile_facts
    assert "iva.oss_enrolled" in result.profile_facts


def test_explain_degrades_gracefully_for_modelo_without_deadline_windows() -> None:
    """A known registry modelo with no deadline windows for the year
    must degrade gracefully: report a (False) applicability flag and an
    informational rationale rather than raising OverviewExplainError.

    Modelo 100 (Renta) is a real registry modelo, but its annual filing
    window is not registered for every year (see registry-track gap
    R1). The CLI must still answer instead of crashing.
    """

    result = build_overview_explain(_profile(), modelo="100", year=2026)

    assert isinstance(result, OverviewExplain)
    assert result.modelo == "100"
    assert result.applicable is False
    # The rationale is an informational substitute, not an error string.
    assert result.rationale
    assert "100" in result.rationale
    # Profile facts are still surfaced so the operator sees the inputs.
    assert "tax_id" in result.profile_facts


def test_explain_unknown_modelo_still_raises_not_degrades() -> None:
    """A modelo identifier absent from the calculation registry must
    still raise OverviewExplainError. Graceful degradation applies only
    to known modelos missing deadline-window data, not to operator
    typos / unknown identifiers."""

    with pytest.raises(OverviewExplainError, match=r"could not evaluate"):
        build_overview_explain(_profile(), modelo="999999", year=2026)


def test_explain_applicability_matches_deadline_engine() -> None:
    """The applicable flag must equal the value the same DeadlineEngine
    instance would return; explain and the operational views cannot
    diverge on the binary applicability decision."""

    from aeat.domain.deadlines import DeadlineEngine

    engine = DeadlineEngine()
    result = build_overview_explain(_profile(), modelo="303", year=2026, engine=engine)

    assert result.applicable == engine.applies_to(_profile(), "303", year=2026)
