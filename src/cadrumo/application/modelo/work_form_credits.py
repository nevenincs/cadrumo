"""The withholding credits of one work form, and the numbered boxes the calculation works out from each.

A credit is a box fed by a binding whose source the withholding register owns.
Its dependents come from the revision's formula graph: every casilla whose
formula reads the credit's box or the register binding feeding it, and every
casilla reading one of those in turn. The walk passes through working figures
the form prints no number for, so a total that reads a credit only through
such a figure is still found; only the numbered boxes the form shows are
served. A casilla whose declared formula the revision does not carry leaves
the graph unreadable, and every credit then states its dependents as not
known rather than as none.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas and formulas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ...core.aggregation import BindingSourceKind
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...domain.calculations.registry.runtime_graph import expression_binding_refs, expression_casilla_refs
from ...domain.calculations.registry.schema import ModeloRevision
from .source_policy import SourceSurface
from .work_form_models import ModeloFormCasillaAddressV1, ModeloFormCredit, ModeloFormField


def _formula_readers(revision: ModeloRevision) -> Mapping[str, frozenset[str]] | None:
    """Every casilla or binding id mapped to the casillas whose formula reads it; ``None`` when one cannot be read."""
    formulas = {formula.id: formula for formula in revision.formulas}
    readers: dict[str, set[str]] = {}
    for casilla in revision.casillas:
        if casilla.formula is None:
            continue
        formula = formulas.get(casilla.formula)
        if formula is None:
            return None
        for operand in (*expression_casilla_refs(formula.expression), *expression_binding_refs(formula.expression)):
            readers.setdefault(str(operand), set()).add(str(casilla.id))
    return {operand: frozenset(casillas) for operand, casillas in readers.items()}


def _register_bindings(field: ModeloFormField) -> tuple[str, ...]:
    return tuple(str(item.binding_id) for item in field.bindings if item.policy.surface is SourceSurface.WITHHOLDING)


def _reached(seeds: Iterable[str], readers: Mapping[str, frozenset[str]]) -> frozenset[str]:
    """The casillas whose formula reads a seed, directly or through other casillas."""
    found: set[str] = set()
    pending = list(seeds)
    while pending:
        for casilla_id in readers.get(pending.pop(), frozenset()):
            if casilla_id not in found:
                found.add(casilla_id)
                pending.append(casilla_id)
    return frozenset(found)


def withholding_credits(fields: tuple[ModeloFormField, ...], revision: ModeloRevision) -> tuple[ModeloFormCredit, ...]:
    """The credits among ``fields``, in their order, each with the numbered boxes of ``fields`` worked out from it.

    ``fields`` are every field the form shows, in reading order. ``revision`` is
    the :class:`ModeloRevision` whose formulas say which boxes each credit feeds.
    """
    credits = [field for field in fields if _register_bindings(field)]
    if not credits:
        return ()
    readers = _formula_readers(revision)
    credit_casillas = {
        str(field.address.casilla_id) for field in credits if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    numbered = [
        field.address
        for field in fields
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.box is not None
        and str(field.address.casilla_id) not in credit_casillas
    ]
    served: list[ModeloFormCredit] = []
    for field in credits:
        if readers is None:
            served.append(ModeloFormCredit(address=field.address, dependents=None))
            continue
        own = (str(field.address.casilla_id),) if isinstance(field.address, ModeloFormCasillaAddressV1) else ()
        reached = _reached((*own, *_register_bindings(field)), readers)
        dependents = tuple(address for address in numbered if str(address.casilla_id) in reached)
        served.append(ModeloFormCredit(address=field.address, dependents=dependents))
    return tuple(served)


_SUFFERED_HEADING_LOCALE_KEY = "application.modelo.work_form.credits_heading.suffered"
_PRACTISED_HEADING_LOCALE_KEY = "application.modelo.work_form.credits_heading.practised"
_MIXED_HEADING_LOCALE_KEY = "application.modelo.work_form.credits_heading.mixed"


def withholding_credits_heading(fields: tuple[ModeloFormField, ...], language: OutputLanguage) -> str | None:
    """Head the credits among ``fields`` by who withheld them, in ``language``; ``None`` when there are none.

    A retención soportada binding is withholding a payer took from the filer's own
    income; every other register binding is withholding the filer took from others.
    """
    kinds = {
        item.policy.source_kind
        for field in fields
        for item in field.bindings
        if item.policy.surface is SourceSurface.WITHHOLDING
    }
    if not kinds:
        return None
    if kinds == {BindingSourceKind.RETENCION_SOPORTADA}:
        key = _SUFFERED_HEADING_LOCALE_KEY
    elif BindingSourceKind.RETENCION_SOPORTADA not in kinds:
        key = _PRACTISED_HEADING_LOCALE_KEY
    else:
        key = _MIXED_HEADING_LOCALE_KEY
    return tr(key, locale=language.value)


__all__ = ["withholding_credits", "withholding_credits_heading"]
