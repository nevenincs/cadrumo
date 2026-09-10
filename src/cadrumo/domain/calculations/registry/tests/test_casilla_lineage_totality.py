"""Lineage totality judges every successor-edition row against a per-row exception set.

Each refusal is paired with a control that differs only in the planted defect,
so removing the rule turns the refusal red rather than leaving it vacuously
green, and over-reaching the rule turns the control red.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..casilla_lineage import CasillaLineageOrigin
from ..casilla_lineage_totality import CasillaRowKey, lineage_totality, unresolved_successor_rows
from ..schema import ModeloDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaDefinition
from ._synthetic_locale_fixtures import _synthetic_locale_scope, _write_test_label

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

__all__ = ["_synthetic_locale_scope"]

_MODELO = "123"
_EVIDENCE = "disenos_registro/modelo_123/files/2025.txt:188 box [07] first printed in 2025"
_NO_PREDECESSOR = {
    "none": {
        "reason": "a parallel scheme variant taking effect alongside its siblings",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    },
}


def _row(
    cid: str,
    *,
    chain: str | None = None,
    origin: CasillaLineageOrigin | None = None,
) -> CasillaDefinition:
    payload: dict[str, object] = {
        "id": cid,
        "number": cid,
        "localization_keys": (_write_test_label(f"Casilla {cid}"),),
        "section": ("liquidacion",),
        "data_type": "money",
        "semantic_role": f"importe_{cid}",
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    }
    if chain is not None:
        payload["continuidad_id"] = chain
    if origin is not None:
        payload["continuidad_origin"] = origin.value
        if origin.requires_evidence:
            payload["continuidad_evidence"] = _EVIDENCE
    return CasillaDefinition.model_validate(payload)


def _modelo(*editions: list[CasillaDefinition], last_declares_no_predecessor: bool = False) -> ModeloDefinition:
    revisions: dict[str, ModeloRevision] = {}
    for offset, casillas in enumerate(editions):
        year = 2023 + offset
        payload: dict[str, object] = {
            "id": str(year),
            "localization_key": f"test.schema.revision.{year}.label",
            "valid_from": date(year, 1, 1),
            "period_selector": PeriodSelector(years=(year,), periods=("0A",)),
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual",),
            "casillas": tuple(casillas),
        }
        if last_declares_no_predecessor and offset == len(editions) - 1:
            payload["predecessor"] = _NO_PREDECESSOR
        revisions[str(year)] = ModeloRevision.model_validate(payload)
    return ModeloDefinition.model_validate(
        {
            "id": _MODELO,
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


def _key(revision: str, casilla: str, modelo: str = _MODELO) -> CasillaRowKey:
    return CasillaRowKey(modelo=modelo, revision=revision, casilla=casilla)


_PREDECESSOR = [_row("06", chain="base")]


def test_a_successor_row_with_neither_lineage_nor_a_none_is_uncovered() -> None:
    modelo = _modelo(_PREDECESSOR, [_row("07")])
    report = lineage_totality([modelo], ())
    assert report.uncovered == (_key("2024", "07"),)
    assert not report.is_total


def test_a_successor_row_whose_id_the_predecessor_carries_resolves() -> None:
    modelo = _modelo(_PREDECESSOR, [_row("07", chain="base")])
    assert lineage_totality([modelo], ()).is_total


def test_an_id_starting_its_chain_in_a_successor_edition_is_unresolved() -> None:
    modelo = _modelo(_PREDECESSOR, [_row("07", chain="nueva")])
    assert unresolved_successor_rows(modelo) == (_key("2024", "07"),)


@pytest.mark.parametrize(
    "origin",
    [
        CasillaLineageOrigin.NEW_ON_FORM,
        CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT,
        CasillaLineageOrigin.NOT_ON_FORM,
    ],
)
def test_an_absence_origin_declares_its_kind_of_none(origin: CasillaLineageOrigin) -> None:
    chain = "nueva" if origin is not CasillaLineageOrigin.NEW_ON_FORM else None
    declared = _modelo(_PREDECESSOR, [_row("07", chain=chain, origin=origin)])
    undeclared = _modelo(_PREDECESSOR, [_row("07", chain=chain)])
    assert unresolved_successor_rows(declared) == ()
    assert unresolved_successor_rows(undeclared) == (_key("2024", "07"),)


def test_a_declared_continuation_origin_carries_lineage() -> None:
    modelo = _modelo(_PREDECESSOR, [_row("06", chain="base", origin=CasillaLineageOrigin.SEEDED)])
    assert unresolved_successor_rows(modelo) == ()


def test_the_first_edition_is_never_judged() -> None:
    assert unresolved_successor_rows(_modelo([_row("06")], [_row("06", chain="x")])) == (_key("2024", "06"),)
    assert unresolved_successor_rows(_modelo([_row("06")])) == ()


def test_an_edition_declaring_no_predecessor_is_not_judged() -> None:
    declared = _modelo(_PREDECESSOR, [_row("07")], last_declares_no_predecessor=True)
    assert unresolved_successor_rows(declared) == ()
    assert unresolved_successor_rows(_modelo(_PREDECESSOR, [_row("07")])) == (_key("2024", "07"),)


def test_only_the_adjacent_predecessor_edition_resolves_an_id() -> None:
    modelo = _modelo(_PREDECESSOR, [_row("08")], [_row("09", chain="base")])
    assert unresolved_successor_rows(modelo) == (_key("2024", "08"), _key("2025", "09"))


def test_an_exception_keyed_to_the_unresolved_row_covers_it() -> None:
    modelo = _modelo(_PREDECESSOR, [_row("07"), _row("08")])
    covered = lineage_totality([modelo], {_key("2024", "07")})
    assert covered.uncovered == (_key("2024", "08"),)
    assert covered.stale == ()
    assert lineage_totality([modelo], {_key("2024", "07"), _key("2024", "08")}).is_total


def test_an_exception_for_a_row_that_now_carries_lineage_is_stale() -> None:
    exception = {_key("2024", "07")}
    resolved = lineage_totality([_modelo(_PREDECESSOR, [_row("07", chain="base")])], exception)
    still_unresolved = lineage_totality([_modelo(_PREDECESSOR, [_row("07")])], exception)
    assert resolved.stale == (_key("2024", "07"),)
    assert not resolved.is_total
    assert still_unresolved.is_total


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(_key("2024", "99"), id="row-removed"),
        pytest.param(_key("2023", "06"), id="first-edition-row"),
        pytest.param(_key("2024", "07", modelo="999"), id="modelo-outside-corpus"),
    ],
)
def test_an_exception_naming_no_unresolved_row_is_stale(exception: CasillaRowKey) -> None:
    modelo = _modelo(_PREDECESSOR, [_row("07")])
    report = lineage_totality([modelo], {_key("2024", "07"), exception})
    assert report.stale == (exception,)
    assert report.uncovered == ()
