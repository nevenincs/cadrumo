"""Generate synthetic AEAT submitted-file fixtures.

The one real submitted declaration in this tree is redacted, and its redactor
assigned placeholders by field POSITION rather than by casilla. Two rows
carrying the same casilla therefore receive different placeholders by
construction -- in ``modelo-100-2023-0A-redacted.xml`` casilla ``0435`` reads
``45.45`` in ``BIGRALH`` and ``47.47`` in ``BIGRALJ``. So no redacted artefact
can ever exercise the case where a casilla's two declared rows AGREE, which is
the normal case for AEAT's carry fields.

That is a property of redaction rather than of this particular file: redaction
destroys relationships between fields, not only their values. Any question about
how two fields relate is unanswerable from a redacted artefact by construction.

Hence this generator. The carry values here are authored directly rather than
produced by rendering a draft, because a fixture emitted by our own writer would
carry agreeing rows by construction and could only prove the writer
self-consistent. Authoring them keeps the fixture honest evidence for the
reading side.

The element ordering mirrors the real submission, whose sequence is AEAT's own.
The ``Aux`` block is included because the schema declares it mandatory
(``minOccurs=1``) and real submissions carry it, even though no bundled
dictionary declares its rows.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_HERE = Path(__file__).parent
_SUBMITTED = _HERE / "submitted-files"

# Casilla 0435 (base imponible general) and 0460 (base imponible del ahorro)
# each address two rows: one in BaseImponibleRes, one carried into
# BaseLiquidableRes. AEAT's own dictionary instructs "traslade el importe de
# esta casilla", so the two rows agree in a genuine filing.
_BASE_IMPONIBLE_GENERAL = "12345.67"
_BASE_IMPONIBLE_AHORRO = "2345.67"

_CARRY_AGREEMENT_XML = (
    "<?xml version='1.0' encoding='utf-8'?>\n"
    '<Declaracion xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
    ' modelo="100" ejercicio="2024" periodo="0A" versionxsd="1.02">'
    "<Aux><Idioma>C</Idioma><VERSION>1.02</VERSION><NIF_EEDD>00000000T</NIF_EEDD></Aux>"
    "<DatosEconomicos><Resultados>"
    "<BaseImponibleRes>"
    f"<BIGRALH>{_BASE_IMPONIBLE_GENERAL}</BIGRALH>"
    f"<BIAHOH>{_BASE_IMPONIBLE_AHORRO}</BIAHOH>"
    "</BaseImponibleRes>"
    "<BaseLiquidableRes>"
    f"<BIGRALJ>{_BASE_IMPONIBLE_GENERAL}</BIGRALJ>"
    f"<BIAHOJ>{_BASE_IMPONIBLE_AHORRO}</BIAHOJ>"
    "</BaseLiquidableRes>"
    "</Resultados></DatosEconomicos>"
    "</Declaracion>"
)

_CARRY_AGREEMENT_NAME = "modelo-100-2024-0A-carry-agreement-synthetic.xml"


def write_carry_agreement_fixture() -> Path:
    """Write the carry-agreement fixture and its provenance sidecar."""
    payload = _CARRY_AGREEMENT_XML.encode("utf-8")
    target = _SUBMITTED / _CARRY_AGREEMENT_NAME
    target.write_bytes(payload)

    sidecar = target.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "output_sha256": hashlib.sha256(payload).hexdigest(),
                "output_size_bytes": len(payload),
                "provenance": "synthetic_generated",
                "role": "carry_agreement",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    written = write_carry_agreement_fixture()
    print(f"wrote {written}")
