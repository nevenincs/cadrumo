"""Tests for the cross-revision drift validator.

Per the AEAT registry design contract, every casilla id has
identical legal responsibilities across every revision of a
modelo. The `_validate_cross_revision_casilla_consistency` gate
fails registry load when two revisions disagree on any
legally-bound field (label, section, data_type, semantic_role,
constraints).
"""

from __future__ import annotations

from typing import Any

import pytest

from ._schema import CasillaConstraints, CasillaDefinition
from ._validate import _validate_cross_revision_casilla_consistency


pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _casilla(
    *,
    cid: str = "0001",
    label: str = "Test casilla",
    section: tuple[str, ...] = ("test",),
    data_type: str = "money",
    semantic_role: str | None = None,
    constraints: CasillaConstraints | None = None,
) -> CasillaDefinition:
    return CasillaDefinition(
        id=cid,
        number=cid,
        label=label,
        section=section,
        data_type=data_type,  # type: ignore[arg-type]
        semantic_role=semantic_role,
        constraints=constraints,
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
    )


def _modelo(modelo_id: str, revs: dict[str, list[CasillaDefinition]]) -> Any:
    class _Rev:
        def __init__(self, rid: str, cas: list[CasillaDefinition]) -> None:
            self.id = rid
            self.casillas = tuple(cas)

    class _Mod:
        def __init__(self) -> None:
            self.id = modelo_id
            self.revisions = {rid: _Rev(rid, c) for rid, c in revs.items()}

    return _Mod()


class TestCrossRevisionConsistency:
    def test_identical_casilla_across_revisions_passes(self) -> None:
        a = _casilla(cid="0700", label="Test", data_type="money")
        b = _casilla(cid="0700", label="Test", data_type="money")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        assert _validate_cross_revision_casilla_consistency([m]) == ()

    def test_label_drift_caught(self) -> None:
        a = _casilla(cid="0700", label="Original")
        b = _casilla(cid="0700", label="Different")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert len(failures) == 1
        assert "label" in failures[0]
        assert "0700" in failures[0]

    def test_data_type_drift_caught(self) -> None:
        a = _casilla(cid="0700", data_type="money")
        b = _casilla(cid="0700", data_type="decimal")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("data_type" in f for f in failures)

    def test_section_drift_caught(self) -> None:
        a = _casilla(cid="0700", section=("a", "b"))
        b = _casilla(cid="0700", section=("a", "c"))
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("section" in f for f in failures)

    def test_semantic_role_drift_caught(self) -> None:
        a = _casilla(cid="0700", semantic_role="taxpayer_nif")
        b = _casilla(cid="0700", semantic_role="payee_nif")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("semantic_role" in f for f in failures)

    def test_constraints_drift_caught(self) -> None:
        constrained = CasillaConstraints(
            sign="non_negative",
            legal_refs=("ley-58-2003:art-29",),
            source_refs=("aeat-manual",),
        )
        a = _casilla(cid="0700", constraints=constrained)
        b = _casilla(cid="0700", constraints=None)
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("constraints" in f for f in failures)

    def test_single_revision_casilla_passes(self) -> None:
        a = _casilla(cid="0700")
        m = _modelo("100", {"2025": [a]})
        assert _validate_cross_revision_casilla_consistency([m]) == ()

    def test_three_revisions_one_diverges(self) -> None:
        a = _casilla(cid="0700", label="Same")
        b = _casilla(cid="0700", label="Same")
        c = _casilla(cid="0700", label="Different")
        m = _modelo("100", {"2023": [a], "2024": [b], "2025": [c]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert len(failures) == 1
        assert "2025" in failures[0]

    def test_two_modelos_independent(self) -> None:
        m100 = _modelo("100", {"2024": [_casilla(cid="0700", label="A")],
                                "2025": [_casilla(cid="0700", label="A")]})
        m180 = _modelo("180", {"2020": [_casilla(cid="0700", label="X")],
                                "2025": [_casilla(cid="0700", label="X")]})
        assert _validate_cross_revision_casilla_consistency([m100, m180]) == ()

    def test_canonical_revision_appears_in_failure_message(self) -> None:
        a = _casilla(cid="0700", label="Old")
        b = _casilla(cid="0700", label="New")
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert len(failures) == 1
        assert "2024" in failures[0]
        assert "2025" in failures[0]
