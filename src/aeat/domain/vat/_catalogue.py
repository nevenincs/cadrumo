"""Hand-curated 2025 VAT regulation catalogue.

One :class:`VATRegulation` per :class:`VATCategory`, each backed by
at least two :class:`Citation` records that quote (or faithfully
paraphrase) articles of **Ley 37/1992** (BOE-A-1992-28740). The
catalogue is the in-memory fallback used by
:func:`load_vat_rules_from_manual` when no on-disk year-keyed
catalogue is present.

The quoted Spanish text is a faithful paraphrase of the operative
statutory language where a verbatim extract would require copying
multi-paragraph blocks from the BOE. Auditability relies on the
combination of :attr:`Citation.source`, :attr:`Citation.article` and
:attr:`Citation.quoted_text_es` — the quoted text is sufficient to
re-locate the article on boe.es and confirm the rule.

Per the Modelo 303 ADR (#183) this module also exposes a
period-keyed mapping :data:`VAT_CATALOGUES_BY_YEAR` and a
:func:`resolve_catalogue` helper. the 2025 catalogue
only; non-2025 years fall back to the 2025 entry with a debug log
line. The mapping infrastructure is in place so future waves can
slot in year-specific catalogues without touching call sites.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType

from ...core.logging import get_logger
from ._schema import (
    Citation,
    CitationSource,
    VATCatalogue,
    VATCategory,
    VATRegulation,
)

_logger = get_logger(__name__)

_RETRIEVAL = date(2026, 4, 13)
_NORMATIVE_ID = "ley-37-1992"


def _cite(
    article: str,
    quoted_text_es: str,
    *,
    source: CitationSource = CitationSource.LEY_37_1992,
) -> Citation:
    """Shorthand builder for a 2026-04-13 retrieval of ``article``."""
    return Citation(
        source=source,
        article=article,
        url=None,
        quoted_text_es=quoted_text_es,
        retrieval_date=_RETRIEVAL,
    )


_DOMESTIC_GENERAL_21 = VATRegulation(
    category=VATCategory.DOMESTIC_GENERAL_21,
    label={
        "es": "Operación interior al tipo general (21 %)",
        "en": "Domestic supply at the general 21 % rate",
        "hu": "Belföldi ügylet általános kulccsal (21 %)",
    },
    description={
        "es": (
            "Entregas de bienes y prestaciones de servicios realizadas en el "
            "territorio de aplicación del impuesto al tipo general del 21 %."
        ),
        "en": ("Supplies of goods and services carried out in the Spanish VAT territory at the 21 % general rate."),
        "hu": ("Belföldi termékértékesítés és szolgáltatásnyújtás 21 %-os általános ÁFA-kulccsal."),
    },
    triggers_when={
        "es": ("El bien o servicio no está incluido en los listados del Art. 91 ni en las exenciones del Art. 20."),
        "en": ("The good or service is neither listed in Art. 91 reduced tables nor exempt under Art. 20."),
        "hu": (
            "A termék vagy szolgáltatás nem tartozik a 91. cikk kedvezményes "
            "listáihoz és nem mentes a 20. cikk alapján."
        ),
    },
    iva_treatment={
        "es": "Se repercute el 21 % en la factura y se declara en Modelo 303.",
        "en": "Charge 21 % on the invoice and declare on Modelo 303.",
        "hu": "A számlán 21 % ÁFA felszámítása, a Modelo 303-on szerepeltetve.",
    },
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
    label={
        "es": "Operación interior al tipo reducido (10 %)",
        "en": "Domestic supply at the reduced 10 % rate",
        "hu": "Belföldi ügylet kedvezményes kulccsal (10 %)",
    },
    description={
        "es": (
            "Entregas de bienes y prestaciones de servicios a los que el "
            "Art. 91.Uno aplica el tipo reducido del 10 %: alimentación "
            "general, hostelería, transporte de viajeros, vivienda nueva."
        ),
        "en": (
            "Goods and services taxed at the 10 % reduced rate under "
            "Art. 91.Uno (general food, hospitality, passenger transport, "
            "new housing)."
        ),
        "hu": (
            "Az Art. 91.Uno alá tartozó 10 %-os kulcsú ügyletek: általános "
            "élelmiszer, vendéglátás, utasszállítás, új lakóingatlan."
        ),
    },
    triggers_when={
        "es": "El bien o servicio figura en el listado del Art. 91.Uno.",
        "en": "The good or service is listed in Art. 91.Uno.",
        "hu": "A termék vagy szolgáltatás szerepel az Art. 91.Uno listáján.",
    },
    iva_treatment={
        "es": "Se repercute el 10 % en la factura y se declara en Modelo 303.",
        "en": "Charge 10 % on the invoice and declare on Modelo 303.",
        "hu": "A számlán 10 % ÁFA felszámítása, a Modelo 303-on szerepeltetve.",
    },
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
    label={
        "es": "Operación interior al tipo súper-reducido (4 %)",
        "en": "Domestic supply at the super-reduced 4 % rate",
        "hu": "Belföldi ügylet szuper-kedvezményes kulccsal (4 %)",
    },
    description={
        "es": (
            "Bienes y servicios de primera necesidad a los que el "
            "Art. 91.Dos aplica el tipo súper-reducido del 4 %: pan "
            "común, leche, huevos, frutas, libros, medicamentos, "
            "prótesis, VPO de régimen especial."
        ),
        "en": (
            "Essential goods and services taxed at the super-reduced "
            "4 % rate under Art. 91.Dos (basic bread, milk, eggs, "
            "fruit, books, medicines, prostheses, special-regime "
            "social housing)."
        ),
        "hu": ("Alapvető termékek és szolgáltatások 4 %-os kulcsa az Art. 91.Dos alapján."),
    },
    triggers_when={
        "es": "El bien o servicio figura en el listado del Art. 91.Dos.",
        "en": "The good or service is listed in Art. 91.Dos.",
        "hu": "A termék vagy szolgáltatás szerepel az Art. 91.Dos listáján.",
    },
    iva_treatment={
        "es": "Se repercute el 4 % en la factura y se declara en Modelo 303.",
        "en": "Charge 4 % on the invoice and declare on Modelo 303.",
        "hu": "A számlán 4 % ÁFA felszámítása, a Modelo 303-on szerepeltetve.",
    },
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
    label={
        "es": "Operación interior al tipo cero",
        "en": "Domestic supply at the zero rate",
        "hu": "Belföldi ügylet nulla kulccsal",
    },
    description={
        "es": (
            "Entregas a las que se aplica un tipo cero transitorio o "
            "estructural (exenciones plenas con derecho a deducción)."
        ),
        "en": ("Supplies taxed at a transitional or structural zero rate (full exemptions with right of deduction)."),
        "hu": ("Átmeneti vagy strukturális 0 %-os kulccsal adózó ügyletek (teljes mentesség levonási joggal)."),
    },
    triggers_when={
        "es": "Una norma transitoria o la exención del Art. 24 habilita el tipo cero.",
        "en": "A transitional law or the Art. 24 exemption enables the zero rate.",
        "hu": "Átmeneti rendelkezés vagy az Art. 24. cikk mentessége alapozza meg a nulla kulcsot.",
    },
    iva_treatment={
        "es": "Se factura al 0 % y se declara en Modelo 303 conservando el derecho a deducir.",
        "en": "Invoice at 0 % and declare on Modelo 303 while preserving input-VAT deduction.",
        "hu": "Számlázás 0 %-kal, Modelo 303-on bevallva, a levonási jog megőrzésével.",
    },
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
    label={
        "es": "Operación interior exenta",
        "en": "Domestic exempt supply",
        "hu": "Belföldi adómentes ügylet",
    },
    description={
        "es": (
            "Entregas de bienes y prestaciones de servicios interiores "
            "expresamente exentas conforme al Art. 20: sanidad, "
            "enseñanza, financieras, seguros, inmobiliarias sin "
            "renuncia."
        ),
        "en": (
            "Domestic supplies exempt under Art. 20: health, education, "
            "financial, insurance, immovable (without waiver)."
        ),
        "hu": (
            "Az Art. 20. alapján mentes belföldi ügyletek: egészségügy, "
            "oktatás, pénzügyi, biztosítási, ingatlan (lemondás nélkül)."
        ),
    },
    triggers_when={
        "es": "La actividad o bien figura en el listado del Art. 20.Uno.",
        "en": "The activity or good is listed in Art. 20.Uno.",
        "hu": "Az ügylet szerepel az Art. 20.Uno listáján.",
    },
    iva_treatment={
        "es": (
            "No se repercute IVA; la exención es limitada (sin derecho "
            "a deducir el IVA soportado) y se declara en casillas "
            "específicas del Modelo 303."
        ),
        "en": (
            "No VAT charged; the exemption is limited (no input-VAT "
            "deduction) and declared on dedicated Modelo 303 boxes."
        ),
        "hu": (
            "Nincs felszámított ÁFA; a mentesség korlátozott (nincs "
            "levonási jog) és a Modelo 303 külön rovataiban kerül bevallásra."
        ),
    },
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
    label={
        "es": "Operación no sujeta al IVA",
        "en": "Non-subject operation",
        "hu": "IVA alá nem tartozó ügylet",
    },
    description={
        "es": (
            "Operaciones que caen fuera del hecho imponible del IVA "
            "conforme al Art. 7: transmisión de unidades económicas "
            "autónomas, servicios prestados por empleados, muestras "
            "gratuitas."
        ),
        "en": (
            "Operations outside the VAT taxable event per Art. 7: "
            "transfer of a going concern, services rendered by "
            "employees, free samples."
        ),
        "hu": ("Az Art. 7. alapján az adóköteles eseményen kívül eső ügyletek."),
    },
    triggers_when={
        "es": "El supuesto está enumerado en el Art. 7 como no sujeto.",
        "en": "The scenario is enumerated in Art. 7 as non-subject.",
        "hu": "Az eset szerepel az Art. 7 nem adóköteles felsorolásában.",
    },
    iva_treatment={
        "es": "No hay hecho imponible; no se factura IVA ni se declara como operación IVA.",
        "en": "There is no taxable event; no VAT is charged or declared.",
        "hu": "Nincs adóköteles tényállás; nincs ÁFA felszámítás vagy bevallás.",
    },
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
    label={
        "es": "Operación interior con inversión del sujeto pasivo",
        "en": "Domestic operation with reverse charge",
        "hu": "Belföldi ügylet fordított adózással",
    },
    description={
        "es": (
            "Entregas de bienes o prestaciones de servicios interiores "
            "en las que el adquirente o destinatario asume la condición "
            "de sujeto pasivo y autoliquida la cuota (Art. 84.Uno.2º): "
            "ejecuciones de obra de construcción, entregas de desechos "
            "y materiales de recuperación, entregas de teléfonos móviles, "
            "consolas, ordenadores portátiles y tabletas digitales entre "
            "empresarios."
        ),
        "en": (
            "Domestic supplies of goods or services where the recipient "
            "becomes the taxable person and self-assesses VAT (Art. "
            "84.Uno.2º): construction works, waste / recovery materials, "
            "B2B supplies of mobile phones, video consoles, laptops and "
            "tablets."
        ),
        "hu": (
            "Olyan belföldi termékértékesítések vagy szolgáltatásnyújtások, "
            "ahol az átvevő/megrendelő válik adóalannyá és önadózással "
            "állapítja meg az ÁFA-t (Art. 84.Uno.2º): építési munkák, "
            "hulladék-/újrahasznosítási anyagok, B2B mobiltelefonok, "
            "játékkonzolok, laptopok és táblagépek értékesítései."
        ),
    },
    triggers_when={
        "es": (
            "El supuesto encaja en alguno de los apartados del Art. "
            "84.Uno.2º (construcción, residuos, electrónica de consumo "
            "entre empresarios, etc.)."
        ),
        "en": (
            "The transaction matches one of the Art. 84.Uno.2º "
            "sub-paragraphs (construction, waste, B2B consumer "
            "electronics, etc.)."
        ),
        "hu": (
            "Az ügylet az Art. 84.Uno.2º valamely pontjának megfelel "
            "(építés, hulladék, B2B fogyasztói elektronika stb.)."
        ),
    },
    iva_treatment={
        "es": (
            "El emisor expide la factura sin IVA repercutido y hace "
            "constar 'inversión del sujeto pasivo'. El destinatario "
            "autoliquida la cuota devengada y, en su caso, la deduce "
            "en el mismo modelo 303."
        ),
        "en": (
            "The issuer raises the invoice without output VAT and "
            "records 'reverse charge'. The recipient self-assesses "
            "the output VAT and may simultaneously deduct it on the "
            "same Modelo 303."
        ),
        "hu": (
            "A kibocsátó ÁFA nélkül állítja ki a számlát, feltüntetve "
            "a 'fordított adózást'. A vevő önbevallással megállapítja "
            "a fizetendő ÁFA-t és — ha jogosult — egyidejűleg le is "
            "vonja ugyanazon a Modelo 303-on."
        ),
    },
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
    label={
        "es": "Entrega intracomunitaria exenta",
        "en": "Intra-community supply (exempt)",
        "hu": "Közösségi értékesítés (mentes)",
    },
    description={
        "es": (
            "Entrega de bienes expedidos desde España a otro Estado "
            "miembro cuyo destinatario tiene NIF-VAT válido, exenta "
            "por el Art. 25."
        ),
        "en": (
            "Supply of goods dispatched from Spain to another member "
            "state to a buyer holding a valid VAT-ID; exempt under "
            "Art. 25."
        ),
        "hu": (
            "Spanyolországból másik tagállamba szállított termék "
            "értékesítése érvényes közösségi adószámú vevő részére; "
            "mentes az Art. 25. alapján."
        ),
    },
    triggers_when={
        "es": (
            "El adquirente es empresario o profesional identificado "
            "a efectos del IVA en otro Estado miembro y los bienes "
            "salen del TAI."
        ),
        "en": ("The buyer is VAT-registered in another member state and the goods leave the Spanish VAT territory."),
        "hu": (
            "A vevő másik tagállamban közösségi adószámmal rendelkező "
            "vállalkozás és a termék elhagyja a spanyol ÁFA-területet."
        ),
    },
    iva_treatment={
        "es": ("Se factura sin IVA con mención 'exenta Art. 25 Ley 37/1992' y se declara en Modelo 303 y Modelo 349."),
        "en": (
            "Invoice without VAT with the 'exenta Art. 25 Ley 37/1992' mention; declare on Modelo 303 and Modelo 349."
        ),
        "hu": ("ÁFA nélküli számla 'exenta Art. 25 Ley 37/1992' megjelöléssel; Modelo 303 és Modelo 349 bevallás."),
    },
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
    label={
        "es": "Adquisición intracomunitaria con inversión del sujeto pasivo",
        "en": "Intra-community acquisition (reverse charge)",
        "hu": "Közösségen belüli beszerzés (fordított adózás)",
    },
    description={
        "es": (
            "Compra de bienes procedentes de otro Estado miembro "
            "por un empresario o profesional español; se autorrepercute "
            "el IVA y se deduce en la misma declaración."
        ),
        "en": (
            "Purchase of goods from another member state by a Spanish "
            "business; the buyer self-assesses and deducts the VAT in "
            "the same return."
        ),
        "hu": (
            "Másik tagállamból származó termék vásárlása spanyol "
            "vállalkozás által; a vevő fordított adózás keretében "
            "számolja el az ÁFA-t."
        ),
    },
    triggers_when={
        "es": (
            "El adquirente es empresario o profesional español y el proveedor actúa con su NIF-VAT intracomunitario."
        ),
        "en": ("The buyer is a Spanish business and the supplier acts with its intra-community VAT-ID."),
        "hu": ("A vevő spanyol vállalkozás és az eladó közösségi ÁFA-azonosítóval jár el."),
    },
    iva_treatment={
        "es": (
            "Se autorrepercute el IVA en Modelo 303 (IVA devengado y "
            "soportado al mismo tiempo) y se declara en Modelo 349."
        ),
        "en": ("Self-assess VAT on Modelo 303 (both output and input) and declare on Modelo 349."),
        "hu": ("Modelo 303-on fordított adózás (egyidejű fizetendő és levonható ÁFA), Modelo 349-en bevallva."),
    },
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
    label={
        "es": "Operación triangular intracomunitaria",
        "en": "Intra-community triangulation",
        "hu": "Közösségen belüli háromszögügylet",
    },
    description={
        "es": (
            "Operación en cadena entre tres empresarios de tres Estados "
            "miembros en la que el intermediario no tributa en destino."
        ),
        "en": (
            "Chain transaction between three businesses in three member "
            "states where the intermediary does not tax in destination."
        ),
        "hu": (
            "Három tagállamban letelepedett vállalkozás közötti láncügylet, "
            "amelyben a közbeékelt szereplő mentesül a rendeltetési ország "
            "ÁFA-jától."
        ),
    },
    triggers_when={
        "es": "Se cumplen los requisitos del Art. 26.tres para la triangulación simplificada.",
        "en": "The simplified triangulation conditions of Art. 26.tres are met.",
        "hu": "Az Art. 26.tres szerinti egyszerűsített háromszögügylet feltételei teljesülnek.",
    },
    iva_treatment={
        "es": "Se declara como operación intracomunitaria con clave T en Modelo 349.",
        "en": "Declared as an intra-community operation with key T on Modelo 349.",
        "hu": "Modelo 349-en T kóddal bevallott közösségi ügylet.",
    },
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
    label={
        "es": "Exportación a país tercero exenta",
        "en": "Export to a third country (zero rated)",
        "hu": "Harmadik országba irányuló export (mentes)",
    },
    description={
        "es": (
            "Entrega de bienes expedidos con destino fuera de la "
            "Comunidad, exenta con derecho a deducción conforme al "
            "Art. 21."
        ),
        "en": (
            "Supply of goods dispatched outside the Community, exempt with input-VAT deduction right under Art. 21."
        ),
        "hu": ("Közösségen kívülre szállított termék értékesítése; mentes levonási joggal az Art. 21. alapján."),
    },
    triggers_when={
        "es": "Los bienes abandonan el territorio aduanero de la Unión con despacho de exportación.",
        "en": "The goods leave the Union customs territory with an export declaration.",
        "hu": "A termék kilép a vámterületről kiviteli nyilatkozattal.",
    },
    iva_treatment={
        "es": (
            "Se factura sin IVA con mención 'exenta Art. 21 Ley 37/1992' "
            "y se conserva el DUA como justificante; se declara en "
            "Modelo 303."
        ),
        "en": (
            "Invoice without VAT with the 'exenta Art. 21 Ley 37/1992' "
            "mention; keep the DUA as evidence; declare on Modelo 303."
        ),
        "hu": ("ÁFA nélküli számla 'exenta Art. 21 Ley 37/1992' megjelöléssel; a DUA igazolásként megőrizve."),
    },
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
    label={
        "es": "Importación de país tercero",
        "en": "Import from a third country",
        "hu": "Harmadik országból történő import",
    },
    description={
        "es": (
            "Entrada en el territorio de aplicación del impuesto de "
            "bienes procedentes de países no miembros; devengo en "
            "Aduana conforme al Art. 17 y 18."
        ),
        "en": (
            "Entry of goods from non-member countries into the Spanish "
            "VAT territory; accrual at customs per Arts. 17 and 18."
        ),
        "hu": ("Harmadik országból érkező termék beléptetése; az ÁFA keletkezése a vámnál az Art. 17-18. szerint."),
    },
    triggers_when={
        "es": "Se formaliza el DUA y se liquida el IVA a la importación.",
        "en": "A DUA is filed and import VAT is assessed at customs.",
        "hu": "A DUA (vámáru-nyilatkozat) benyújtása és az ÁFA megállapítása.",
    },
    iva_treatment={
        "es": (
            "El IVA lo liquida la Aduana (o se difiere con el modelo "
            "303 mediante inversión del sujeto pasivo si el importador "
            "está acogido al régimen de diferimiento)."
        ),
        "en": ("VAT is assessed at customs (or deferred via Modelo 303 under the deferred import-VAT regime)."),
        "hu": ("Az ÁFA a vámnál kerül megállapításra, vagy a halasztott import-ÁFA rendszerben a Modelo 303-on."),
    },
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
    label={
        "es": "Recargo de equivalencia",
        "en": "Equivalence surcharge regime",
        "hu": "Egyenértékűségi pótlék rendszer",
    },
    description={
        "es": (
            "Régimen especial obligatorio para comerciantes minoristas "
            "personas físicas que grava las compras del minorista con "
            "un recargo adicional sobre el IVA (5.2 / 1.4 / 0.5)."
        ),
        "en": (
            "Mandatory special regime for retail sole traders charging "
            "an additional surcharge on top of the supplier's VAT "
            "(5.2 / 1.4 / 0.5)."
        ),
        "hu": ("Kötelező különleges adózási mód kiskereskedő magánszemélyeknek, kiegészítő pótlékkal."),
    },
    triggers_when={
        "es": (
            "El destinatario es un comerciante minorista persona física "
            "acogido al régimen especial del recargo de equivalencia."
        ),
        "en": ("The recipient is a natural-person retail trader subject to the equivalence-surcharge regime."),
        "hu": ("A vevő kiskereskedő magánszemély, aki az egyenértékűségi pótlék rendszerébe tartozik."),
    },
    iva_treatment={
        "es": (
            "El proveedor repercute el IVA más el recargo; el minorista "
            "no presenta Modelo 303 ni Modelo 390 por su actividad."
        ),
        "en": (
            "The supplier charges VAT plus the surcharge; the retailer "
            "does not file Modelo 303 or 390 for that activity."
        ),
        "hu": ("A szállító az ÁFA-n felül pótlékot is felszámít; a kiskereskedő nem nyújt be Modelo 303/390-et."),
    },
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
    label={
        "es": "Régimen simplificado del IVA",
        "en": "Simplified VAT regime (módulos)",
        "hu": "Egyszerűsített ÁFA-rendszer (modulok)",
    },
    description={
        "es": (
            "Régimen especial de determinación de cuotas mediante "
            "índices y módulos para actividades recogidas en la Orden "
            "Ministerial anual."
        ),
        "en": (
            "Special regime computing VAT via indices and modules for "
            "activities listed in the yearly Ministerial Order."
        ),
        "hu": ("Az éves miniszteri rendeletben felsorolt tevékenységekre alkalmazandó modulos ÁFA rendszer."),
    },
    triggers_when={
        "es": ("La actividad del autónomo está recogida en la Orden HFP vigente y no ha renunciado al régimen."),
        "en": (
            "The self-employed activity is listed in the current Ministerial Order and the taxpayer has not opted out."
        ),
        "hu": ("A tevékenység szerepel a hatályos miniszteri rendeletben és az adózó nem mondott le a rendszerről."),
    },
    iva_treatment={
        "es": "Se liquidan cuotas mediante Modelo 303 trimestral con índices anuales.",
        "en": "Quarterly Modelo 303 settlements computed via yearly indices.",
        "hu": "Negyedéves Modelo 303 bevallás éves modulok alapján.",
    },
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
    label={
        "es": "Operación no sujeta (localización fuera del TAI)",
        "en": "Out-of-scope operation (place of supply outside Spain)",
        "hu": "Hatályon kívüli ügylet (teljesítési hely Spanyolországon kívül)",
    },
    description={
        "es": (
            "Operaciones cuyo lugar de realización se sitúa fuera "
            "del territorio de aplicación del impuesto conforme a "
            "las reglas de localización de los Arts. 68 a 74."
        ),
        "en": (
            "Operations whose place of supply is outside the Spanish "
            "VAT territory per Arts. 68-74 place-of-supply rules."
        ),
        "hu": ("Olyan ügyletek, amelyek teljesítési helye a spanyol ÁFA területen kívül esik az Art. 68-74. szerint."),
    },
    triggers_when={
        "es": ("Las reglas de localización sitúan la operación fuera del TAI y Ley 37/1992 no la considera sujeta."),
        "en": (
            "Place-of-supply rules place the operation outside the "
            "Spanish VAT territory and Law 37/1992 does not tax it."
        ),
        "hu": ("A teljesítési helyet szabályozó előírások szerint az ügylet Spanyolországon kívül teljesül."),
    },
    iva_treatment={
        "es": (
            "No se repercute IVA español; se informa en la declaración "
            "y puede requerir identificación VAT en el país de destino."
        ),
        "en": (
            "No Spanish VAT is charged; the operation is reported but "
            "may require VAT registration in the destination country."
        ),
        "hu": ("Nincs spanyol ÁFA; a célországban lehet szükséges ÁFA-regisztráció."),
    },
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
    label={
        "es": "Factura errónea (rectificable)",
        "en": "Erroneous invoice (rectifiable)",
        "hu": "Hibás számla (helyesbítendő)",
    },
    description={
        "es": (
            "Factura recibida o emitida con datos incorrectos "
            "(base, cuota, destinatario, tipo) que debe rectificarse "
            "antes de ser declarada."
        ),
        "en": (
            "Received or issued invoice with incorrect data (base, "
            "VAT amount, recipient, rate) that must be rectified "
            "before being declared."
        ),
        "hu": ("Hibás adatot tartalmazó kapott vagy kiállított számla, amelyet bevallás előtt helyesbíteni kell."),
    },
    triggers_when={
        "es": "Se detecta un error en la factura antes o después de la declaración.",
        "en": "An error is detected on the invoice before or after the return.",
        "hu": "A bevallás előtt vagy után hibát észlelünk a számlán.",
    },
    iva_treatment={
        "es": (
            "Se emite factura rectificativa conforme al Art. 89 y se ajusta la declaración del período correspondiente."
        ),
        "en": ("Issue a rectifying invoice under Art. 89 and adjust the corresponding period's return."),
        "hu": ("Helyesbítő számla kiállítása az Art. 89. szerint és az érintett időszak bevallásának módosítása."),
    },
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
    label={
        "es": "Régimen IVA desconocido",
        "en": "Unknown VAT regime",
        "hu": "Ismeretlen ÁFA-szabályozás",
    },
    description={
        "es": (
            "Sentinela para transacciones cuya categoría IVA no ha "
            "podido determinarse automáticamente y requieren revisión "
            "humana."
        ),
        "en": (
            "Sentinel for transactions whose VAT category cannot be determined automatically and require human review."
        ),
        "hu": ("Sentinel érték olyan tranzakciókra, amelyek ÁFA-kategóriája nem állapítható meg automatikusan."),
    },
    triggers_when={
        "es": "El clasificador no encuentra ninguna regla aplicable con suficiente confianza.",
        "en": "The classifier cannot find any applicable rule with sufficient confidence.",
        "hu": "A besoroló nem talál megfelelő szabályt elegendő bizonyossággal.",
    },
    iva_treatment={
        "es": "Se marca la transacción para revisión humana antes de declarar.",
        "en": "Flag the transaction for human review before declaring.",
        "hu": "A tranzakció kézi felülvizsgálatra kerül bevallás előtt.",
    },
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
    """Build the module-level :data:`VAT_CATALOGUE_2025` instance."""
    return VATCatalogue(regulations={regulation.category: regulation for regulation in _REGULATIONS})


VAT_CATALOGUE_2025: VATCatalogue = _build_catalogue()
"""Hand-curated 2025 VAT catalogue covering every :class:`VATCategory`."""


VAT_CATALOGUES_BY_YEAR: Mapping[int, VATCatalogue] = MappingProxyType(
    {
        2025: VAT_CATALOGUE_2025,
    }
)
"""Year-keyed view over the available :class:`VATCatalogue` instances.

 (#183) ships only the 2025 entry. Future waves slot in year-
specific catalogues (e.g., a 2026 entry once Ley 7/2024-derived
amendments require divergent regulation text) without touching
call sites — :func:`resolve_catalogue` performs the lookup with a
documented fallback.
"""


def resolve_catalogue(*, on: date) -> VATCatalogue:
    """Return the :class:`VATCatalogue` effective on ``on``.

    Looks up :data:`VAT_CATALOGUES_BY_YEAR` by ``on.year``. Falls
    back to the closest available year (currently 2025) and emits
    a ``debug`` log line when the exact year is not yet populated.

    Args:
        on: The transaction date for which the catalogue is needed.

    Returns:
        The :class:`VATCatalogue` covering ``on.year`` or the
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


def total_citation_count(catalogue: VATCatalogue = VAT_CATALOGUE_2025) -> int:
    """Return the total number of :class:`Citation` records in ``catalogue``."""
    return sum(len(regulation.citations) for regulation in catalogue)


__all__ = [
    "VAT_CATALOGUES_BY_YEAR",
    "VAT_CATALOGUE_2025",
    "resolve_catalogue",
    "total_citation_count",
]
