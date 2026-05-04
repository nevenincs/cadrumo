"""Hand-curated 2025 VAT regulation catalogue.

One :class:`aeat.domain.vat.VATRegulation` per
:class:`aeat.domain.vat.VATCategory`, each backed by at least two
:class:`aeat.domain.vat.VatCitation` records that quote (or faithfully
paraphrase) articles of **Ley 37/1992** (BOE-A-1992-28740). The catalogue is
the in-memory fallback used by
:func:`aeat.domain.vat.load_vat_rules_from_manual` when no on-disk year-keyed
catalogue is present.

The quoted Spanish text is a faithful paraphrase of the operative statutory
language where a verbatim extract would require copying multi-paragraph
blocks from the BOE. Auditability relies on the combination of
:attr:`aeat.domain.vat.VatCitation.source`,
:attr:`aeat.domain.vat.VatCitation.article` and
:attr:`aeat.domain.vat.VatCitation.quoted_text_es` — the quoted text is
sufficient to re-locate the article on boe.es and confirm the rule.

This module also exposes the period-keyed mapping
:data:`VAT_CATALOGUES_BY_YEAR` and the :func:`resolve_catalogue` helper.
Currently only the 2025 catalogue is populated; other years fall back to it
with a debug log line. The mapping infrastructure is in place so year-specific
catalogues can be slotted in without touching call sites.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from ...core.logging import get_logger
from ._schema import (
    VATCatalogue,
    VATCategory,
    VatCitation,
    VatCitationSource,
    VATRegulation,
)

_logger = get_logger(__name__)

_RETRIEVAL = date(2026, 4, 13)
_NORMATIVE_ID = "ley-37-1992"


def _cite(
    article: str,
    quoted_text_es: str,
    *,
    source: VatCitationSource = VatCitationSource.LEY_37_1992,
) -> VatCitation:
    """Shorthand builder for a :class:`VatCitation` against ``article``.

    Stamps every record with the module's :data:`_RETRIEVAL` date so the
    audit trail is consistent across the catalogue.

    Args:
        article: Free-form article reference (e.g. ``Art. 91.Uno``).
        quoted_text_es: Spanish quote or faithful paraphrase.
        source: Legal source enum value; defaults to
            :attr:`VatCitationSource.LEY_37_1992`.

    Returns:
        A frozen :class:`VatCitation` ready to embed in a
        :class:`VATRegulation`.
    """
    return VatCitation(
        source=source,
        article=article,
        url=None,
        quoted_text_es=quoted_text_es,
        retrieval_date=_RETRIEVAL,
    )


_DOMESTIC_GENERAL_21 = VATRegulation(
    category=VATCategory.DOMESTIC_GENERAL_21,
    label="vat.catalogue.label_365838",
    description="vat.catalogue.description_217010",
    triggers_when="vat.catalogue.triggers_when_142813",
    iva_treatment="vat.catalogue.iva_treatment_888336",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 90.Uno",
            "El impuesto se exigirá al tipo del 21 por ciento, salvo lo dispuesto en el artículo siguiente.",
        ),
        _cite(
            "Art. 4.Uno",
            (
                "Estarán sujetas al impuesto las entregas de bienes y prestaciones de servicios realizadas "
                "en el ámbito espacial del impuesto por empresarios o profesionales a título oneroso."
            ),
        ),
    ),
)


_DOMESTIC_REDUCED_10 = VATRegulation(
    category=VATCategory.DOMESTIC_REDUCED_10,
    label="vat.catalogue.label_027962",
    description="vat.catalogue.description_983244",
    triggers_when="vat.catalogue.triggers_when_029777",
    iva_treatment="vat.catalogue.iva_treatment_786939",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 91.Uno",
            (
                "Se aplicará el tipo del 10 por ciento a las operaciones siguientes: entregas, "
                "adquisiciones intracomunitarias e importaciones de los bienes que se indican a continuación."
            ),
        ),
        _cite(
            "Art. 91.Uno.2.1º",
            ("Los transportes de viajeros y sus equipajes tributarán al tipo del 10 por ciento."),
        ),
    ),
)


_DOMESTIC_SUPER_REDUCED_4 = VATRegulation(
    category=VATCategory.DOMESTIC_SUPER_REDUCED_4,
    label="vat.catalogue.label_915730",
    description="vat.catalogue.description_069076",
    triggers_when="vat.catalogue.triggers_when_352485",
    iva_treatment="vat.catalogue.iva_treatment_774580",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 91.Dos.1",
            (
                "Se aplicará el tipo del 4 por ciento a las operaciones siguientes: las entregas, "
                "adquisiciones intracomunitarias o importaciones de los bienes que se indican a continuación, "
                "entre ellos el pan común, las harinas panificables, la leche, los quesos, los huevos, "
                "las frutas, verduras, hortalizas, legumbres, tubérculos y cereales."
            ),
        ),
        _cite(
            "Art. 91.Dos.1.2º",
            (
                "Se aplicará el tipo del 4 por ciento a los libros, periódicos y revistas que no contengan "
                "única o fundamentalmente publicidad."
            ),
        ),
    ),
)


_DOMESTIC_ZERO = VATRegulation(
    category=VATCategory.DOMESTIC_ZERO,
    label="vat.catalogue.label_996028",
    description="vat.catalogue.description_640356",
    triggers_when="vat.catalogue.triggers_when_739440",
    iva_treatment="vat.catalogue.iva_treatment_872035",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 91.Dos.1.1º",
            (
                "Durante los períodos establecidos por las leyes transitorias, las entregas de determinados "
                "productos de primera necesidad tributan al tipo del 0 por ciento manteniendo el derecho a la "
                "deducción íntegra de las cuotas soportadas."
            ),
        ),
        _cite(
            "Art. 24.Uno",
            (
                "Estarán exentas, en las condiciones y con los requisitos que se establezcan reglamentariamente, "
                "las entregas de los bienes que, sin haber salido del territorio de aplicación del impuesto, "
                "se hallen vinculados al régimen de depósito distinto del aduanero."
            ),
        ),
    ),
)


_DOMESTIC_EXEMPT = VATRegulation(
    category=VATCategory.DOMESTIC_EXEMPT,
    label="vat.catalogue.label_342635",
    description="vat.catalogue.description_311472",
    triggers_when="vat.catalogue.triggers_when_049241",
    iva_treatment="vat.catalogue.iva_treatment_795653",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 20.Uno",
            (
                "Estarán exentas de este impuesto, entre otras, las prestaciones de servicios de hospitalización "
                "o asistencia sanitaria, la asistencia a personas físicas por profesionales médicos o sanitarios, "
                "la educación de la infancia y de la juventud, las operaciones financieras y las operaciones de "
                "seguro, reaseguro y capitalización."
            ),
        ),
        _cite(
            "Art. 20.Uno.22º",
            (
                "Estarán exentas las segundas y ulteriores entregas de edificaciones cuando tengan lugar después "
                "de terminada su construcción o rehabilitación, salvo renuncia expresa del sujeto pasivo."
            ),
        ),
    ),
)


_DOMESTIC_NOT_SUBJECT = VATRegulation(
    category=VATCategory.DOMESTIC_NOT_SUBJECT,
    label="vat.catalogue.label_385669",
    description="vat.catalogue.description_196978",
    triggers_when="vat.catalogue.triggers_when_425274",
    iva_treatment="vat.catalogue.iva_treatment_078140",
    declares_in_modelos=("303",),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 7.1º",
            (
                "No estarán sujetas al impuesto la transmisión de un conjunto de elementos corporales y, en su caso, "
                "incorporales que, formando parte del patrimonio empresarial del transmitente, constituyan o sean "
                "susceptibles de constituir una unidad económica autónoma en el transmitente, capaz de desarrollar una "
                "actividad empresarial por sus propios medios."
            ),
        ),
        _cite(
            "Art. 7.5º",
            (
                "No estarán sujetos los servicios prestados por personas físicas en régimen de dependencia derivada de "
                "relaciones administrativas o laborales."
            ),
        ),
    ),
)


_DOMESTIC_REVERSE_CHARGE = VATRegulation(
    category=VATCategory.DOMESTIC_REVERSE_CHARGE,
    label="vat.catalogue.label_198815",
    description="vat.catalogue.description_425875",
    triggers_when="vat.catalogue.triggers_when_234924",
    iva_treatment="vat.catalogue.iva_treatment_847858",
    declares_in_modelos=("303",),
    requires_reverse_charge=True,
    requires_supplier_vat_id=True,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 84.Uno.2º.f",
            (
                "Serán sujetos pasivos los empresarios o profesionales para quienes se realicen las operaciones "
                "consistentes en ejecuciones de obra, con o sin aportación de materiales, así como las cesiones "
                "de personal para su realización, consecuencia de contratos directamente formalizados entre el "
                "promotor y el contratista que tengan por objeto la urbanización de terrenos o la construcción "
                "o rehabilitación de edificaciones."
            ),
        ),
        _cite(
            "Art. 84.Uno.2º.c",
            (
                "Serán sujetos pasivos los empresarios o profesionales para quienes se realicen las entregas de "
                "los siguientes productos: desechos nuevos de la industria, desperdicios y desechos de fundición, "
                "residuos y demás materiales de recuperación constituidos por metales férreos y no férreos, sus "
                "aleaciones, escorias, cenizas y residuos de la industria que contengan metales o sus aleaciones."
            ),
        ),
        _cite(
            "Art. 84.Uno.2º.g",
            (
                "Serán sujetos pasivos los empresarios o profesionales para quienes se realicen las entregas de "
                "plata, platino y paladio, en bruto, en polvo o semilabrados; entregas de teléfonos móviles, "
                "consolas de videojuegos, ordenadores portátiles y tabletas digitales cuando el destinatario sea "
                "un empresario o profesional revendedor o supere los límites cuantitativos establecidos."
            ),
        ),
    ),
)


_INTRA_COMMUNITY_SUPPLY = VATRegulation(
    category=VATCategory.INTRA_COMMUNITY_SUPPLY,
    label="vat.catalogue.label_375372",
    description="vat.catalogue.description_170404",
    triggers_when="vat.catalogue.triggers_when_605383",
    iva_treatment="vat.catalogue.iva_treatment_816799",
    declares_in_modelos=("303", "349"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=True,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 25.Uno",
            (
                "Estarán exentas las entregas de bienes expedidos o transportados, por el vendedor, por el adquirente "
                "o por un tercero en nombre y por cuenta de cualquiera de los anteriores, al territorio de otro Estado "
                "miembro, siempre que el adquirente sea un empresario o profesional identificado a efectos del "
                "Impuesto sobre el Valor Añadido en un Estado miembro distinto del Reino de España."
            ),
        ),
        _cite(
            "Art. 164.Uno.3º",
            (
                "Los sujetos pasivos del impuesto estarán obligados a expedir y entregar factura de todas sus "
                "operaciones, ajustada a lo que se determine reglamentariamente."
            ),
        ),
    ),
)


_INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE = VATRegulation(
    category=VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    label="vat.catalogue.label_576993",
    description="vat.catalogue.description_027697",
    triggers_when="vat.catalogue.triggers_when_477522",
    iva_treatment="vat.catalogue.iva_treatment_373587",
    declares_in_modelos=("303", "349"),
    requires_reverse_charge=True,
    requires_supplier_vat_id=True,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 13.1º",
            (
                "Estarán sujetas las adquisiciones intracomunitarias de bienes efectuadas a título oneroso por "
                "empresarios, profesionales o personas jurídicas que no actúen como tales, cuando el transmitente sea "
                "un empresario o profesional."
            ),
        ),
        _cite(
            "Art. 84.Uno.2º",
            (
                "Serán sujetos pasivos los empresarios o profesionales para quienes se realicen las operaciones "
                "sujetas al impuesto en los supuestos que se indican a continuación, produciéndose la inversión del "
                "sujeto pasivo."
            ),
        ),
    ),
)


_INTRA_COMMUNITY_TRIANGULATION = VATRegulation(
    category=VATCategory.INTRA_COMMUNITY_TRIANGULATION,
    label="vat.catalogue.label_357358",
    description="vat.catalogue.description_747833",
    triggers_when="vat.catalogue.triggers_when_253417",
    iva_treatment="vat.catalogue.iva_treatment_660394",
    declares_in_modelos=("303", "349"),
    requires_reverse_charge=True,
    requires_supplier_vat_id=True,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 26.Tres",
            (
                "Se considerará sujeta a gravamen la adquisición intracomunitaria de bienes cuyo lugar de llegada "
                "esté en otro Estado miembro, cuando el adquirente acredite haber satisfecho en dicho Estado el "
                "impuesto correspondiente a la operación triangular, siempre que se hayan cumplido los requisitos "
                "simplificadores previstos en la normativa comunitaria."
            ),
        ),
        _cite(
            "Art. 15.Uno",
            (
                "Se entenderá por adquisición intracomunitaria de bienes la obtención del poder de disposición sobre "
                "bienes muebles corporales expedidos o transportados al territorio de aplicación del impuesto."
            ),
        ),
    ),
)


_EXPORT_THIRD_COUNTRY_ZERO_RATED = VATRegulation(
    category=VATCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
    label="vat.catalogue.label_620271",
    description="vat.catalogue.description_889069",
    triggers_when="vat.catalogue.triggers_when_824512",
    iva_treatment="vat.catalogue.iva_treatment_338490",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 21.1º",
            (
                "Estarán exentas las entregas de bienes expedidos o transportados fuera de la Comunidad por el "
                "transmitente o por un tercero que actúe en nombre y por cuenta de éste."
            ),
        ),
        _cite(
            "Art. 21.2º",
            (
                "Estarán exentas las entregas de bienes expedidos o transportados fuera de la Comunidad por el "
                "adquirente no establecido en el territorio de aplicación del impuesto o por un tercero que actúe en "
                "nombre y por cuenta de él."
            ),
        ),
    ),
)


_IMPORT_THIRD_COUNTRY = VATRegulation(
    category=VATCategory.IMPORT_THIRD_COUNTRY,
    label="vat.catalogue.label_889802",
    description="vat.catalogue.description_247574",
    triggers_when="vat.catalogue.triggers_when_775302",
    iva_treatment="vat.catalogue.iva_treatment_869170",
    declares_in_modelos=("303",),
    requires_reverse_charge=True,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 17",
            (
                "Estarán sujetas al impuesto las importaciones de bienes, cualquiera que sea el fin a que se destinen "
                "y la condición del importador."
            ),
        ),
        _cite(
            "Art. 18.Uno",
            (
                "Tendrá la consideración de importación de bienes la entrada en el interior del país de un bien que "
                "no cumpla las condiciones previstas en los artículos 9 y 10 del Tratado constitutivo de la Comunidad "
                "Económica Europea."
            ),
        ),
    ),
)


_RECARGO_EQUIVALENCIA = VATRegulation(
    category=VATCategory.RECARGO_EQUIVALENCIA,
    label="vat.catalogue.label_243153",
    description="vat.catalogue.description_951487",
    triggers_when="vat.catalogue.triggers_when_060209",
    iva_treatment="vat.catalogue.iva_treatment_837679",
    declares_in_modelos=("303",),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 148.Uno",
            (
                "El régimen especial del recargo de equivalencia se aplicará a los comerciantes minoristas que sean "
                "personas físicas o entidades en régimen de atribución de rentas en el Impuesto sobre la Renta de las "
                "Personas Físicas que desarrollen su actividad en los sectores económicos y cumplan los requisitos "
                "que reglamentariamente se determinen."
            ),
        ),
        _cite(
            "Art. 154.Dos",
            (
                "Los sujetos pasivos sometidos a este régimen especial no estarán obligados a efectuar la liquidación "
                "ni el pago del impuesto a la Hacienda pública en relación con las operaciones comerciales que "
                "realicen, ni tampoco por las transmisiones de los bienes utilizados exclusivamente en dicha actividad."
            ),
        ),
    ),
)


_REGIMEN_SIMPLIFICADO = VATRegulation(
    category=VATCategory.REGIMEN_SIMPLIFICADO,
    label="vat.catalogue.label_574464",
    description="vat.catalogue.description_837760",
    triggers_when="vat.catalogue.triggers_when_809073",
    iva_treatment="vat.catalogue.iva_treatment_720111",
    declares_in_modelos=("303", "390"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 122.Uno",
            (
                "El régimen simplificado se aplicará a los sujetos pasivos personas físicas y a las entidades en "
                "régimen de atribución de rentas en el Impuesto sobre la Renta de las Personas Físicas, siempre que "
                "todos sus socios, herederos, comuneros o partícipes sean personas físicas, que cumplan los "
                "requisitos que reglamentariamente se determinen."
            ),
        ),
        _cite(
            "Art. 123.Uno",
            (
                "Los sujetos pasivos acogidos al régimen simplificado determinarán, con referencia a cada actividad "
                "a que resulte aplicable, el importe de las cuotas devengadas en concepto del Impuesto sobre el Valor "
                "Añadido y del recargo de equivalencia, en su caso, mediante el procedimiento establecido "
                "reglamentariamente."
            ),
        ),
    ),
)


_OPERACION_NO_SUJETA = VATRegulation(
    category=VATCategory.OPERACION_NO_SUJETA,
    label="vat.catalogue.label_765009",
    description="vat.catalogue.description_113281",
    triggers_when="vat.catalogue.triggers_when_020809",
    iva_treatment="vat.catalogue.iva_treatment_703895",
    declares_in_modelos=("303", "349"),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 68.Uno",
            (
                "El lugar de realización de las entregas de bienes se determinará según las reglas siguientes: las "
                "entregas de bienes que no sean objeto de expedición o transporte se entenderán realizadas en el "
                "territorio de aplicación del impuesto cuando los bienes se pongan a disposición del adquirente en "
                "dicho territorio."
            ),
        ),
        _cite(
            "Art. 69.Uno.1º",
            (
                "Las prestaciones de servicios se entenderán realizadas en el territorio de aplicación del impuesto "
                "cuando el destinatario sea un empresario o profesional que actúe como tal y radique en el citado "
                "territorio la sede de su actividad económica."
            ),
        ),
    ),
)


_ERRONEOUS_INVOICE = VATRegulation(
    category=VATCategory.ERRONEOUS_INVOICE,
    label="vat.catalogue.label_947785",
    description="vat.catalogue.description_243075",
    triggers_when="vat.catalogue.triggers_when_035779",
    iva_treatment="vat.catalogue.iva_treatment_592112",
    declares_in_modelos=("303",),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 89.Uno",
            (
                "Los sujetos pasivos deberán efectuar la rectificación de las cuotas impositivas repercutidas cuando "
                "el importe de las mismas se hubiese determinado incorrectamente o se produzcan las circunstancias "
                "que, según lo dispuesto en el artículo 80 de esta Ley, dan lugar a la modificación de la base "
                "imponible."
            ),
        ),
        _cite(
            "Art. 89.Cinco",
            (
                "Cuando la rectificación determine una minoración de las cuotas inicialmente repercutidas, el sujeto "
                "pasivo podrá optar por iniciar ante la Administración tributaria el correspondiente procedimiento "
                "de devolución de ingresos indebidos o por regularizar su situación tributaria en la declaración-"
                "liquidación del período en que deba efectuarse la rectificación."
            ),
        ),
    ),
)


_UNKNOWN = VATRegulation(
    category=VATCategory.UNKNOWN,
    label="vat.catalogue.label_775396",
    description="vat.catalogue.description_306964",
    triggers_when="vat.catalogue.triggers_when_512869",
    iva_treatment="vat.catalogue.iva_treatment_732254",
    declares_in_modelos=("303",),
    requires_reverse_charge=False,
    requires_supplier_vat_id=False,
    boe_references=(_NORMATIVE_ID,),
    manual_references=(),
    citations=(
        _cite(
            "Art. 164.Uno",
            (
                "Sin perjuicio de lo establecido en el Título anterior, los sujetos pasivos del impuesto estarán "
                "obligados, con los requisitos, límites y condiciones que se determinen reglamentariamente, a "
                "presentar las declaraciones-liquidaciones correspondientes e ingresar el importe del impuesto "
                "resultante."
            ),
        ),
        _cite(
            "Art. 164.Uno.6º",
            (
                "Los sujetos pasivos del impuesto estarán obligados a nombrar un representante a efectos del "
                "cumplimiento de las obligaciones impuestas en esta Ley cuando se trate de sujetos pasivos no "
                "establecidos en la Comunidad."
            ),
        ),
    ),
    notes="Never ship this sentinel as a classifier outcome without human review.",
)


_REGULATIONS: tuple[VATRegulation, ...] = (
    _DOMESTIC_GENERAL_21,
    _DOMESTIC_REDUCED_10,
    _DOMESTIC_SUPER_REDUCED_4,
    _DOMESTIC_ZERO,
    _DOMESTIC_EXEMPT,
    _DOMESTIC_NOT_SUBJECT,
    _DOMESTIC_REVERSE_CHARGE,
    _INTRA_COMMUNITY_SUPPLY,
    _INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
    _INTRA_COMMUNITY_TRIANGULATION,
    _EXPORT_THIRD_COUNTRY_ZERO_RATED,
    _IMPORT_THIRD_COUNTRY,
    _RECARGO_EQUIVALENCIA,
    _REGIMEN_SIMPLIFICADO,
    _OPERACION_NO_SUJETA,
    _ERRONEOUS_INVOICE,
    _UNKNOWN,
)


def _build_catalogue() -> VATCatalogue:
    """Assemble the module-level :data:`VAT_CATALOGUE_2025` instance."""
    return VATCatalogue(regulations={regulation.category: regulation for regulation in _REGULATIONS})


VAT_CATALOGUE_2025: VATCatalogue = _build_catalogue()
"""Hand-curated 2025 :class:`aeat.domain.vat.VATCatalogue` covering every
:class:`aeat.domain.vat.VATCategory` member."""


VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue] = MappingProxyType(
    {
        2025: VAT_CATALOGUE_2025,
    }
)
"""Year-keyed view over the available :class:`aeat.domain.vat.VATCatalogue`
instances.

