"""Operation labels preserve the official A=purchases, B=supplies distinction."""

from pathlib import Path

import pytest

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("locale", "purchase", "supply"),
    [
        ("es", "A: adquisiciones", "B: entregas de bienes"),
        ("en", "A: purchases", "B: supplies of goods"),
        ("ca", "A: adquisicions", "B: lliuraments de béns"),
        ("hu", "A: beszerzések", "B: termékértékesítések"),
    ],
)
def test_operation_codes_keep_official_meaning(locale: str, purchase: str, supply: str) -> None:
    # Annex II, declarado operation code: both the 2011 and 2025 official designs.
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/347"))
    for revision in modelo.revisions.values():
        field = next(c for c in revision.casillas if c.id == "contraparte.clave-operacion")
        label = field.get_label(locale)
        assert purchase in label
        assert supply in label
