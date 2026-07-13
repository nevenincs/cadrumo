"""OSS / IOSS regime substrate for the Modelo 369 autoliquidation chain.

Closes the regime taxonomy gap surfaced by the Modelo 369 IVA
centralization audit. Three closed enumerations (:class:`OssIossRegime`,
:class:`IossFilerRole`, :class:`DeductionScope`), the regime ↔ filing
periodicity mapping (:data:`REGIME_PERIODICITY`), and the
LIVA-grounded deductibility predicate
(:func:`regime_allows_deduction`) live here. The substrate is purely
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

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


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


class IossFilerRole(StrEnum):
    """Closed enumeration of IOSS filer roles defined by HAC/610/2021 art. 2.

    Letters (c) and (d) of HAC/610/2021 art. 2 split the IOSS regime
    into two filer roles. Both file monthly under
    :attr:`OssIossRegime.IMPORT_SCHEME`; the role distinction flows
    into Modelo 369 binding selectors so per-empresario aggregation
    can be represented for intermediarios.

    Attributes:
        DIRECT: Sujeto pasivo acogido al régimen IOSS sin intermediario,
            cuyo Estado miembro de identificación es España. Files one
            autoliquidación per natural calendar month. HAC/610/2021
            art. 2 letter (c).
        INTERMEDIARIO: Intermediario establecido en el territorio de
            aplicación del impuesto que actúa por cuenta de empresarios
            o profesionales acogidos al IOSS. Files one autoliquidación
            per natural calendar month per empresario representado.
            HAC/610/2021 art. 2 letter (d).
    """

    DIRECT = "direct"
    INTERMEDIARIO = "intermediario"


class DeductionScope(StrEnum):
    """Closed enumeration of scopes against which deductibility is asked.

    The three regimes share the same operative rule for the autoliquidación
    itself — deduction is denied — but recovery is allowed elsewhere. The
    scope discriminates between the three places the question can be asked.

    Attributes:
        WITHIN_MODELO_369_AUTOLIQUIDATION: The deduction is being
            attempted inside the Modelo 369 declaration-liquidation. The
            three deduction articles (163 vicies, 163 tervicies, 163
            octovicies) all forbid this.
        ESTABLECIDO_REGULAR_IVA_RETURN: The deduction is being attempted
            in the operator's regular IVA return (typically Modelo 303),
            available to operators that are establecidos in a Member
            State for IVA purposes. Permitted by the three articles for
            establecido operators.
        NON_ESTABLECIDO_DIRECTIVE_PROCEDURE: The deduction is being
            attempted via the Eighth or Thirteenth Directive procedure
            available to non-establecidos. Permitted by the three
            articles for non-establecido operators.
    """

    WITHIN_MODELO_369_AUTOLIQUIDATION = "within_modelo_369_autoliquidation"
    ESTABLECIDO_REGULAR_IVA_RETURN = "establecido_regular_iva_return"
    NON_ESTABLECIDO_DIRECTIVE_PROCEDURE = "non_establecido_directive_procedure"


class RegimePeriodicity(StrEnum):
    """Closed enumeration of regime filing cadences."""

    QUARTERLY = "quarterly"
    MONTHLY = "monthly"


REGIME_PERIODICITY: Mapping[OssIossRegime, RegimePeriodicity] = MappingProxyType(
    {
        OssIossRegime.EXTERNAL_SCHEME: RegimePeriodicity.QUARTERLY,
        OssIossRegime.UNION_SCHEME: RegimePeriodicity.QUARTERLY,
        OssIossRegime.IMPORT_SCHEME: RegimePeriodicity.MONTHLY,
    },
)
"""Filing cadence per regime per HAC/610/2021 art. 2.

Article 2 letters (a) and (b) declare quarterly cadence for Esquemas
Exterior and Unión; letters (c) and (d) declare monthly cadence for
the IOSS regime irrespective of filer role.
"""


def regime_allows_deduction(regime: OssIossRegime, scope: DeductionScope) -> bool:
    """Return whether ``regime`` allows IVA deduction against ``scope``.

    Anchored to LIVA art. 163 vicies (Exterior), art. 163 tervicies
    (Unión), and art. 163 octovicies (IOSS). The three articles share
    the same operative structure: the sujeto pasivo "no podrá deducir
    en la declaración-liquidación... cantidad alguna por las cuotas
    soportadas" inside the Modelo 369 autoliquidation; recovery is
    routed through the regular IVA return for establecidos and through
    the Eighth / Thirteenth Directive procedures for non-establecidos.

    Args:
        regime: The OSS / IOSS regime against which deductibility is
            evaluated.
        scope: The procedural surface on which the deduction is being
            attempted.

    Returns:
        ``False`` for :attr:`DeductionScope.WITHIN_MODELO_369_AUTOLIQUIDATION`
        for every regime; ``True`` for
        :attr:`DeductionScope.ESTABLECIDO_REGULAR_IVA_RETURN` and
        :attr:`DeductionScope.NON_ESTABLECIDO_DIRECTIVE_PROCEDURE` for
        every regime, since the three articles allow recovery via those
        procedures.
    """
    if scope is DeductionScope.WITHIN_MODELO_369_AUTOLIQUIDATION:
        return False
    return regime in {
        OssIossRegime.EXTERNAL_SCHEME,
        OssIossRegime.UNION_SCHEME,
        OssIossRegime.IMPORT_SCHEME,
    }


__all__ = [
    "REGIME_PERIODICITY",
    "DeductionScope",
    "IossFilerRole",
    "OssIossRegime",
    "RegimePeriodicity",
    "regime_allows_deduction",
]
