"""Non-ASCII header round-trip invariant per encoding (wave 127).

Kent's APELLIDOS / NOMBRE often contain Spanish tildes and
accents (ñ, á, é, í, ó, ú, ü plus their upper-case variants,
and ¡ ¿ punctuation). The fichero-BOE serialiser + deserialiser
pair must round-trip these characters losslessly under both
encodings we ship:

- **cp1252** (Modelo 130) — full Western-European superset;
  includes the Euro sign (€) at position 0x80.
- **iso-8859-1** (Modelo 303) — base Latin-1; does NOT define
  the Euro sign, so any € in a 303 header must fail loud at
  encode time rather than silently mojibake into ``?``.

Wave 127 locks these invariants end-to-end.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ._deserialise import deserialise, deserialise_envelope
from ._serialise import serialise, serialise_envelope
from ._test_fixtures import KENT_130_CASILLAS, kent_130_headers, kent_303_headers
from .modelo_130_2024 import (
    ENCODING as ENCODING_130,
)
from .modelo_130_2024 import (
    RECORD_LENGTH,
    RECORD_SPECS,
)
from .modelo_130_2024 import (
    REQUIRED_HEADER_FIELDS as REQUIRED_130,
)
from .modelo_303_2024 import (
    ENCODING as ENCODING_303,
)
from .modelo_303_2024 import (
    ENVELOPE,
)
from .modelo_303_2024 import (
    REQUIRED_HEADER_FIELDS as REQUIRED_303,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


#: Characters both encodings support and Kent may reasonably file with.
_LATIN1_SAFE_SAMPLES: list[str] = [
    "MUÑOZ ÑAÑEZ",
    "GARCÍA LÓPEZ",
    "PÉREZ RODRÍGUEZ",
    "MARTÍN ÚBEDA",
    "HERNÁNDEZ FRÖBEL",  # ö is in both
    "¡HOLA! ¿QUÉ TAL?",  # Spanish inverted punctuation
]

#: Characters cp1252 supports but iso-8859-1 does NOT. A 303 filing
#: must refuse to encode these rather than drop or mojibake them.
_CP1252_ONLY_SAMPLES: list[str] = [
    "CAFÉ €15",  # Euro sign
    "ESPAÑA ™",  # Trade-mark
    "RESUMEN: •",  # Bullet
]


class TestModelo130AccentedRoundTrip:
    @pytest.mark.parametrize("apellidos", _LATIN1_SAFE_SAMPLES, ids=lambda v: v.replace(" ", "_"))
    def test_130_preserves_spanish_accents(self, apellidos: str) -> None:
        headers = kent_130_headers("2024") | {"APELLIDOS": apellidos}
        payload = serialise(
            casilla_values=KENT_130_CASILLAS,
            headers=headers,
            specs=RECORD_SPECS,
            encoding=ENCODING_130,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_130,
        )
        parsed = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING_130, total_length=RECORD_LENGTH)
        # APELLIDOS is space-padded to 30 bytes; the decoder strips trailing
        # spaces for LEFT justification, so compare against the trimmed input.
        assert parsed.field_values["APELLIDOS"] == apellidos.rstrip()

    @pytest.mark.parametrize("apellidos", _CP1252_ONLY_SAMPLES, ids=lambda v: v.replace(" ", "_"))
    def test_130_accepts_cp1252_only_characters(self, apellidos: str) -> None:
        """cp1252 supports the extended Western-European range; 130 round-trips
        the Euro sign, trade-mark, etc. without drift."""
        headers = kent_130_headers("2024") | {"APELLIDOS": apellidos}
        payload = serialise(
            casilla_values=KENT_130_CASILLAS,
            headers=headers,
            specs=RECORD_SPECS,
            encoding=ENCODING_130,
            total_length=RECORD_LENGTH,
            required_field_ids=REQUIRED_130,
        )
        parsed = deserialise(payload, specs=RECORD_SPECS, encoding=ENCODING_130, total_length=RECORD_LENGTH)
        assert parsed.field_values["APELLIDOS"] == apellidos.rstrip()


class TestModelo303AccentedRoundTrip:
    @pytest.mark.parametrize("name", _LATIN1_SAFE_SAMPLES, ids=lambda v: v.replace(" ", "_"))
    def test_303_preserves_spanish_accents(self, name: str) -> None:
        headers = kent_303_headers("2024") | {
            "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": name,
        }
        payload = serialise_envelope(
            casilla_values={"07": Decimal("20000.00")},
            headers=headers,
            segments=ENVELOPE,
            encoding=ENCODING_303,
            required_field_ids=REQUIRED_303,
        )
        parsed = deserialise_envelope(payload, segments=ENVELOPE, encoding=ENCODING_303)
        apellidos_y_nombre = parsed.merged_field_values["DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N"]
        assert apellidos_y_nombre == name.rstrip()

    @pytest.mark.parametrize("name", _CP1252_ONLY_SAMPLES, ids=lambda v: v.replace(" ", "_"))
    def test_303_refuses_cp1252_only_characters(self, name: str) -> None:
        """iso-8859-1 does NOT define the Euro sign / trade-mark / bullet.
        A 303 filing must raise rather than emit mojibake."""
        headers = kent_303_headers("2024") | {
            "DP30301_F008_IDENTIFICACI_N_APELLIDOS_Y_N": name,
        }
        with pytest.raises((UnicodeEncodeError, ValueError)):
            serialise_envelope(
                casilla_values={"07": Decimal("20000.00")},
                headers=headers,
                segments=ENVELOPE,
                encoding=ENCODING_303,
                required_field_ids=REQUIRED_303,
            )
