"""Roundtrip and validator tests for Plan C semantic_role + aliases.

`CasillaDefinition` gained an optional `semantic_role: str | None`
slot and an `aliases: tuple[CasillaAlias, ...]` slot. The
snapshot-build validator now enforces that every casilla sharing a
`semantic_role` declares the same `data_type` and structurally
compatible `constraints`. Single-occurrence role values emit a
typo-twin warning via `warnings.warn`.

These tests exercise the field shape, the consistency validator,
the typo-twin warning surface, and the alias-preservation
round-trip.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from typing import Any

import pytest
from pydantic import ValidationError

from ._schema import CasillaAlias, CasillaConstraints, CasillaDefinition
from ._validate import (
    _emit_semantic_role_typo_twin_warnings,
    _validate_semantic_role_consistency,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _casilla(
    *,
    cid: str = "test_casilla",
    data_type: str = "money",
    semantic_role: str | None = None,
    aliases: Iterable[CasillaAlias] = (),
    constraints: CasillaConstraints | None = None,
) -> CasillaDefinition:
    return CasillaDefinition(
        id=cid,
        number="01",
        label="Test casilla",
        section=("test",),
        data_type=data_type,  # type: ignore[arg-type]
        semantic_role=semantic_role,
        aliases=tuple(aliases),
        constraints=constraints,
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
    )


def _modelo(modelo_id: str, revision_id: str, casillas: Iterable[CasillaDefinition]) -> Any:
    """Build the minimum object shape `_validate_semantic_role_consistency` expects.

    The validator only reads `.id` on the modelo, `.id` on each
    revision, and walks `.casillas`. Use a lightweight stand-in to
    avoid pulling the full ModeloDefinition / ModeloRevision schema
    (with its many required fields) for unit-test scope.
    """

    class _Rev:
        def __init__(self) -> None:
            self.id = revision_id
            self.casillas = tuple(casillas)

    class _Mod:
        def __init__(self) -> None:
            self.id = modelo_id
            self.revisions = {revision_id: _Rev()}

    return _Mod()


class TestSemanticRoleFieldShape:
    def test_default_role_is_none(self) -> None:
        c = _casilla()
        assert c.semantic_role is None
        assert c.aliases == ()

    def test_role_round_trips(self) -> None:
        c = _casilla(semantic_role="taxpayer_nif", data_type="nif")
        rebuilt = CasillaDefinition.model_validate(c.model_dump())
        assert rebuilt.semantic_role == "taxpayer_nif"
        assert rebuilt == c

    def test_empty_role_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _casilla(semantic_role="")

    def test_aliases_round_trip(self) -> None:
        alias = CasillaAlias(
            label="NIF declarante",
            legal_refs=("ley-58-2003:art-29",),
            source_refs=("aeat-manual",),
        )
        c = _casilla(semantic_role="taxpayer_nif", data_type="nif", aliases=[alias])
        rebuilt = CasillaDefinition.model_validate(c.model_dump())
        assert len(rebuilt.aliases) == 1
        assert rebuilt.aliases[0].label == "NIF declarante"
        assert rebuilt.aliases[0].legal_refs == ("ley-58-2003:art-29",)


class TestValidateSemanticRoleConsistency:
    def test_no_role_declarations_passes(self) -> None:
        m = _modelo("180", "2023", [_casilla()])
        assert _validate_semantic_role_consistency([m]) == ()

    def test_matching_role_declarations_pass(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        assert _validate_semantic_role_consistency([m1, m2]) == ()

    def test_diverging_data_type_rejected(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="text")
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        failures = _validate_semantic_role_consistency([m1, m2])
        assert any("data_type" in f for f in failures)
        assert any("taxpayer_nif" in f for f in failures)

    def test_diverging_constraints_rejected(self) -> None:
        common_legal = ("ley-58-2003:art-29",)
        common_source = ("aeat-manual",)
        constrained = CasillaConstraints(
            sign="non_negative", legal_refs=common_legal, source_refs=common_source
        )
        unconstrained = CasillaConstraints(
            sign="any", legal_refs=common_legal, source_refs=common_source
        )
        a = _casilla(cid="a", semantic_role="retenciones", data_type="money", constraints=constrained)
        b = _casilla(cid="b", semantic_role="retenciones", data_type="money", constraints=unconstrained)
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        failures = _validate_semantic_role_consistency([m1, m2])
        assert any("constraints" in f for f in failures)


class TestTypoTwinWarning:
    def test_single_occurrence_role_emits_warning(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer-nif", data_type="nif")  # note hyphen typo
        m = _modelo("180", "2023", [a])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m])
        assert any("taxpayer-nif" in str(w.message) for w in captured)

    def test_repeated_role_does_not_warn(self) -> None:
        a = _casilla(cid="a", semantic_role="taxpayer_nif", data_type="nif")
        b = _casilla(cid="b", semantic_role="taxpayer_nif", data_type="nif")
        m1 = _modelo("180", "2023", [a])
        m2 = _modelo("184", "2023", [b])
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            _emit_semantic_role_typo_twin_warnings([m1, m2])
        role_warnings = [w for w in captured if "taxpayer_nif" in str(w.message)]
        assert role_warnings == []
