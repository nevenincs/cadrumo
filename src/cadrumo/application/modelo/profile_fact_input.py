"""Refusal of a calculation whose input is a profile fact the profile does not state.

A binding the registry sources from one profile fact has no value of its own
to supply on the declaration: the filer states the fact in the profile and the
calculation reads it. The refusal therefore names the input by its declared
label, says to state it in the profile, and serves the profile door for that
fact instead of the declaration's binding listing.
"""

from __future__ import annotations

from typing import Final

from ...domain.calculations.registry.modelo_localization import binding_label_text
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.work_unit import WorkUnit
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ..operations.error_detail import served_words_language
from ..operations.next_step import is_profile_field_path
from ..operator_actions.preconditions import profile_required_facts_missing_verdict
from .profile_readiness_gate import open_profile_path_step
from .work_missing_input import ModeloWorkMissingInputError

PROFILE_FACT_INPUT_REQUIRED_MESSAGE_LOCALE_KEY: Final[str] = "application.modelo.errors.input_required_profile_fact"
"""The sentence naming the profile fact by its binding's label and saying to state it in the profile."""


def _profile_fact_path(
    snapshot: RegistrySnapshot, missing: ModeloWorkMissingInputError, schema: ProfileSchemaDefinition
) -> str | None:
    """The one profile field the refused binding reads, or ``None`` when it reads no single scalar fact."""
    binding = next((item for item in snapshot.revision.bindings if item.id == missing.binding_id), None)
    if binding is None:
        return None
    provider = binding.provider
    if not isinstance(provider, ProfileProvider) or provider.repeating or provider.collection is not None:
        return None
    selectors = profile_binding_selectors(provider)
    if len(selectors) != 1:
        return None
    (selector,) = selectors
    path = selector if selector in schema.field_paths else schema.path_for_model_selector(selector)
    return path if path is not None and is_profile_field_path(path) else None


def profile_fact_input_required(
    missing: ModeloWorkMissingInputError,
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    schema: ProfileSchemaDefinition,
) -> ModeloWorkMissingInputError | None:
    """The refusal of ``missing`` as the profile fact its binding reads, or ``None`` when it reads none.

    The words name the input by its binding's declared label, worded again
    from the binding and modelo wherever the refusal travels, and say to state
    it in the profile. The door is the profile edit for that fact; the next
    step opens it.

    ``snapshot`` is the :class:`RegistrySnapshot` it uses.
    """
    path = _profile_fact_path(snapshot, missing, schema)
    if path is None:
        return None
    modelo = str(work_unit.modelo)
    return ModeloWorkMissingInputError(
        missing,
        binding_id=missing.binding_id,
        translated_message=PROFILE_FACT_INPUT_REQUIRED_MESSAGE_LOCALE_KEY,
        context={
            "modelo": modelo,
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.registry_token,
            "binding_id": missing.binding_id,
            "binding_label": binding_label_text(modelo, missing.binding_id, locale=served_words_language().value),
        },
        precondition_verdict=profile_required_facts_missing_verdict(modelo=modelo, field_paths=(path,)),
        next_step=open_profile_path_step(path),
    )


__all__ = ["PROFILE_FACT_INPUT_REQUIRED_MESSAGE_LOCALE_KEY", "profile_fact_input_required"]
