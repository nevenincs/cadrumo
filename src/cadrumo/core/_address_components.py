"""The canonical component vocabulary an AEAT address slot may be named from.

AEAT reuses one address grammar across forms, and every modelo that carries an
address carries the same components under the same Spanish names. What it does
NOT do is carry them all in the same shape: Modelo 210 identifies the municipio
by its five-digit INE code and the provincia by its two-digit code, while Modelo
360 writes the municipio's NAME in thirty characters and the provincia as text.
Thirteen of the fifteen components agree; two do not.

So this is a vocabulary, deliberately not a shared address type. Merging the two
shapes would assert they are interchangeable, and they are not -- a name does not
fit a code slot, and the constraint set of one is not a superset of the other's.
What the vocabulary prevents is the OTHER failure: a third modelo inventing
``street_name`` beside ``nombre_via``, or ``zip`` beside ``postal_code``, so that
the same official component acquires two registry spellings and neither is
findable from the other.

Each party scope in :class:`~core.FilingProducerKey` still declares its own flat
members; this only fixes what those members' leaves may be called.
"""

from __future__ import annotations

from typing import Final

#: Components of the Spanish-coded address AEAT prints as a decomposed via.
#: Both municipio and provincia variants are listed because both are real: a
#: design asks for the INE code or for the name, and the two are not the same
#: fact rendered differently.
SPANISH_ADDRESS_COMPONENTS: Final[frozenset[str]] = frozenset(
    {
        "tipo_via",
        "nombre_via",
        "tipo_numeracion",
        "numero_casa",
        "calificador_numero",
        "bloque",
        "portal",
        "escalera",
        "planta",
        "puerta",
        "datos_complementarios",
        "localidad",
        "codigo_postal",
        "codigo_ine_municipio",
        "nombre_municipio",
        "codigo_provincia",
        "provincia",
        "referencia_catastral",
    },
)

#: Components of a FOREIGN address, which AEAT writes as free text with a ZIP and
#: a region name rather than the coded Spanish decomposition.
FOREIGN_ADDRESS_COMPONENTS: Final[frozenset[str]] = frozenset(
    {
        "street",
        "complement",
        "city",
        "email",
        "postal_code",
        "region",
        "country_code",
        "phone",
        "mobile_phone",
        "fax",
    },
)

#: The infixes that mark a producer key as addressing one of the two shapes.
#: A key is Spanish-coded when its path carries ``domicilio`` or ``situacion``,
#: and foreign when it carries ``foreign_address``.
SPANISH_ADDRESS_INFIXES: Final[frozenset[str]] = frozenset({"domicilio", "situacion"})
FOREIGN_ADDRESS_INFIX: Final[str] = "foreign_address"

__all__ = [
    "FOREIGN_ADDRESS_COMPONENTS",
    "FOREIGN_ADDRESS_INFIX",
    "SPANISH_ADDRESS_COMPONENTS",
    "SPANISH_ADDRESS_INFIXES",
]
