"""The statement a Modelo form offers when an amount carried from an earlier ejercicio holds no value.

A declaration can read amounts still pending from earlier ejercicios out of the
earlier return, such as the negative general bases a Modelo 100 compensates
over the four following years (Ley 35/2006 art. 50.3). With no earlier return
stored, those carries are unknown, never zero, and the filer who has nothing
pending says so here: one action states it for every carry still open, and the
edit records each as a zero the filer stated, apart from a zero typed.
"""

from __future__ import annotations

from typing import Final

from ...core.i18n.render import tr
from .edit_models import ModeloEditBindingIntentKind, ModeloEditWritableBindingOverrideSurfaceEntryV1
from .work_form_context import WorkFormContext
from .work_form_models import ModeloFormCarryAttestation

_ACTION_LOCALE_KEY: Final = "application.modelo.work_form.carry_attestation.action"
_STATEMENT_LOCALE_KEY: Final = "application.modelo.work_form.carry_attestation.statement"


def form_carry_attestation(context: WorkFormContext) -> ModeloFormCarryAttestation | None:
    """The statement for every attestable carry that holds no value, or ``None`` when none is open.

    A carry holds a value when the current calculation resolved one for it from
    any source, a stored earlier return included, or the filer entered or
    stated one. A form that admits no edit offers nothing.
    """
    if context.surface is None:
        return None
    revision = context.revision
    held = frozenset(()) if revision is None else frozenset(revision.binding_overrides)
    entered = context.overridden or frozenset(())
    open_carries = sorted(
        entry.binding_id
        for entry in context.surface.values()
        if isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
        and ModeloEditBindingIntentKind.ATTEST_NO_AMOUNT in entry.allowed_intents
        and entry.binding_id not in held
        and entry.binding_id not in entered
    )
    if not open_carries:
        return None
    locale = context.language.value
    return ModeloFormCarryAttestation(
        binding_ids=tuple(open_carries),
        action_words=tr(_ACTION_LOCALE_KEY, locale=locale),
        statement_words=tr(_STATEMENT_LOCALE_KEY, locale=locale),
    )


__all__ = ["form_carry_attestation"]
