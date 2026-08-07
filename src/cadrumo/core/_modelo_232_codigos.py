"""Closed value sets for the Modelo 232 coded declaration fields.

Modelo 232 declares each operación vinculada with three coded fields, and AEAT
publishes their enumerations as Tablas A, B and C of the diseño de registro
``DR23200``, bundled under ``_data/corpus/aeat_official/disenos_registro/
modelo_232/``. Orden HFP/816/2017 art. 3 names the same three axes in prose --
art. 3.1.d the tipo de vinculación, art. 3.1.f the tipo de operación with its
eleven claves enumerated inline, art. 3.1.h the método de valoración -- and
delegates the first and last to Ley 27/2014 arts. 18.2 and 18.4.

These enums are the single typed home for those three sets, declared in ``core``
per the core-authority discipline: closed axes live in ``core/``, hydrate at
boundaries, and are asserted as members in tests. Two packages read them --
``domain.modelos`` types the operator-supplied CLI row, and
``domain.calculations.registry`` types the related-party observation its binding
family resolves -- which is why the home is ``core`` rather than either consumer.

The DR's field widths are load-bearing rather than incidental, because these
values are written into fixed-width positions on page_01: tipo de vinculación
occupies ONE position (240), while tipo de operación (243-244) and método de
valoración (246-247) occupy two each. A code wider than its field cannot be
declared at all, which is what rules out the OECD abbreviations (``CUP``,
``TNMM``) for the art. 18.4 methods AEAT codes as ``1A``-``1E``.

Each axis carries an explicit blank member. The whole vinculada block is marked
conditional rather than obligatorio in the DR, so a blank field is a state the
record genuinely represents -- and the alternative, defaulting to a real code,
would declare a relationship, an operation kind or a valuation method the
taxpayer never stated.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "MetodoValoracion",
    "TipoOperacionVinculada",
    "TipoVinculacion",
]


class TipoVinculacion(StrEnum):
    """One Modelo 232 tipo-de-vinculación code — DR23200 Tabla A.

    The art. 18.2 LIS relationship cases, in the single alphanumeric position
    the DR gives the field. The value byte-equals the stored token, so a member
    compares, hashes, and JSON-serialises identically to its string.

    Attributes:
        A_SOCIOS_O_PARTICIPES: Una entidad y sus socios o partícipes.
        B_CONSEJEROS_O_ADMINISTRADORES: Una entidad y sus consejeros o
            administradores.
        C_PARIENTES_DE_SOCIOS_O_ADMINISTRADORES: Una entidad y los cónyuges o
            personas unidas por relaciones de parentesco con sus socios,
            partícipes, consejeros o administradores (art. 18.3.c LIS).
        D_ENTIDADES_DEL_MISMO_GRUPO: Dos entidades que pertenezcan a un grupo.
        E_ADMINISTRADORES_DE_OTRA_DEL_GRUPO: Una entidad y los consejeros o
            administradores de otra entidad, cuando ambas pertenezcan a un grupo.
        F_PARTICIPACION_INDIRECTA_25: Una entidad y otra participada por la
            primera indirectamente en, al menos, el 25 % del capital social o de
            los fondos propios.
        G_SOCIOS_COMUNES_25: Dos entidades en las cuales los mismos socios,
            partícipes o sus cónyuges, o personas unidas por relaciones de
            parentesco, participen directa o indirectamente en, al menos, el
            25 % del capital social o los fondos propios.
        H_ESTABLECIMIENTOS_PERMANENTES_EN_EL_EXTRANJERO: Una entidad residente en
            territorio español y sus establecimientos permanentes en el
            extranjero.
        NO_DECLARADO: The DR's blank — the conditional field carries no code.
    """

    A_SOCIOS_O_PARTICIPES = "A"
    B_CONSEJEROS_O_ADMINISTRADORES = "B"
    C_PARIENTES_DE_SOCIOS_O_ADMINISTRADORES = "C"
    D_ENTIDADES_DEL_MISMO_GRUPO = "D"
    E_ADMINISTRADORES_DE_OTRA_DEL_GRUPO = "E"
    F_PARTICIPACION_INDIRECTA_25 = "F"
    G_SOCIOS_COMUNES_25 = "G"
    H_ESTABLECIMIENTOS_PERMANENTES_EN_EL_EXTRANJERO = "H"
    NO_DECLARADO = ""


class TipoOperacionVinculada(StrEnum):
    """One Modelo 232 tipo-de-operación clave — DR23200 Tabla C.

    The eleven claves Orden HFP/816/2017 art. 3.1.f enumerates, zero-padded to
    the two positions the DR gives the field. The prose numbers them ``Clave 1``
    through ``Clave 11``; the record design stores them ``01`` through ``11``,
    and the padded form is what a declaration carries.

    Attributes:
        C01_BIENES_TANGIBLES: Adquisición/transmisión de bienes tangibles
            (existencias, inmovilizados materiales, etc.).
        C02_INTANGIBLES: Adquisición/transmisión/cesión de uso de intangibles:
            cánones y otros ingresos o pagos por utilización de tecnología,
            patentes, marcas, know-how, etc.
        C03_FONDOS_PROPIOS: Adquisición/transmisión de activos financieros
            representativos de fondos propios.
        C04_DERECHOS_DE_CREDITO_Y_DEUDA: Adquisición/transmisión de derechos de
            crédito y activos financieros representativos de deuda, excluidas las
            operaciones de tipo 5.
        C05_OPERACIONES_FINANCIERAS_DE_DEUDA: Constitución o amortización de
            créditos o préstamos, emisión o amortización de obligaciones y bonos,
            etc., excluidos los intereses.
        C06_SERVICIOS: Servicios entre personas o entidades vinculadas
            (art. 18.5 LIS), incluidos rendimientos de actividades profesionales,
            artísticas y deportivas.
        C07_ACUERDOS_DE_REPARTO_DE_COSTES: Acuerdos de reparto de costes de
            bienes o servicios (art. 18.7 LIS).
        C08_ALQUILERES_DE_INMUEBLES: Alquileres y otros rendimientos por cesión
            de uso de inmuebles, excluidas las transmisiones.
        C09_INTERESES: Intereses de créditos, préstamos y demás activos
            financieros representativos de deuda, excluidas las transmisiones.
        C10_RENDIMIENTOS_DEL_TRABAJO_Y_PENSIONES: Rendimientos del trabajo,
            pensiones y aportaciones a fondos de pensiones y a otros sistemas de
            capitalización o retribución diferida, entrega de acciones u opciones
            sobre las mismas, etc.
        C11_OTRAS_OPERACIONES: Otras operaciones.
        NO_DECLARADO: The DR's blank — the conditional field carries no clave.
    """

    C01_BIENES_TANGIBLES = "01"
    C02_INTANGIBLES = "02"
    C03_FONDOS_PROPIOS = "03"
    C04_DERECHOS_DE_CREDITO_Y_DEUDA = "04"
    C05_OPERACIONES_FINANCIERAS_DE_DEUDA = "05"
    C06_SERVICIOS = "06"
    C07_ACUERDOS_DE_REPARTO_DE_COSTES = "07"
    C08_ALQUILERES_DE_INMUEBLES = "08"
    C09_INTERESES = "09"
    C10_RENDIMIENTOS_DEL_TRABAJO_Y_PENSIONES = "10"
    C11_OTRAS_OPERACIONES = "11"
    NO_DECLARADO = ""


class MetodoValoracion(StrEnum):
    """One Modelo 232 método-de-valoración code — DR23200 Tabla B.

    The five transfer-pricing methods of art. 18.4.1º LIS, in the two positions
    the DR gives the field. These are AEAT's own codes, not the OECD
    abbreviations for the same methods: the OECD names (``CUP``, ``RPM``,
    ``CPM``, ``PS``, ``TNMM``) are three and four characters wide and could not
    be written into the field even if AEAT accepted them.

    Attributes:
        M1A_PRECIO_LIBRE_COMPARABLE: Método del precio libre comparable
            (art. 18.4.1º.a LIS).
        M1B_COSTE_INCREMENTADO: Método del coste incrementado
            (art. 18.4.1º.b LIS).
        M1C_PRECIO_DE_REVENTA: Método del precio de reventa
            (art. 18.4.1º.c LIS).
        M1D_DISTRIBUCION_DEL_RESULTADO: Método de la distribución del resultado
            (art. 18.4.1º.d LIS).
        M1E_MARGEN_NETO_OPERACIONAL: Método del margen neto operacional del
            conjunto de operaciones (art. 18.4.1º.e LIS).
        NO_DECLARADO: The DR's blank — the conditional field carries no método.
    """

    M1A_PRECIO_LIBRE_COMPARABLE = "1A"
    M1B_COSTE_INCREMENTADO = "1B"
    M1C_PRECIO_DE_REVENTA = "1C"
    M1D_DISTRIBUCION_DEL_RESULTADO = "1D"
    M1E_MARGEN_NETO_OPERACIONAL = "1E"
    NO_DECLARADO = ""
