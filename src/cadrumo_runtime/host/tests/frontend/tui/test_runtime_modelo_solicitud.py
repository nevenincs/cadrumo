"""The installed solicitud door reads its facts file as the command line's document does."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.filing.producer_snapshot_m360 import M360TitularEnCalidadDe
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import tr
from cadrumo.entrypoints.tui.modelo.tests.solicitud_360_fixtures import synthetic_facts_json

from ....frontend.tui.runtime_modelo_solicitud import read_solicitud_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]


def test_a_facts_file_validates_into_the_public_input(tmp_path: Path) -> None:
    path = tmp_path / "facts.json"
    path.write_text(synthetic_facts_json(M360TitularEnCalidadDe.SOLICITANTE), encoding=UTF_8_ENCODING)

    facts = read_solicitud_facts(str(path))

    assert facts.solicitud.pais_destino == "FR"
    assert facts.representante is None


def test_an_absent_file_is_refused_by_name_without_its_content(tmp_path: Path) -> None:
    absent = str(tmp_path / "absent.json")

    with pytest.raises(ValueError, match=r"absent.json") as refused:
        read_solicitud_facts(absent)

    assert str(refused.value) == tr("tui.modelo.m360_solicitud.source_unreadable", path=absent)


def test_an_invalid_file_is_refused_with_a_count_and_never_echoes_its_content(tmp_path: Path) -> None:
    path = tmp_path / "facts.json"
    path.write_text('{"cuenta": {"titular_nombre": "TITULAR PRUEBA"}}', encoding=UTF_8_ENCODING)

    with pytest.raises(ValueError, match=r"facts.json") as refused:
        read_solicitud_facts(str(path))

    assert "TITULAR PRUEBA" not in str(refused.value)
