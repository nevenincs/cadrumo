"""An inherited casilla keeps a label: the catalogue inherits alongside the row.

Enrolment keys an inherited row to the edition it now sits in, but the label
catalogue holds the row's text only under the key of the edition that stated
it. These tests drive the real directory loader and the production label
accessor, against the real shared catalogue, and check that the stated
edition's occurrence key joins the row's resolution chain, that a chain
propagates that origin rather than the immediate predecessor, that an
edition's own keys are exactly what restating the row would have produced
plus that one fallback, and that a chain resolving nowhere still raises.

The catalogue entry the label comes from is a real one, found at runtime: a
modelo, edition and casilla whose occurrence key carries Spanish text. The
successor editions are years no corpus edition uses, so their own occurrence
keys carry nothing and any label they yield must have come through the
fallback.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

import pytest
from test_support.registry_authoring import load_modelo_directory

from .....core.i18n import MissingTranslationError, lookup_translation
from ..authority import bundled_authority
from ..errors import RegistryLoadError
from ..modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
)
from ..schema import ModeloDefinition
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-58-2003:art-29"
_SOURCE_REF = "aeat-manual"
_LABEL = ModeloLocalizationFieldKind.LABEL
_YEAR_EDITION = re.compile(r"^\d{4}$")
#: Editions no corpus modelo declares, so their occurrence keys have no catalogue entry.
_SUCCESSOR = "2091"
_SECOND_SUCCESSOR = "2092"
#: A casilla id no catalogue entry names under any edition.
_UNLABELLED_CASILLA = "zz-sin-etiqueta"
_LINEAGE = "linaje-heredado"


class _Witness(NamedTuple):
    """A real catalogue entry: Spanish text under one edition's occurrence key."""

    modelo_id: str
    revision_id: str
    casilla_id: str
    label: str


@cache
def _witness() -> _Witness:
    for modelo in bundled_authority().modelos:
        for revision in modelo.revisions.values():
            if not _YEAR_EDITION.fullmatch(revision.id) or int(revision.id) >= int(_SUCCESSOR):
                continue
            for casilla in revision.casillas:
                key = casilla_occurrence_locale_key(modelo.id, revision.id, casilla.id, _LABEL)
                label = lookup_translation(key, locale="es")
                if label is not None and label.strip():
                    return _Witness(modelo.id, revision.id, casilla.id, label)
    pytest.fail("no bundled casilla carries Spanish text under its own edition's occurrence key")


def _casilla(revision_id: str, casilla_id: str, *, number: str, lineage: str | None = None, alias: bool = False) -> str:
    lineage_line = f'continuidad_id = "{lineage}"\n' if lineage is not None else ""
    alias_block = (
        f'[[revisions."{revision_id}".casillas.aliases]]\n'
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
        if alias
        else ""
    )
    return (
        f'[[revisions."{revision_id}".casillas]]\n'
        f'id = "{casilla_id}"\n'
        f'number = "{number}"\n'
        'section = ["liquidacion"]\n'
        f"{lineage_line}"
        f'legal_refs = ["{_LEGAL_REF}"]\n'
        f'source_refs = ["{_SOURCE_REF}"]\n\n'
        f"{alias_block}"
    )


def _write_edition(modelo_dir: Path, revision_id: str, *, predecessor: str | None, casillas: str) -> None:
    year = int(revision_id)
    revision_dir = modelo_dir / "revisions" / revision_id
    revision_dir.mkdir(parents=True)
    predecessor_line = f'predecessor = "{predecessor}"\n' if predecessor is not None else ""
    (revision_dir / "revision.toml").write_text(
        (
            f'[revisions."{revision_id}"]\n'
            f"valid_from = {year}-01-01\n"
            f"valid_to = {year}-12-31\n"
            f'period_selector = {{ years = [{year}], periods = ["0A"] }}\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            f'source_refs = ["{_SOURCE_REF}"]\n'
            f"{predecessor_line}"
        ),
        encoding="utf-8",
        newline="\n",
    )
    if casillas:
        (revision_dir / "casillas").mkdir()
        (revision_dir / "casillas" / "0001-casillas.toml").write_text(casillas, encoding="utf-8", newline="\n")


