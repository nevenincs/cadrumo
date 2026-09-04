"""Which tax a taxpayer pays, and — for a legal entity — under which form.

:class:`EntityType` is the axis that selects the tax itself: IRPF for a
persona física, Impuesto sobre Sociedades for a legal entity, and the
régimen de atribución de rentas for an entity without legal personality.
The tax then selects the modelos, the calendar, and the rate schedule.

The pair lives in a module of its own, and deliberately not beside the
deadline records that first needed it: every Impuesto sobre Sociedades
surface reads this axis, so a home under the taxpayer package keeps that
dependency honest. Following :mod:`domain.contribuyente.ccaa`, the module
carries no import-time chain of its own, so a caller may reference the
enums without pulling in the rest of the package.
"""

from __future__ import annotations

from enum import StrEnum


class EntityType(StrEnum):
    """The taxpayer's entity type — the most consequential taxpayer axis.

    Entity type selects the tax (IRPF vs Impuesto sobre Sociedades vs
    régimen de atribución de rentas), and the tax selects the modelos,
    the calendar, and the rate schedule. Grounded in Ley 35/2006 LIRPF
    (BOE-A-2006-20764), Ley 27/2014 LIS (BOE-A-2014-12328), and LIRPF
    Title X Section 2 (régimen de atribución de rentas).

    Attributes:
        NATURAL_PERSON: Persona física — an IRPF taxpayer
            (contribuyente del IRPF).
        LEGAL_ENTITY: A legal entity with personalidad jurídica — a
            contribuyente del Impuesto sobre Sociedades.
        ATTRIBUTION_ENTITY: An entity without legal personality
            (comunidad de bienes, sociedad civil sin objeto mercantil,
            herencia yacente) under the régimen de atribución de rentas;
            income is taxed in the hands of each member.
    """

    NATURAL_PERSON = "natural_person"
    LEGAL_ENTITY = "legal_entity"
    ATTRIBUTION_ENTITY = "attribution_entity"


class LegalEntityForm(StrEnum):
    """The recognised legal form of an Impuesto sobre Sociedades entity.

    Only meaningful when :class:`EntityType` is ``LEGAL_ENTITY``; the
    sub-form drives the IS rate schedule (LIS Art. 29). Grounded in the
    AEAT distinction between sociedades civiles and comunidades de
    bienes and the project registry ``legal/is.toml``.

    Attributes:
        SL: Sociedad de responsabilidad limitada (S.L. / S.R.L.).
        SA: Sociedad anónima (S.A.).
        SAL: Sociedad Anónima Laboral (Ley 44/2015 Art. 1). Majority of
            share capital held by worker-shareholders. Eligible for
            reserva especial dotación under Ley 44/2015 Art. 14.
        SLL: Sociedad Limitada Laboral (Ley 44/2015 Art. 1). Same
            régimen as SAL but limited-liability form. Eligible for
            the same reserva especial under Ley 44/2015 Art. 14.
        COOPERATIVA: Sociedad cooperativa — IS with a reduced rate.
        SOCIEDAD_CIVIL_MERCANTIL: Sociedad civil con personalidad
            jurídica y objeto mercantil — an IS contribuyente since 2016.
        SIN_FINES_LUCRATIVOS: Asociación / fundación / entidad sin fines
            lucrativos — IS contribuyente, partially exempt.
        OTHER: Any other recognised legal form.
    """

    SL = "sl"
    SA = "sa"
    SAL = "sal"
    SLL = "sll"
    COOPERATIVA = "cooperativa"
    SOCIEDAD_CIVIL_MERCANTIL = "sociedad_civil_mercantil"
    SIN_FINES_LUCRATIVOS = "sin_fines_lucrativos"
    OTHER = "other"
