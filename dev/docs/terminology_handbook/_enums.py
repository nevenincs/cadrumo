"""Closed value-set enumerations for the Terminology Handbook schema.

These StrEnum axes are the terminology-package-local closed sets that
the concept-oriented schema (TBX / ISO 30042 three-tier model, SKOS
relation vocabulary) declares. They live here, beside the schema they
constrain, rather than in :mod:`cadrumo.core`, because they are
Handbook-internal vocabulary with no consumer outside the terminology
surface: unlike :class:`~cadrumo.core.Modelo` (a cross-cutting AEAT
identifier referenced across domain, application, and CLI layers), a
concept's ``domain`` or ``term_status`` is meaningful only inside the
Handbook. The two closed axes that ARE cross-cutting are NOT redeclared
here: the schema reuses the canonical four-language
:class:`~cadrumo.core.external_constants.OutputLanguage`, and the concept
lifecycle -- read by the shipped product terminology search as well as by
the glossary and Pagefind projectors here -- is the core-owned
:class:`~cadrumo.core.ConceptLifecycle`. Because ``dev/`` is not shipped in
the wheel, ``cadrumo.core`` is the only home both sides can import.

Provenance of each axis:

* :class:`ConceptDomain` -- the TBX ``subjectField`` borrowing, mapped
  onto the AEAT enrolment-source axes (modelos, casillas, legal
  provisions, regimes, periods, CLI verbs, free concepts).
* :class:`TermStatus` -- the TBX ``normativeAuthorization`` /
  SKOS ``prefLabel`` / ``altLabel`` borrowing. Per-term status is
  orthogonal to the concept lifecycle (the TBX insight).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ConceptDomain", "TermStatus"]


class ConceptDomain(StrEnum):
    """Closed subject-field axis a Handbook concept belongs to.

    Mirrors the enrolment-source axes the Handbook represents (modelos,
    casillas, legal provisions, IVA / tax regimes, periods, CLI verbs)
    plus the catch-all ``CONCEPTO`` for free tax concepts that are not a
    structural surface. The Spanish-stem values follow the project
    naming convention for AEAT-mapped vocabulary.
    """

    CONCEPTO = "concepto"
    MODELO = "modelo"
    CASILLA_NAMESPACE = "casilla-namespace"
    REGIMEN = "regimen"
    PERIODO = "periodo"
    CLI_VERB = "cli-verb"
    LEGAL = "legal"


class TermStatus(StrEnum):
    """Normative status of a single term inside a language section.

    ``PREFERRED`` is the SKOS ``prefLabel`` (exactly one per language
    section); ``ADMITTED`` terms are accepted synonyms (SKOS
    ``altLabel``) carrying the declarative synonym surface;
    ``DEPRECATED`` terms are discouraged; ``FORBIDDEN`` terms are
    anti-recommendations (e.g. an English calque the project refuses)
    retained so search can steer away from them.
    """

    PREFERRED = "preferred"
    ADMITTED = "admitted"
    DEPRECATED = "deprecated"
    FORBIDDEN = "forbidden"
