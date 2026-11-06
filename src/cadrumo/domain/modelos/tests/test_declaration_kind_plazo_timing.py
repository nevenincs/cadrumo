"""Which declaration kinds a period's plazo can call late, and which it cannot.

Ley 58/2003 art. 122.1 lets an autoliquidación complementaria, or a declaración
or comunicación complementaria o sustitutiva, be presented inside the plazo
established for it or after that plazo ends, "siempre que no haya prescrito el
derecho de la Administración para determinar la deuda tributaria. En este
último caso tendrán el carácter de extemporáneas." Art. 27.1 attaches the
recargo to the presentation of an autoliquidación or declaración "fuera de
plazo sin requerimiento previo". So for an original, a complementaria and a
sustitutiva the lateness question is the same one: the period's own window
against the presentation date.

Art. 120.3 and the art. 120.4 added by Ley 13/2023 make the autoliquidación
rectificativa the vehicle of the rectification procedure, replacing the
solicitud de rectificación of an autoliquidación that harmed the taxpayer's
legitimate interests. Art. 122.1's extemporaneidad rule does not name it, and
no bundled official text says a rectificativa presented after the plazo is
thereby extemporánea. Its posture therefore stays unknown.

The classification is closed over the enum, so a new declaration kind has to be
classified deliberately rather than inheriting a default.
"""

from __future__ import annotations

import pytest

from ..filing_record import FilingDeclarationKind, declaration_kind_is_timed_against_the_plazo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TIMED_AGAINST_THE_PLAZO = {
    FilingDeclarationKind.ORIGINAL: True,
    FilingDeclarationKind.COMPLEMENTARIA: True,
    FilingDeclarationKind.SUSTITUTIVA: True,
    FilingDeclarationKind.RECTIFICATIVA: False,
}


def test_every_declaration_kind_is_classified() -> None:
    """No kind may fall through to an unstated default."""
    assert set(_TIMED_AGAINST_THE_PLAZO) == set(FilingDeclarationKind)


@pytest.mark.parametrize(("kind", "timed"), list(_TIMED_AGAINST_THE_PLAZO.items()), ids=lambda value: str(value))
def test_the_classification_matches_the_official_text(kind: FilingDeclarationKind, timed: bool) -> None:
    """Complementaria and sustitutiva are timed; the rectificativa is not."""
    assert declaration_kind_is_timed_against_the_plazo(kind) is timed
