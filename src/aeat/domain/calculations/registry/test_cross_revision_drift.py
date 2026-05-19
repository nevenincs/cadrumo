"""Tests for the cross-revision drift validator.

Per the AEAT registry design contract, every casilla id has
identical legal responsibilities across every revision of a
modelo. The `_validate_cross_revision_casilla_consistency` gate
reports drift when two revisions disagree on any
legally-bound field (label, section, data_type, semantic_role,
legal_refs).
"""

from __future__ import annotations

from typing import Any

import pytest

from aeat.core.resources import bundled_path

from . import load_registry_tree
from ._errors import RegistryValidationError
from ._schema import CasillaDefinition
from ._validate import (
    _validate_cross_revision_casilla_consistency,
    validate_cross_revision_casilla_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _casilla(
    *,
    cid: str = "0001",
    label: str = "Test casilla",
    section: tuple[str, ...] = ("test",),
    data_type: str = "money",
    semantic_role: str | None = None,
    legal_refs: tuple[str, ...] = ("ley-58-2003:art-29",),
) -> CasillaDefinition:
    return CasillaDefinition(
        id=cid,
        number=cid,
        label=label,
        section=section,
        data_type=data_type,  # type: ignore[arg-type]
        semantic_role=semantic_role,
        legal_refs=legal_refs,
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

    def test_legal_refs_drift_caught(self) -> None:
        a = _casilla(cid="0700", legal_refs=("ley-58-2003:art-29",))
        b = _casilla(cid="0700", legal_refs=("ley-58-2003:art-30",))
        m = _modelo("100", {"2024": [a], "2025": [b]})
        failures = _validate_cross_revision_casilla_consistency([m])
        assert any("legal_refs" in f for f in failures)

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


def test_cross_revision_validator_catches_real_committed_corpus_drift() -> None:
    modelos, _ = load_registry_tree(bundled_path("registry", "aeat"))

    with pytest.raises(RegistryValidationError) as exc_info:
        validate_cross_revision_casilla_consistency(modelos)

    message = str(exc_info.value)
    assert "cross-revision casilla drift detected" in message
    assert "modelo 123 casilla '01'" in message
    assert "label" in message
