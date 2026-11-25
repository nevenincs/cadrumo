"""Detector teeth: no Modelo 100 credit casilla may take its value from the borrador.

The live corpus holds every credit binding a borrador snapshot may hold as
``cross_check_only``. A COPY of the live Modelo 100 tree is compiled through the
mutable loader with one credit binding flipped to ``precedence``; the binding
registration section must then refuse it, while the untouched copy passes.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.binding_borrador_participation import BorradorParticipation
from cadrumo.domain.calculations.registry.retencion_soportada_bindings import credit_casilla_ids
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    revision_covering,
)

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_bindings import validate_binding_registration_section

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELOS_ROOT = Path(__file__).resolve().parents[3] / "src" / "cadrumo" / "_data" / "registry" / "aeat" / "modelos"
_BASELINE = str(revision_covering("100", filing_year_envelope().floor).id)
_INHERITING = str(authored_revisions("100")[-1].id)
_CREDIT_BINDING = "renta-retencion-soportada-trabajo"
_CROSS_CHECK_LINE = 'borrador_participation = "cross_check_only"'


def _copy(tmp_path: Path) -> Path:
    destination = tmp_path / "100"
    shutil.copytree(_MODELOS_ROOT / "100", destination)
    return destination


def _flip_to_precedence(tree: Path) -> None:
    anchor = f'id = "{_CREDIT_BINDING}"'
    (path,) = [p for p in sorted(tree.rglob("*.toml")) if anchor in p.read_text(encoding="utf-8")]
    text = path.read_text(encoding="utf-8")
    declaration = text.index(anchor)
    headers = [match.start() for match in re.finditer(r"^\[\[revisions\.", text, re.MULTILINE)]
    end = min((position for position in headers if position > declaration), default=len(text))
    row = text[declaration:end]
    assert row.count(_CROSS_CHECK_LINE) == 1, row
    path.write_text(
        text[:declaration] + row.replace(_CROSS_CHECK_LINE, 'borrador_participation = "precedence"') + text[end:],
        encoding="utf-8",
    )


def _failures(tree: Path, revision_id: str) -> list[str]:
    revision = load_modelo_directory(tree).revisions[revision_id]
    return validate_binding_registration_section(prefix=f"modelo 100 revision {revision_id}", revision=revision)


def test_every_borrador_held_credit_binding_is_cross_check_only_and_the_tree_passes(tmp_path: Path) -> None:
    tree = _copy(tmp_path)
    for revision_id in (_BASELINE, _INHERITING):
        revision = load_modelo_directory(tree).revisions[revision_id]
        credits = credit_casilla_ids(revision)
        held = [
            binding
            for binding in revision.bindings
            if binding.aeat_prefilled
            and any(casilla.binding == binding.id and casilla.id in credits for casilla in revision.casillas)
        ]
        assert {binding.id for binding in held} >= {_CREDIT_BINDING}, revision_id
        assert all(binding.borrador_participation is BorradorParticipation.CROSS_CHECK_ONLY for binding in held)
        assert _failures(tree, revision_id) == [], revision_id


def test_a_credit_binding_flipped_to_borrador_precedence_is_refused_in_every_inheriting_revision(
    tmp_path: Path,
) -> None:
    tree = _copy(tmp_path)
    _flip_to_precedence(tree)
    for revision_id in (_BASELINE, _INHERITING):
        failures = [failure for failure in _failures(tree, revision_id) if _CREDIT_BINDING in failure]
        assert any("reaches credit casilla(s) ['0596']" in failure for failure in failures), failures
        assert any("cannot be marked aeat_prefilled with borrador precedence" in failure for failure in failures)
