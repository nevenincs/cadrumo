"""Applicability-rule fragment-family validation.

Validates the ``applicability`` schema family (W01.P03.S08) declared on a
:class:`~cadrumo.domain.calculations.registry.ModeloRevision`: its legal refs
resolve to grounded legal authority, at most one rule is declared per
revision, and the rule hydrates into the runtime
:class:`~cadrumo.domain.calculations.registry.applicability.ModeloApplicabilityRule`
without error.

See Also:
    :func:`cadrumo.domain.calculations.registry.validate_revision_sections.validate_revision_definition`
        Per-revision dispatcher that invokes every section validator,
        including relation, dependency-classification and filing-schedule
        validation in :mod:`_validate_dependency_sections`. This module's
        :func:`validate_applicability_section` follows the same
        accumulate-never-raise shape (returning ``list[str]``) and is meant
        to be dispatched from there alongside its siblings.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core import Modelo
from .applicability import hydrate_applicability_rule
from .errors import RegistryValidationError
from .schema import LegalReference, ModeloRevision
from ._validate_helpers import missing_refs


def validate_applicability_section(
    *,
    prefix: str,
    modelo: str,
    revision: ModeloRevision,
    legal_refs: Mapping[str, LegalReference],
) -> list[str]:
    """Return applicability-rule reference, cardinality and hydration failures.

    The :class:`~cadrumo.domain.calculations.registry.ModeloRevision` supplies
    the ``applicability`` family. Accumulates rather than raises, and
    preserves the underlying enum-coercion error text from
    :func:`hydrate_applicability_rule` in the diagnostic rather than
    flattening it to a generic message, so a bad token names itself and the
    field it broke.

    Args:
        prefix: The revision-scoped diagnostic prefix every failure line
            starts with, matching the sibling section validators.
        modelo: The modelo id the revision belongs to (a plain ``str``,
            matching the dispatcher's ``modelo_id`` contract), needed to
            hydrate the rule -- the fragment carries no self-referential
            ``modelo`` field.
        revision: The revision supplying the ``applicability`` family.
        legal_refs: The bundled legal-reference catalogue, keyed by id.
    """
    failures: list[str] = []
    rules = revision.applicability
    if len(rules) > 1:
        failures.append(
            f"{prefix}: revision declares {len(rules)} applicability rules; at most one is expected per revision",
        )
    for rule in rules:
        owner = f"applicability rule {rule.id}"
        failures.extend(missing_refs(prefix, owner, rule.legal_refs, legal_refs, "legal"))
        try:
            hydrate_applicability_rule(Modelo(modelo), rule)
        except RegistryValidationError as exc:
            failures.append(f"{prefix}: {owner}: {exc}")
    return failures