def _modelo_dir(root: Path, modelo_id: str) -> Path:
    modelo_dir = root / modelo_id
    modelo_dir.mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(
        (
            "[modelo]\n"
            f'id = "{modelo_id}"\n'
            'tax_domain = "iva"\n'
            'cadence = "annual"\n'
            'jurisdiction = "ES-AEAT"\n'
            f'legal_refs = ["{_LEGAL_REF}"]\n'
            f'source_refs = ["{_SOURCE_REF}"]\n'
        ),
        encoding="utf-8",
        newline="\n",
    )
    return modelo_dir


def _casilla_of(modelo: ModeloDefinition, revision_id: str, casilla_id: str) -> CasillaDefinition:
    return next(casilla for casilla in modelo.revisions[revision_id].casillas if casilla.id == casilla_id)


def _occurrence(witness: _Witness, revision_id: str, casilla_id: str) -> str:
    return casilla_occurrence_locale_key(witness.modelo_id, revision_id, casilla_id, _LABEL)


def _chain_modelo(root: Path, witness: _Witness) -> ModeloDefinition:
    """The witness edition stating the witness row, then two successors inheriting it down a chain."""
    modelo_dir = _modelo_dir(root, witness.modelo_id)
    _write_edition(
        modelo_dir,
        witness.revision_id,
        predecessor=None,
        casillas=_casilla(witness.revision_id, witness.casilla_id, number="1")
        + _casilla(witness.revision_id, _UNLABELLED_CASILLA, number="2"),
    )
    _write_edition(modelo_dir, _SUCCESSOR, predecessor=witness.revision_id, casillas="")
    _write_edition(modelo_dir, _SECOND_SUCCESSOR, predecessor=_SUCCESSOR, casillas="")
    return load_modelo_directory(modelo_dir)


def test_an_inherited_row_without_lineage_takes_its_label_from_the_edition_that_last_stated_it(
    tmp_path: Path,
) -> None:
    witness = _witness()
    modelo = _chain_modelo(tmp_path, witness)

    for revision_id in (_SUCCESSOR, _SECOND_SUCCESSOR):
        casilla = _casilla_of(modelo, revision_id, witness.casilla_id)
        assert casilla.continuidad_id is None
        # The origin propagates: the second successor falls back to the edition
        # that stated the row, not to the first successor, which never did.
        assert casilla.localization_keys == (
            _occurrence(witness, revision_id, witness.casilla_id),
            _occurrence(witness, witness.revision_id, witness.casilla_id),
        )
        assert casilla.get_label("es") == witness.label


def test_the_inherited_label_is_lost_without_the_origin_fallback(tmp_path: Path) -> None:
    witness = _witness()
    inherited = _casilla_of(_chain_modelo(tmp_path, witness), _SECOND_SUCCESSOR, witness.casilla_id)
    fallback = _occurrence(witness, witness.revision_id, witness.casilla_id)
    without_fallback = inherited.model_copy(
        update={"localization_keys": tuple(key for key in inherited.localization_keys if key != fallback)},
    )

    assert without_fallback.localization_keys == (_occurrence(witness, _SECOND_SUCCESSOR, witness.casilla_id),)
    with pytest.raises(MissingTranslationError):
        without_fallback.get_label("es")


def test_an_inherited_row_resolving_under_neither_key_still_raises(tmp_path: Path) -> None:
    witness = _witness()
    inherited = _casilla_of(_chain_modelo(tmp_path, witness), _SECOND_SUCCESSOR, _UNLABELLED_CASILLA)

    assert inherited.localization_keys[1] == _occurrence(witness, witness.revision_id, _UNLABELLED_CASILLA)
    with pytest.raises(MissingTranslationError):
        inherited.get_label("es")


