"""Canonical AEAT modelo identifier enumeration.

This module exposes the closed set of AEAT modelo *identifiers* the codebase
references. Almost every member has a directory under
``src/aeat/_data/registry/aeat/modelos/`` and is therefore registry-loadable;
the enum value is the bare three-digit code string (``"036"``, ``"100"``, …) so
it is directly substitutable for the existing bare-string usage throughout the
codebase.

A small set of members are known modelos that the code references as
identifiers but which have **no registry definition by design** — currently the
retired :data:`Modelo.M037` (censo simplificada, suppressed by
Orden HAC/1526/2024).  These are enumerated in :data:`NON_REGISTRY_MODELOS`.
They are real codes with implementation support (lifecycle routing, portal
entries), but
:meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.validate_modelo`
raises for them and no registry TOML exists or may be created for them.

Filing-grade authority — deadline windows, period restrictions, and casilla
definitions — remains the :class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`
and the typed :class:`~aeat.domain.calculations.registry.RegistrySnapshot` it
produces. This enum is the closed-set *identifier* type: it tells you which
modelos exist; the registry tells you what (if anything) they contain.
Modelo-specific support such as filing, export, extraction, and verification is
declared on registry data such as
:attr:`~aeat.domain.calculations.registry.ModeloDefinition.capabilities`, not by
branching on this enum.

A gate test in ``src/aeat/core/tests/test_modelo.py`` binds the registry-backed
members to :func:`aeat.application.modelo.registry_modelo_codes` (enum minus
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
    :func:`aeat.application.modelo.registry_modelo_codes`; adding a new modelo
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
    M100 = "100"
    M111 = "111"
    M115 = "115"
    M117 = "117"
    M123 = "123"
    M126 = "126"
    M128 = "128"
    M130 = "130"
    M131 = "131"
    M136 = "136"
    M140 = "140"
    M151 = "151"
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
    M714 = "714"
    M720 = "720"
    M721 = "721"
    M840 = "840"


#: Recognized AEAT obligation modelos the registry does **not** yet model, each
#: mapped to a short description of the obligation. These are real, currently
#: fileable AEAT forms outside the registry directory listing; the
#: obligation-coverage reconciliation
#: (:func:`aeat.application.overview.build_obligation_coverage`) treats them as
#: part of the AEAT obligation universe and surfaces each as an *advised*
#: (registry-unmodeled → investigate) row rather than leaving it invisible.
#: Promoting one to a full registry definition (deadline windows + applicability
#: rule) removes it from this delta and folds it into
#: :func:`aeat.application.modelo.registry_modelo_codes`. The mapping is the
#: extensible edge of AEAT-wide enrollment: it ratchets up as obligations are
#: recognized and shrinks as they are modeled. The current set covers the common
#: retención autoliquidaciones and declaraciones informativas an autónomo, a PYME,
#: or an entity may owe, grounded against AEAT's published catalogue of
#: declaraciones informativas and retención forms; it is not yet AEAT's full
#: ~200-form set.
UNMODELED_OBLIGATIONS: Mapping[Modelo, str] = {
    Modelo.M220: "declaracion anual del Impuesto sobre Sociedades en regimen de consolidacion fiscal (grupos)",
    Modelo.M216: "IRNR retenciones e ingresos a cuenta for non-resident income, not yet registry-modeled",
}


#: Registry modelos (with a TOML definition) deliberately out of scope of the
#: overview obligation calendar, each with the recorded reason it is not scheduled.
_REGISTRY_OUT_OF_SCOPE_OBLIGATIONS: Mapping[Modelo, str] = {
    Modelo.M036: "registration form, not a periodic self-assessment the calendar schedules",
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
    Modelo.M198: "operaciones con activos financieros y otros valores mobiliarios (anual)",
    Modelo.M290: "cuentas de personas estadounidenses (FATCA, instituciones financieras)",
    Modelo.M291: "cuentas de no residentes sin establecimiento permanente (entidades)",
    Modelo.M294: "clientes perceptores de beneficios de IIC (lo declaran las gestoras)",
    Modelo.M295: "clientes con posicion inversora en IIC (lo declaran las gestoras)",
}


#: Registry modelos deliberately **out of scope** of the overview obligation
#: calendar, each mapped to the recorded reason it is not scheduled or advised.
#: The obligation-coverage reconciliation
#: (:func:`aeat.application.overview.build_obligation_coverage`) partitions every
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


#: Known modelo identifiers that intentionally have **no registry definition**.
#: These are real, code-referenced modelos for which
#: :meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.validate_modelo`
#: raises and no registry TOML exists or may be created. Three reasons put a member
#: here: the retired :data:`Modelo.M037` (censo simplificada, suppressed by
#: Orden HAC/1526/2024; superseded by :data:`Modelo.M036`), every
#: recognized-but-not-yet-modeled obligation in :data:`UNMODELED_OBLIGATIONS`, and
#: every recognized non-registry obligation declared out of scope
#: (:data:`_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS`). The parity gate compares the
#: remaining members to :func:`aeat.application.modelo.registry_modelo_codes`, so the
#: enum can carry retired codes, recognized-unmodeled obligations, and out-of-scope
#: non-registry forms without implying the registry can load them.
NON_REGISTRY_MODELOS: frozenset[Modelo] = (
    frozenset({Modelo.M037}) | frozenset(UNMODELED_OBLIGATIONS) | frozenset(_UNMODELED_OUT_OF_SCOPE_OBLIGATIONS)
)
