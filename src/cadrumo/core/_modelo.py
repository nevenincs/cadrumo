"""Canonical AEAT modelo identifier enumeration.

This module exposes the closed set of AEAT modelo *identifiers* the codebase
references. Almost every member has a directory under
``src/cadrumo/_data/registry/aeat/modelos/`` and is therefore registry-loadable;
the enum value is the bare three-digit code string (``"036"``, ``"100"``, …) so
it is directly substitutable for the existing bare-string usage throughout the
codebase.

A small set of members are known modelos that the code references as
identifiers but which have **no registry definition by design** — the modelos
suppressed by a later norm (:data:`Modelo.M037`, suppressed by
Orden HAC/1526/2024, and :data:`Modelo.M179`, suppressed from ejercicio 2024),
plus the recognized obligations filed by third parties or specialised filers.
These are enumerated in :data:`NON_REGISTRY_MODELOS`.
They are real codes with implementation support (lifecycle routing, portal
entries), but
:meth:`~domain.calculations.registry.ValidatedRegistryAuthority.validate_modelo`
raises for them and no registry TOML exists or may be created for them.

Filing-grade authority — deadline windows, period restrictions, and casilla
definitions — remains the :class:`~domain.calculations.registry.ValidatedRegistryAuthority`
and the typed :class:`~domain.calculations.registry.RegistrySnapshot` it
produces. This enum is the closed-set *identifier* type: it tells you which
modelos exist; the registry tells you what (if anything) they contain.
Modelo-specific support such as filing, export, extraction, and verification is
declared on registry data such as
:attr:`~domain.calculations.registry.ModeloDefinition.capabilities`, not by
branching on this enum.

A gate test in ``src/cadrumo/core/tests/test_modelo.py`` binds the registry-backed
members to :func:`application.modelo.registry_modelo_codes` (enum minus
:data:`NON_REGISTRY_MODELOS`) so the two cannot drift silently, and pins every
non-registry member to its deliberately-absent registry definition.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

__all__ = ["NON_REGISTRY_MODELOS", "OUT_OF_SCOPE_OBLIGATIONS", "UNMODELED_OBLIGATIONS", "Modelo"]


class Modelo(StrEnum):
    """Closed enumeration of AEAT modelo identifier codes.

    Each member's *name* is the prefixed form (``M036``, ``M100``, …) and
    its *value* is the bare three-digit code string (``"036"``, ``"100"``, …).
    Because :class:`Modelo` inherits from :class:`str` via :class:`~enum.StrEnum`,
    every member compares equal to its raw string value::

        Modelo.M303 == "303"   # True
        Modelo.M303 == Modelo.M303   # True

    The registry-backed members are bound to the registry directory listing by
    :func:`application.modelo.registry_modelo_codes`; adding a new modelo
    to the registry without updating this enum will fail the core parity test.
    Members in :data:`NON_REGISTRY_MODELOS` (the retired :data:`M037` and the
    recognized-but-not-yet-modeled obligations in :data:`UNMODELED_OBLIGATIONS`)
    are known identifiers with no registry definition by design.

    Use this enum at code boundaries that carry a modelo identifier. Operator
    input and registry TOML still enter as strings; callers may coerce with
    ``Modelo(value)`` when they need the closed enum contract, while registry
    consumers validate loadable support through the registry authority.
    """

    M030 = "030"
    M035 = "035"
    M036 = "036"
    M037 = "037"
    M038 = "038"
    M043 = "043"
    M100 = "100"
    M111 = "111"
    M115 = "115"
    M117 = "117"
    M121 = "121"
    M122 = "122"
    M123 = "123"
    M126 = "126"
    M128 = "128"
    M130 = "130"
    M131 = "131"
    M136 = "136"
    M140 = "140"
    M143 = "143"
    M145 = "145"
    M149 = "149"
    M150 = "150"
    M151 = "151"
    M156 = "156"
    M159 = "159"
    M165 = "165"
    M170 = "170"
    M171 = "171"
    M172 = "172"
    M173 = "173"
    M179 = "179"
    M180 = "180"
    M181 = "181"
    M182 = "182"
    M184 = "184"
    M185 = "185"
    M186 = "186"
    M187 = "187"
    M188 = "188"
    M189 = "189"
    M190 = "190"
    M192 = "192"
    M193 = "193"
    M194 = "194"
    M196 = "196"
    M198 = "198"
    M200 = "200"
    M202 = "202"
    M210 = "210"
    M216 = "216"
    M218 = "218"
    M221 = "221"
    M235 = "235"
    M236 = "236"
    M240 = "240"
    M241 = "241"
    M242 = "242"
    M220 = "220"
    M222 = "222"
    M231 = "231"
    M232 = "232"
    M233 = "233"
    M234 = "234"
    M238 = "238"
    M270 = "270"
    M280 = "280"
    M289 = "289"
    M290 = "290"
    M291 = "291"
    M294 = "294"
    M295 = "295"
    M296 = "296"
    M303 = "303"
    M308 = "308"
    M309 = "309"
    M322 = "322"
    M341 = "341"
    M345 = "345"
    M347 = "347"
    M349 = "349"
    M353 = "353"
    M360 = "360"
    M361 = "361"
    M362 = "362"
    M363 = "363"
    M368 = "368"
    M369 = "369"
    M379 = "379"
    M380 = "380"
    M390 = "390"
    M430 = "430"
    M480 = "480"
    M490 = "490"
    M510 = "510"
    M511 = "511"
    M517 = "517"
    M518 = "518"
    M519 = "519"
    M520 = "520"
    M521 = "521"
    M522 = "522"
    M524 = "524"
    M548 = "548"
    M553 = "553"
    M554 = "554"
    M555 = "555"
    M556 = "556"
    M557 = "557"
    M558 = "558"
    M559 = "559"
    M560 = "560"
    M561 = "561"
    M562 = "562"
    M563 = "563"
    M566 = "566"
    M568 = "568"
    M570 = "570"
    M573 = "573"
    M576 = "576"
    M580 = "580"
    M581 = "581"
    M582 = "582"
    M583 = "583"
    M584 = "584"
    M585 = "585"
    M586 = "586"
    M587 = "587"
    M588 = "588"
    M589 = "589"
    M590 = "590"
    M591 = "591"
    M592 = "592"
    M593 = "593"
    M595 = "595"
    M596 = "596"
    M604 = "604"
    M714 = "714"
    M718 = "718"
    M720 = "720"
    M721 = "721"
    M795 = "795"
    M796 = "796"
    M797 = "797"
    M798 = "798"
    M763 = "763"
    M840 = "840"
    M848 = "848"
    M993 = "993"


#: Recognized AEAT obligation modelos the registry does **not** yet model, each
#: mapped to a short description of the obligation. A member is a real, currently
#: fileable AEAT form outside the registry directory listing; the
#: obligation-coverage reconciliation
#: (:func:`application.overview.build_obligation_coverage`) treats every member as
#: part of the AEAT obligation universe and surfaces it as an *advised*
#: (registry-unmodeled → investigate) row rather than leaving it invisible.
#: Promoting one to a full registry definition (deadline windows + applicability
#: rule) removes it from this delta and folds it into
#: :func:`application.modelo.registry_modelo_codes`. The mapping is the
#: extensible edge of AEAT-wide enrollment: it ratchets up as obligations are
#: recognized and shrinks as they are modeled.
#:
#: **It is INTENTIONALLY EMPTY today, and that is a recorded decision rather than
#: an oversight.** Every sentence above describes the mechanism, which is live and
#: exercised; none of it asserts that a member currently exists.
#:
#: Why it stays empty rather than being filled in passing: deciding that a
#: **Do not delete the consuming branch to remove "dead code".** While this
#: mapping is empty the ``REGISTRY_UNMODELED`` disposition in
#: :func:`application.overview.build_obligation_coverage` is unreachable from any
#: production input, because the out-of-scope partition resolves first. It is
#: retained deliberately: it is the advisory capability for a real class of
#: taxpayers — those whose obligation is registry-less — and removing it reads as
#: tidying while silently withdrawing that advice. The coverage tests exercise the
#: branch through a substituted declaration, which proves the disposition
#: classifies a member correctly; it does not, and cannot, prove any actually
#: declared obligation is correct. The first real entry therefore inherits a gate
#: that already bites.
UNMODELED_OBLIGATIONS: Mapping[Modelo, str] = {}


#: Registry modelos (with a TOML definition) deliberately out of scope of the
#: overview obligation calendar, each with the recorded reason it is not scheduled.
_REGISTRY_OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = {
    Modelo.M036: "registration form, not a periodic self-assessment the calendar schedules",
    Modelo.M145: "local IRPF payer communication, not an AEAT filing/calendar obligation",
    Modelo.M151: "IRPF impatriado special regime, outside the autonomo/PYME core",
    Modelo.M714: "Impuesto sobre el Patrimonio, outside the IRPF/IVA/IS core",
    Modelo.M840: "Impuesto sobre Actividades Economicas, most taxpayers exempt (INCN < 1M)",
}


#: Recognized AEAT obligations OUTSIDE the registry that a general autónomo / PYME /
#: entity never files — filed by financial institutions, registrars, or under a
#: regional special regime — each with its recorded reason. They are declared out of
#: scope rather than advised so they do not become investigate-noise for the target
#: profiles, while still being explicitly accounted for by the completeness invariant.
_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = {
    Modelo.M510: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M511: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M517: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M518: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M519: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M520: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M521: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M522: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M524: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M548: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M553: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M554: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M555: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M556: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M557: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M558: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M559: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M561: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M562: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M563: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M566: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M570: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M573: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M580: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M581: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M582: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M590: "impuesto especial de fabricacion; lo declaran fabricantes, depositos u operadores del sector",
    Modelo.M560: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M595: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M596: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M583: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M584: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M585: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M588: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M589: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M591: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M586: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M587: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M593: "impuesto medioambiental/sectorial; lo declaran productores o instalaciones del sector",
    Modelo.M430: "impuesto sobre primas de seguros; lo declaran las entidades aseguradoras",
    Modelo.M480: "impuesto sobre primas de seguros, resumen anual; lo declaran las aseguradoras",
    Modelo.M568: "IEDMT solicitud de devolucion; tramite puntual del sector de matriculacion",
    Modelo.M149: "regimen especial de impatriados (vinculado al Modelo 151); fuera del nucleo autonomo/PYME",
    Modelo.M150: "regimen especial de impatriados, declaracion residual; fuera del nucleo autonomo/PYME",
    Modelo.M218: "pago fraccionado IS residual, sustituido en la practica por el Modelo 202",
    Modelo.M221: "prestacion patrimonial por conversion de activos por impuesto diferido; supuesto especializado",
    Modelo.M235: "actualizacion de mecanismos transfronterizos DAC6; complementa el Modelo 234, filers especializados",
    Modelo.M236: "utilizacion de mecanismos transfronterizos DAC6; complementa el Modelo 234, filers especializados",
    Modelo.M240: "Impuesto Complementario (Pilar 2), comunicacion; solo grandes grupos multinacionales",
    Modelo.M241: "Impuesto Complementario (Pilar 2), informativa GIR; solo grandes grupos multinacionales",
    Modelo.M242: "Impuesto Complementario (Pilar 2), autoliquidacion; solo grandes grupos multinacionales",
    Modelo.M718: "Impuesto Temporal de Solidaridad de las Grandes Fortunas; solo patrimonios netos elevados",
    Modelo.M795: "gravamen temporal energetico; solo grandes operadores del sector",
    Modelo.M796: "gravamen temporal energetico, pago anticipado; solo grandes operadores del sector",
    Modelo.M797: "gravamen temporal de entidades de credito; solo grandes entidades del sector",
    Modelo.M798: "gravamen temporal de entidades de credito, pago anticipado; solo grandes entidades",
    Modelo.M159: "consumo de energia electrica (lo declaran las comercializadoras)",
    Modelo.M170: "operaciones con tarjetas (lo declaran las entidades de gestion de cobros)",
    Modelo.M171: "imposiciones, disposiciones y cobros (lo declaran las entidades de credito)",
    Modelo.M172: "saldos en monedas virtuales (lo declaran los proveedores de servicios)",
    Modelo.M173: "operaciones con monedas virtuales (lo declaran los proveedores de servicios)",
    Modelo.M192: "operaciones con Letras del Tesoro (lo declaran las entidades gestoras)",
    Modelo.M196: "cuentas en instituciones financieras (lo declaran las entidades de credito)",
    Modelo.M368: "MOSS del IVA sustituido por la ventanilla unica OSS/IOSS (Modelo 369); sin periodos vigentes",
    Modelo.M030: "declaracion censal de personas fisicas (alta, domicilio, datos); no es autoliquidacion periodica",
    Modelo.M035: "registro censal de la ventanilla unica OSS/IOSS del IVA; no es autoliquidacion periodica",
    Modelo.M362: "reembolso de IVA diplomatico/consular/OOII; no aplica a contribuyentes generales",
    Modelo.M363: "reconocimiento previo de exencion de IVA diplomatica/consular; no aplica a contribuyentes generales",
    Modelo.M043: "tasa fiscal del juego (bingo); gestion cedida a las CCAA; no aplica a contribuyentes generales",
    Modelo.M993: "procedimiento interno AEAT de control de deducciones autonomicas; sin orden de aprobacion",
    Modelo.M198: "operaciones con activos financieros y otros valores mobiliarios (anual)",
    Modelo.M290: "cuentas de personas estadounidenses (FATCA, instituciones financieras)",
    Modelo.M186: "nacimientos y defunciones; lo declaran los Registros Civiles",
    Modelo.M231: "informacion pais por pais (CbC); solo grandes grupos multinacionales",
    Modelo.M233: "gastos en guarderias; lo declaran los centros de educacion infantil autorizados",
    Modelo.M234: "mecanismos transfronterizos DAC6; filers especializados, como los Modelos 235 y 236",
    Modelo.M238: "operadores de plataformas DAC7; lo declaran las plataformas digitales",
    Modelo.M289: "cuentas financieras CRS/DAC2; lo declaran las instituciones financieras, como el Modelo 290",
    Modelo.M379: "pagos transfronterizos CESOP; lo declaran los proveedores de servicios de pago",
    Modelo.M592: "envases de plastico no reutilizables; lo declaran fabricantes e importadores del sector",
    Modelo.M121: "cesion de la deduccion por familia numerosa/discapacidad; tramite electivo del IRPF",
    Modelo.M140: "abono anticipado de la deduccion por maternidad; tramite electivo del IRPF",
    Modelo.M143: "abono anticipado de la deduccion por familia numerosa/discapacidad; tramite electivo",
    Modelo.M361: "devolucion de IVA a no establecidos en el TAI; no aplica a contribuyentes establecidos",
    Modelo.M380: "operaciones asimiladas a las importaciones; operadores de zonas francas y depositos",
    Modelo.M848: "comunicacion del INCN en el IAE; solo sujetos pasivos no exentos, si no consta ya en IS",
    Modelo.M291: "cuentas de no residentes sin establecimiento permanente (entidades)",
    Modelo.M294: "clientes perceptores de beneficios de IIC (lo declaran las gestoras)",
    Modelo.M295: "clientes con posicion inversora en IIC (lo declaran las gestoras)",
}


#: Registry modelos deliberately **out of scope** of the overview obligation
#: calendar, each mapped to the recorded reason it is not scheduled or advised.
#: The obligation-coverage reconciliation
#: (:func:`application.overview.build_obligation_coverage`) partitions every
#: obligation in the AEAT universe into exactly one of *surfaced*, *confidently
#: excluded*, *advised* (investigate), or *out of scope*; this mapping is the sole
#: home of the last bucket, so "invisible" is always a recorded product-scope
#: decision rather than a silent omission. A modelo absent from a deadline window
#: and from an applicability rule but NOT listed here is **advised**, not dropped —
#: membership here is the explicit opt-out. It spans both registry forms declared
#: out of scope and recognized non-registry forms a general taxpayer never files.
OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = {
    **_REGISTRY_OUT_OF_SCOPE_OBLIGATIONS,
    **_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS,
}


#: Modelos suppressed by a later norm, each mapped to the instrument that
#: suppressed it and its successor where one exists. Membership is a legal fact
#: with a citable source, never an inference from a form's absence or from this
#: application's inability to file it: :data:`Modelo.M037` was suppressed by
#: Orden HAC/1526/2024 and superseded by :data:`Modelo.M036`; :data:`Modelo.M179`
#: ceased to be fileable from ejercicio 2024, its platform-reporting duty
#: absorbed into :data:`Modelo.M238` under the DAC7 regime.
_SUPPRESSED_MODELOS: Mapping[Modelo, str] = {
    Modelo.M037: "censo simplificada, suprimido por la Orden HAC/1526/2024; sustituido por el Modelo 036",
    Modelo.M179: "cesion de viviendas turisticas, suprimido desde 2024; sustituido por el Modelo 238 (DAC7)",
}


#: Known modelo identifiers that intentionally have **no registry definition**.
#: These are real, code-referenced modelos for which
#: :meth:`~domain.calculations.registry.ValidatedRegistryAuthority.validate_modelo`
#: raises and no registry TOML exists or may be created. Three reasons put a member
#: here: every modelo suppressed by a later norm (:data:`_SUPPRESSED_MODELOS`),
#: every recognized-but-not-yet-modeled obligation in
#: :data:`UNMODELED_OBLIGATIONS`, and every recognized non-registry obligation
#: declared out of scope (:data:`_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS`). The parity
#: gate compares the remaining members to
#: :func:`application.modelo.registry_modelo_codes`, so the enum can carry
#: suppressed codes, recognized-unmodeled obligations, and out-of-scope
#: non-registry forms without implying the registry can load them.
NON_REGISTRY_MODELOS: frozenset[Modelo] = (
    frozenset(_SUPPRESSED_MODELOS) | frozenset(UNMODELED_OBLIGATIONS) | frozenset(_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS)
)
