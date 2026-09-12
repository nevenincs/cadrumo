"""A casilla's lineage origin is a closed vocabulary with row-local coherence.

Each refusal below is a planted defect: the payload differs from a control that
validates only in the one field under test, so removing the rule it exercises
turns the test red rather than leaving it vacuously green.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..casilla_lineage import CasillaLineageOrigin
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE: dict[str, object] = {
    "id": "01",
    "number": "01",
    "localization_keys": ("modelo.schema.test.casilla.01.label",),
    "section": ("liquidacion",),
    "legal_refs": ("ley-35-2006:art-25",),
    "source_refs": ("aeat-dr-123-2024-v20",),
}
_EVIDENCE = "disenos_registro/modelo_123/files/example.txt:188 box [06]"


def _casilla(**updates: object) -> CasillaDefinition:
    return CasillaDefinition.model_validate({**_BASE, **updates})


def test_an_unmarked_row_makes_no_lineage_claim() -> None:
    casilla = _casilla()
    assert casilla.continuidad_origin is None
    assert casilla.continuidad_evidence is None


@pytest.mark.parametrize(
    ("origin", "continuidad_id", "evidence"),
    [
        (CasillaLineageOrigin.SEEDED, "base-retenciones", None),
        (CasillaLineageOrigin.GROUNDED, "base-retenciones", _EVIDENCE),
        (CasillaLineageOrigin.NEW_ON_FORM, None, _EVIDENCE),
        (CasillaLineageOrigin.NEW_ON_FORM, "starts-a-chain", _EVIDENCE),
        (CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT, None, _EVIDENCE),
        (CasillaLineageOrigin.NOT_ON_FORM, None, _EVIDENCE),
    ],
)
def test_every_coherent_origin_hydrates_from_its_toml_token(
    origin: CasillaLineageOrigin, continuidad_id: str | None, evidence: str | None
) -> None:
    casilla = _casilla(continuidad_origin=origin.value, continuidad_id=continuidad_id, continuidad_evidence=evidence)
    assert casilla.continuidad_origin is origin


def test_an_unknown_origin_token_is_refused_naming_the_accepted_set() -> None:
    with pytest.raises(
        ValidationError, match=r"not a recognised CasillaLineageOrigin member.*predecessor_edition_silent"
    ):
        _casilla(continuidad_origin="new", continuidad_evidence=_EVIDENCE)


def test_a_non_string_origin_is_refused() -> None:
    with pytest.raises(ValidationError, match="continuidad_origin must be a string"):
        _casilla(continuidad_origin=1)


@pytest.mark.parametrize("origin", [CasillaLineageOrigin.SEEDED, CasillaLineageOrigin.GROUNDED])
def test_a_continuation_without_a_chain_is_refused(origin: CasillaLineageOrigin) -> None:
    _casilla(continuidad_origin=origin.value, continuidad_id="chain", continuidad_evidence=_EVIDENCE)
    with pytest.raises(ValidationError, match="without continuidad_id"):
        _casilla(continuidad_origin=origin.value, continuidad_evidence=_EVIDENCE)


@pytest.mark.parametrize(
    "origin",
    [
        CasillaLineageOrigin.GROUNDED,
        CasillaLineageOrigin.NEW_ON_FORM,
        CasillaLineageOrigin.PREDECESSOR_EDITION_SILENT,
        CasillaLineageOrigin.NOT_ON_FORM,
    ],
)
def test_an_evidenced_origin_without_evidence_is_refused(origin: CasillaLineageOrigin) -> None:
    _casilla(continuidad_origin=origin.value, continuidad_id="chain", continuidad_evidence=_EVIDENCE)
    with pytest.raises(ValidationError, match="without continuidad_evidence"):
        _casilla(continuidad_origin=origin.value, continuidad_id="chain")


def test_evidence_without_an_origin_is_refused() -> None:
    with pytest.raises(ValidationError, match="continuidad_evidence without continuidad_origin"):
        _casilla(continuidad_evidence=_EVIDENCE)


def test_empty_evidence_is_refused() -> None:
    with pytest.raises(ValidationError, match="continuidad_evidence"):
        _casilla(continuidad_origin=CasillaLineageOrigin.NOT_ON_FORM.value, continuidad_evidence="")


def test_evidence_is_bounded_at_1024_characters() -> None:
    origin = CasillaLineageOrigin.NOT_ON_FORM.value
    at_cap = "x" * 1024
    assert _casilla(continuidad_origin=origin, continuidad_evidence=at_cap).continuidad_evidence == at_cap
    with pytest.raises(ValidationError, match="continuidad_evidence"):
        _casilla(continuidad_origin=origin, continuidad_evidence=at_cap + "x")
