"""The continuity gate reads a casilla's lineage origin.

A seeded chain is inference -- identifier, semantic role, data type and printed
box agree -- and is admissible only while that inference still holds. A
grounded chain is a statement resting on cited evidence. Each pair below
declares the same chain with identical content and identical evidence text,
differing only in the origin token, and the two must reach different outcomes.
Every refusal has a control that differs only in the planted defect, so
removing the rule turns the refusal test red rather than vacuously green.
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict, Unpack

import pytest
from dev.registry.compiler.registry_scope import validate_registry_scope

from ..casilla_lineage import CasillaLineageOrigin
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaDefinition
from ._synthetic_locale_fixtures import _synthetic_locale_scope, _write_test_label

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = ["_synthetic_locale_scope"]

_EVIDENCE = "disenos_registro/modelo_123/files/2025.txt:188 box [06] continues 2024 box [06]"
_CHAIN = "base-retenciones"
_ROLE = "base_retenciones"
_SEEDED = CasillaLineageOrigin.SEEDED
_GROUNDED = CasillaLineageOrigin.GROUNDED


class _RowFields(TypedDict, total=False):
    """The row content a seeded and a grounded chain are compared on."""

    cid: str
    role: str | None
    data_type: str
    form_number: str | None


def _row(
    *,
    chain: str = _CHAIN,
    origin: CasillaLineageOrigin | None = None,
    evidence: str | None = None,
    **fields: Unpack[_RowFields],
) -> CasillaDefinition:
    cid = fields.get("cid", "06")
    form_number = fields.get("form_number")
    payload: dict[str, object] = {
        "id": cid,
        "number": cid,
        "localization_keys": (_write_test_label("Base de retenciones"),),
        "section": ("liquidacion",),
        "data_type": fields.get("data_type", "money"),
        "semantic_role": fields.get("role", _ROLE),
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
        "continuidad_id": chain,
    }
    if form_number is not None:
        payload["form_number"] = form_number
    if origin is not None:
        payload["continuidad_origin"] = origin.value
    if evidence is not None:
        payload["continuidad_evidence"] = evidence
    return CasillaDefinition.model_validate(payload)


def _modelo(*editions: list[CasillaDefinition], shared_window: bool = False) -> ModeloDefinition:
    years = tuple(2023 + offset for offset in range(len(editions)))
    shared = PeriodSelector(years=years, periods=("0A",))
    revisions = {
        str(year): ModeloRevision.model_validate(
            {
                "id": str(year),
                "localization_key": f"test.schema.revision.{year}.label",
                "valid_from": date(year, 1, 1),
                "period_selector": shared if shared_window else PeriodSelector(years=(year,), periods=("0A",)),
                "legal_refs": ("ley-58-2003:art-29",),
                "source_refs": ("aeat-manual",),
                "casillas": tuple(casillas),
            },
        )
        for year, casillas in zip(years, editions, strict=True)
    }
    return ModeloDefinition.model_validate(
        {
            "id": "123",
            "title_localization_key": "test.schema.modelo.123.title",
            "official_name_localization_key": "test.schema.modelo.123.official_name",
            "tax_domain": "irpf",
            "cadence": "annual",
            "jurisdiction": "ES-AEAT",
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "revisions": revisions,
        },
    )


def _continuation(
    origin: CasillaLineageOrigin,
    *,
    predecessor: _RowFields,
    successor: _RowFields,
) -> ModeloDefinition:
    """One boundary: an unmarked predecessor row and a successor claiming it."""
    return _modelo(
        [_row(**predecessor)],
        [_row(**successor, origin=origin, evidence=_EVIDENCE)],
    )


_CONTINUITY_GATE = ("casilla lineage continuation refused", "cross-revision continuity semantic linkage")


def _continuity_outcome(modelo: ModeloDefinition) -> tuple[str, ...]:
    """The continuity gate's findings from a full registry-scope run.

    A moved data type under one semantic role is also refused by the separate
    role-consistency gate whatever the lineage origin; that refusal is not
    this gate's outcome and must not decide the comparison.
    """
    return tuple(failure for failure in validate_registry_scope([modelo]) if failure.startswith(_CONTINUITY_GATE))


_DIVERGENCES: dict[str, tuple[_RowFields, _RowFields, str]] = {
    "renumbered box": ({"cid": "06"}, {"cid": "07"}, "casilla identifier moved '06' -> '07'"),
    "role moved": ({"role": _ROLE}, {"role": "base_retenciones_trabajo"}, "semantic_role moved"),
    "data type moved": ({"data_type": "money"}, {"data_type": "integer"}, "data_type moved"),
    "printed box moved": ({"form_number": "6"}, {"form_number": "8"}, "form_number moved '6' -> '8'"),
}


@pytest.mark.parametrize("divergence", sorted(_DIVERGENCES))
def test_a_divergent_seeded_chain_is_refused_where_the_same_grounded_chain_passes(divergence: str) -> None:
    predecessor, successor, reason = _DIVERGENCES[divergence]

    seeded = _continuity_outcome(_continuation(_SEEDED, predecessor=predecessor, successor=successor))
    grounded = _continuity_outcome(_continuation(_GROUNDED, predecessor=predecessor, successor=successor))

    assert grounded == ()
    assert len(seeded) == 1
    assert "casilla lineage continuation refused" in seeded[0]
    assert "continuidad_origin 'seeded'" in seeded[0]
    assert reason in seeded[0]


def test_a_seeded_chain_whose_inference_still_holds_passes() -> None:
    """The control for every divergence above: agreeing rows are admissible seeded."""
    agreeing: _RowFields = {"cid": "06", "form_number": "6"}

    assert validate_registry_scope([_continuation(_SEEDED, predecessor=agreeing, successor=agreeing)]) == ()


def test_a_role_less_grounded_chain_links_where_the_same_seeded_chain_is_refused() -> None:
    role_less: _RowFields = {"role": None}

    seeded = validate_registry_scope([_continuation(_SEEDED, predecessor=role_less, successor=role_less)])
    grounded = validate_registry_scope([_continuation(_GROUNDED, predecessor=role_less, successor=role_less)])

    assert grounded == ()
    assert sorted(failure.split(":")[0] for failure in seeded) == [
        "casilla lineage continuation refused",
        "cross-revision continuity semantic linkage missing",
        "cross-revision continuity semantic linkage missing",
    ]
    assert any("predecessor row has no semantic_role to agree on" in failure for failure in seeded)


def test_an_unmarked_role_less_chain_is_still_refused() -> None:
    """Unset origin is an authored declaration and earns no evidence exemption."""
    modelo = _modelo([_row(role=None)], [_row(role=None)])

    failures = validate_registry_scope([modelo])

    assert len(failures) == 2
    assert all("semantic linkage missing" in failure for failure in failures)


def test_grounding_does_not_exempt_a_row_that_also_takes_part_in_an_ungrounded_link() -> None:
    """2023 -grounded-> 2024 -unmarked-> 2025: only the 2023 row is fully grounded."""
    grounded_middle = _row(role=None, origin=_GROUNDED, evidence=_EVIDENCE)

    authored_tail = validate_registry_scope([_modelo([_row(role=None)], [grounded_middle], [_row(role=None)])])
    grounded_tail = validate_registry_scope(
        [_modelo([_row(role=None)], [grounded_middle], [_row(role=None, origin=_GROUNDED, evidence=_EVIDENCE)])],
    )

    assert grounded_tail == ()
    assert sorted(failure.rsplit("revision ", 1)[1].split(" ")[0] for failure in authored_tail) == ["'2024'", "'2025'"]


def test_whitespace_evidence_grounds_nothing() -> None:
    blank = _modelo([_row(role=None)], [_row(role=None, origin=_GROUNDED, evidence="   ")])

    failures = validate_registry_scope([blank])

    assert len(failures) == 2
    assert all("semantic linkage missing" in failure for failure in failures)


@pytest.mark.parametrize("origin", [_SEEDED, _GROUNDED])
def test_a_continuation_in_the_first_edition_is_refused(origin: CasillaLineageOrigin) -> None:
    modelo = _modelo([_row(origin=origin, evidence=_EVIDENCE)], [_row()])

    failures = validate_registry_scope([modelo])

    assert len(failures) == 1
    assert "revision '2023'" in failures[0]
    assert "the first edition has no predecessor edition to continue" in failures[0]


@pytest.mark.parametrize("origin", [_SEEDED, _GROUNDED])
def test_a_continuation_the_predecessor_edition_does_not_carry_is_refused(origin: CasillaLineageOrigin) -> None:
    carried = _modelo([_row()], [_row(origin=origin, evidence=_EVIDENCE)])
    not_carried = _modelo(
        [_row(chain="base-retenciones-anterior", role="base_retenciones_anterior")],
        [_row(origin=origin, evidence=_EVIDENCE)],
    )

    assert validate_registry_scope([carried]) == ()
    failures = validate_registry_scope([not_carried])
    assert len(failures) == 1
    assert "predecessor edition '2023' does not carry continuidad_id 'base-retenciones'" in failures[0]


@pytest.mark.parametrize("origin", [_SEEDED, _GROUNDED])
def test_a_continuation_with_two_predecessor_carriers_is_refused(origin: CasillaLineageOrigin) -> None:
    modelo = _modelo(
        [_row(cid="06"), _row(cid="07", role="base_retenciones_bis")],
        [_row(origin=origin, evidence=_EVIDENCE)],
    )

    failures = [failure for failure in validate_registry_scope([modelo]) if "lineage continuation" in failure]

    assert len(failures) == 1
    assert "on 2 rows ('06', '07')" in failures[0]


@pytest.mark.parametrize("origin", [_SEEDED, _GROUNDED])
def test_a_continuation_across_a_shared_validity_window_is_refused(origin: CasillaLineageOrigin) -> None:
    modelo = _modelo([_row()], [_row(origin=origin, evidence=_EVIDENCE)], shared_window=True)

    failures = [failure for failure in validate_registry_scope([modelo]) if "lineage continuation" in failure]

    assert len(failures) == 1
    assert "shares a validity window with this edition" in failures[0]
