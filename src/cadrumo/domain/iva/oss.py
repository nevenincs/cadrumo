"""OSS / IOSS regime substrate for the Modelo 369 autoliquidation chain.

Closes the regime taxonomy gap surfaced by the Modelo 369 IVA
centralization audit. The closed :class:`OssIossRegime` and
:class:`DeductionScope` enumerations live here. The substrate is purely
additive against the wider :mod:`cadrumo.domain.iva` package; existing
rate values, classifier rules, and consumers remain unaffected.

The three regimes track the LIVA chapters that establish them:

* :attr:`OssIossRegime.EXTERNAL_SCHEME` — Régimen especial aplicable a
  los servicios prestados por sujetos pasivos no establecidos en la
  Comunidad. Articles 163 octiesdecies through 163 vicies.
* :attr:`OssIossRegime.UNION_SCHEME` — Régimen especial aplicable a las
  ventas intracomunitarias a distancia de bienes, a las entregas
  interiores de bienes facilitadas a través de interfaces electrónicas
  y a los servicios prestados por sujetos pasivos establecidos en la
  Comunidad pero no en el Estado miembro de consumo. Articles 163
  unvicies through 163 quatervicies.
* :attr:`OssIossRegime.IMPORT_SCHEME` — Régimen especial aplicable a
  las ventas a distancia de bienes importados procedentes de
  territorios o países terceros. Articles 163 quinvicies through
  163 octovicies.

Article 163 septiesdecies provides definitions common to all three
regimes (declaraciones-liquidaciones periódicas, Estado miembro de
consumo, Estado miembro de identificación).
"""

from __future__ import annotations

from enum import StrEnum


class OssIossRegime(StrEnum):
    """Closed enumeration of the three OSS / IOSS Esquemas covered by Modelo 369.

    Members are kebab-case lowercase strings to align with the
    ``selector.regime`` keys the registry binding shape declares for
    Modelo 369 ledger aggregations.

    Attributes:
        EXTERNAL_SCHEME: Régimen especial Exterior — services from
            non-EU taxable persons routed through Spain as Estado
            miembro de identificación. LIVA art. 163 octiesdecies
            through 163 vicies. Filing cadence is quarterly.
        UNION_SCHEME: Régimen especial Unión — intra-community
            distance sales of goods, interface-facilitated interior
            supplies, and services from EU-established suppliers to
            consumers in other Member States. LIVA art. 163 unvicies
            through 163 quatervicies. Filing cadence is quarterly.
        IMPORT_SCHEME: Régimen especial de Importación (IOSS) —
            distance sales of imported goods with intrinsic value at
            or below 150 EUR. LIVA art. 163 quinvicies through 163
            octovicies. Filing cadence is monthly.
    """

    EXTERNAL_SCHEME = "external_scheme"
    UNION_SCHEME = "union_scheme"
    IMPORT_SCHEME = "import_scheme"


__all__ = [
    "OssIossRegime",
]