Currently the mapping carries only the 2025 entry. Year-specific catalogues
(for instance a 2026 entry once Ley 7/2024-derived amendments require
divergent regulation text) can be added without touching call sites —
:func:`resolve_catalogue` performs the lookup with a documented fallback.
"""


def resolve_catalogue(*, on: date) -> VATCatalogue:
    """Return the :class:`aeat.domain.vat.VATCatalogue` effective on ``on``.

    Looks up :data:`VAT_CATALOGUES_BY_YEAR` by ``on.year``. Falls back to the
    closest available year (currently 2025) and emits a ``debug`` log line
    when the exact year is not yet populated.

    Args:
        on: The transaction date for which the catalogue is needed.

    Returns:
        The :class:`aeat.domain.vat.VATCatalogue` covering ``on.year`` or the
        fallback 2025 catalogue.
    """
    catalogue = VAT_CATALOGUES_BY_YEAR.get(on.year)
    if catalogue is not None:
        return catalogue
    _logger.debug(
        "resolve_catalogue: no catalogue for year %d; falling back to 2025",
        on.year,
    )
    return VAT_CATALOGUE_2025


__all__ = [
    "VAT_CATALOGUES_BY_YEAR",
    "VAT_CATALOGUE_2025",
    "resolve_catalogue",
]
