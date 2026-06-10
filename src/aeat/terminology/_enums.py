"""Closed value-set enumerations for the Terminology Handbook schema.

These StrEnum axes are the terminology-package-local closed sets that
the concept-oriented schema (TBX / ISO 30042 three-tier model, SKOS
relation vocabulary) declares. They live here, beside the schema they
constrain, rather than in :mod:`aeat.core`, because they are
Handbook-internal vocabulary with no consumer outside the terminology
surface: unlike :class:`~aeat.core.Modelo` (a cross-cutting AEAT
identifier referenced across domain, application, and CLI layers), a
concept's ``domain`` or ``term_status`` is meaningful only inside the
Handbook. The one closed axis that IS cross-cutting -- the four output
languages -- is NOT redeclared here; the schema reuses the canonical
:class:`~aeat.core.external_constants.OutputLanguage`.

Provenance of each axis:

* :class:`ConceptDomain` -- the TBX ``subjectField`` borrowing, mapped
  onto the AEAT enrolment-source axes (modelos, casillas, legal
  provisions, regimes, periods, CLI verbs, free concepts).
* :class:`ConceptLifecycle` -- the four-state git-native lifecycle
  (SNOMED immutable-id inactivation pattern); a record is retired, never
  deleted.
* :class:`TermStatus` -- the TBX ``normativeAuthorization`` /
  SKOS ``prefLabel`` / ``altLabel`` borrowing. Per-term status is
  orthogonal to the concept lifecycle (the TBX insight).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ConceptDomain", "ConceptLifecycle", "TermStatus"]


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


class ConceptLifecycle(StrEnum):
    """Four-state lifecycle of a Handbook concept.

    A concept moves ``DRAFT`` (scaffolded, curation pending) ->
    ``APPROVED`` (curated, shippable) and may later be ``DEPRECATED``
    (discouraged but still resolvable) or ``RETIRED`` (tombstoned). A
    ``RETIRED`` concept MUST carry ``replaced_by``; records are never
    deleted, only inactivated.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


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