def _restated_or_inherited(root: Path, witness: _Witness, *, migrated: bool) -> ModeloDefinition:
    """The successor either restates both witness-edition rows or names the edition and states neither."""
    modelo_dir = _modelo_dir(root, witness.modelo_id)
    rows = _casilla(witness.revision_id, witness.casilla_id, number="1") + _casilla(
        witness.revision_id, _UNLABELLED_CASILLA, number="2", lineage=_LINEAGE
    )
    _write_edition(modelo_dir, witness.revision_id, predecessor=None, casillas=rows)
    restated = _casilla(_SUCCESSOR, witness.casilla_id, number="1") + _casilla(
        _SUCCESSOR, _UNLABELLED_CASILLA, number="2", lineage=_LINEAGE
    )
    _write_edition(
        modelo_dir,
        _SUCCESSOR,
        predecessor=witness.revision_id if migrated else None,
        casillas="" if migrated else restated,
    )
    return load_modelo_directory(modelo_dir)


def test_a_migrated_edition_keeps_its_pre_migration_keys_and_adds_only_the_origin_fallback(tmp_path: Path) -> None:
    witness = _witness()
    before = _restated_or_inherited(tmp_path / "before", witness, migrated=False).revisions[_SUCCESSOR]
    after = _restated_or_inherited(tmp_path / "after", witness, migrated=True).revisions[_SUCCESSOR]
    own_plain = _occurrence(witness, _SUCCESSOR, witness.casilla_id)
    own_lineage = _occurrence(witness, _SUCCESSOR, _UNLABELLED_CASILLA)
    continuity = casilla_continuity_locale_key(witness.modelo_id, _LINEAGE, _LABEL)

    assert [casilla.localization_keys for casilla in before.casillas] == [(own_plain,), (own_lineage, continuity)]
    # The successor's own keys stay first and in order; the stated edition's
    # occurrence key sits between the exact key and the lineage-wide key.
    assert [casilla.localization_keys for casilla in after.casillas] == [
        (own_plain, _occurrence(witness, witness.revision_id, witness.casilla_id)),
        (own_lineage, _occurrence(witness, witness.revision_id, _UNLABELLED_CASILLA), continuity),
    ]
    assert after.casillas[0].get_label("es") == witness.label


def test_a_row_the_successor_states_gets_no_fallback(tmp_path: Path) -> None:
    witness = _witness()
    modelo_dir = _modelo_dir(tmp_path, witness.modelo_id)
    _write_edition(
        modelo_dir,
        witness.revision_id,
        predecessor=None,
        casillas=_casilla(witness.revision_id, witness.casilla_id, number="1", lineage=_LINEAGE),
    )
    _write_edition(
        modelo_dir,
        _SUCCESSOR,
        predecessor=witness.revision_id,
        casillas=_casilla(_SUCCESSOR, witness.casilla_id, number="11", lineage=_LINEAGE),
    )
    superseding = _casilla_of(load_modelo_directory(modelo_dir), _SUCCESSOR, witness.casilla_id)

    assert superseding.number == "11"
    assert superseding.localization_keys == (
        _occurrence(witness, _SUCCESSOR, witness.casilla_id),
        casilla_continuity_locale_key(witness.modelo_id, _LINEAGE, _LABEL),
    )


def test_an_inherited_row_carrying_aliases_is_refused_and_loads_once_stated(tmp_path: Path) -> None:
    witness = _witness()
    for migrated_row_stated in (False, True):
        modelo_dir = _modelo_dir(tmp_path / str(migrated_row_stated), witness.modelo_id)
        _write_edition(
            modelo_dir,
            witness.revision_id,
            predecessor=None,
            casillas=_casilla(witness.revision_id, witness.casilla_id, number="1", lineage=_LINEAGE, alias=True),
        )
        _write_edition(
            modelo_dir,
            _SUCCESSOR,
            predecessor=witness.revision_id,
            casillas=(
                _casilla(_SUCCESSOR, witness.casilla_id, number="1", lineage=_LINEAGE, alias=True)
                if migrated_row_stated
                else ""
            ),
        )
        if migrated_row_stated:
            stated = _casilla_of(load_modelo_directory(modelo_dir), _SUCCESSOR, witness.casilla_id)
            assert len(stated.aliases) == 1
        else:
            with pytest.raises(RegistryLoadError, match=r"carries aliases"):
                load_modelo_directory(modelo_dir)
