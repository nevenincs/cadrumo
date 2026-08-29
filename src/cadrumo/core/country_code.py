"""The two-letter country code carried across counterparty and jurisdiction facts.

AEAT identifies a counterparty's country, a perceptor's country of fiscal
residence and an income's source jurisdiction with an ISO 3166-1 alpha-2 code.
The shape was written out at twenty-two sites under the Spanish and English
field names both -- ``codigo_pais``, ``pais``, ``pais_residencia_fiscal``,
``country_code``, ``counterparty_country``, ``member_state_code``,
``source_jurisdiction`` -- each stating the same two-character bound.

The alias states LENGTH ONLY, which is what every site stated before it. It is
deliberately not strengthened to a letters-only pattern in the same change that
consolidates it: adding a charset check would refuse values the tree accepts
today, and whether it should is a separate ruling that deserves its own
evidence rather than riding in on a de-duplication.

Two neighbours are NOT this alias, and the distinction is load-bearing. The
registry's ``CountryCode`` layers a validator checking membership of the
AEAT-supported country list, so it is a superset and the sites here would be
loosened by adopting it. And a two-character field is not automatically a
country: ``tipo_renta``, ``subclave`` and ``codigo_provincia`` codes share the
length and mean something else entirely, so they keep their own declarations.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import StringConstraints

#: Every ISO 3166-1 alpha-2 code is exactly this long.
COUNTRY_CODE_LENGTH: Final[int] = 2

CountryCodeAlpha2 = Annotated[
    str,
    StringConstraints(min_length=COUNTRY_CODE_LENGTH, max_length=COUNTRY_CODE_LENGTH),
]
"""A two-letter country code, as AEAT states a jurisdiction on a filing."""

__all__ = ["COUNTRY_CODE_LENGTH", "CountryCodeAlpha2"]
