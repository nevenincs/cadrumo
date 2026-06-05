"""Tests for the committed Modelo 151 (IRPF régimen impatriados / Beckham) registry foundation."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, RegistryValidator, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_151() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "151")
    return modelo, catalogues


def test_modelo_151_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_151()
    assert modelo.id == "151"
    assert modelo.revisions, "151 must declare at least one revision"
    assert any(rev.formulas for rev in modelo.revisions.values()), "151 must declare formulas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_151_revision_2015_declares_constructs() -> None:
    modelo, _ = _load_modelo_151()
    revision = modelo.revisions["2015-y-siguientes"]
    assert revision.constructs, "151 2015-y-siguientes revision must declare constructs"
    construct_ids = {c.id for c in revision.constructs}
    assert "m151-impatriado-calculation" in construct_ids


def test_modelo_151_revision_2015_formula_targets_resolve() -> None:
    modelo, _ = _load_modelo_151()
    revision = modelo.revisions["2015-y-siguientes"]
    impatriado = next(c for c in revision.constructs if c.id == "m151-impatriado-calculation")
    formula_ids = {f.id for f in revision.formulas}
    for declared_formula in impatriado.formulas:
        assert declared_formula in formula_ids, (
            f"construct lists formula {declared_formula!r} but the revision does not declare it"
        )


def test_modelo_151_legal_authority_is_ley_35_2006_art_93() -> None:
    """M151 is the Beckham regime (Ley 35/2006 art. 93 LIRPF)."""
    modelo, catalogues = _load_modelo_151()
    revision = modelo.revisions["2015-y-siguientes"]
    impatriado = next(c for c in revision.constructs if c.id == "m151-impatriado-calculation")
    assert "ley-35-2006:art-93" in impatriado.legal_refs
    assert "ley-35-2006:art-93" in catalogues.legal
