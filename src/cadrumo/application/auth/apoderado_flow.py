"""The paged apoderado-representation flow hosted by the ``apoderado`` door.

Apoderamiento representation is NOT a profile fact: it persists in the
:class:`ApoderadoService`'s own encrypted namespace, separate from the
taxpayer profile record. The CLI door therefore hosts these pages over an
in-memory-only :class:`~cadrumo.application.flows.engine.FlowState`
(:class:`~cadrumo.core.flows.FlowMode` ``MODIFY``, checkpointing declared
``UNAVAILABLE`` in both modes) and hands the reviewed answers to
:meth:`ApoderadoService.configure` at commit -- the substrate never mints a
profile fact for this flow, and there is no create-mode checkpoint that
could write one.

Two pages compose the flow: the represented party's tax identifier
(validated through the canonical :func:`cadrumo.core.identity.validate_identity`
authority, the same authority every identity page binds -- never a second
identifier implementation) and the granted scope set (a CHECKBOX over the
live :class:`~cadrumo.domain.auth.apoderamientos.ApoderamientosCatalogue`).
Every copy slot is an existing locale-catalogue reference resolved at render
time; the flow authors no literal prose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .apoderado_service import ApoderadoConfiguration, ApoderadoService

if TYPE_CHECKING:
    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output

    from ...domain.auth import ApoderamientosCatalogue

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.flows import (
    CheckpointAvailability,
    CopyRefKind,
    FlowMode,
    FlowWidgetKind,
)
from ...core.identity import IdentityError, validate_identity
from ..flows.definition import CopyRef, FlowChoice, FlowDefinition, FlowPage, FlowSection
from ..flows.engine import FlowState
from ..flows.validators import ValidationVerdict, register_answer_validator

#: Flow, section, and page ids. Answers key the canonical map by these bare page ids.
APODERADO_FLOW_ID = "apoderado"
_APODERADO_SECTION_ID = "apoderado"
REPRESENTED_NIF_PAGE_ID = "apoderado-represented-nif"
SCOPES_PAGE_ID = "apoderado-scopes"

#: Registered id of the per-answer represented-party identity validator.
REPRESENTED_NIF_VALIDATOR_ID = "apoderado-represented-nif"

# Copy references -- every key already ships in the four locale catalogues,
# so the flow adds no new locale key. Declared as module constants so the
# static locale scanner treats them as live (they are referenced only inside
# the frozen page literals below, never at a ``tr()`` call site).
_FLOW_TITLE_LOCALE_KEY = "cli.config.auth.apoderado.help"
_FLOW_DESCRIPTION_LOCALE_KEY = "cli.config.auth.apoderado.configure_help"
_REPRESENTED_NIF_PROMPT_LOCALE_KEY = "cli.config.auth.apoderado.configure.represented_nif_help"
_SCOPES_PROMPT_LOCALE_KEY = "cli.config.auth.apoderado.configure.scope_help"
_FORMAT_TAX_ID_LOCALE_KEY = "wizard.setup.format.tax-id"
_NIF_INVALID_LOCALE_KEY = "wizard.errors.invalid_tax_id"

#: Every locale key this module references, for the scaffold gate.
APODERADO_FLOW_LOCALE_KEYS: tuple[str, ...] = (
    _FLOW_TITLE_LOCALE_KEY,
    _FLOW_DESCRIPTION_LOCALE_KEY,
    _REPRESENTED_NIF_PROMPT_LOCALE_KEY,
    _SCOPES_PROMPT_LOCALE_KEY,
    _FORMAT_TAX_ID_LOCALE_KEY,
    _NIF_INVALID_LOCALE_KEY,
)


class ApoderadoFlowAnswers(BaseModel):
    """The typed answer shape the apoderado flow collects.

    Carried on the :class:`~cadrumo.application.flows.definition.FlowDefinition` as its
    declared ``answers_model``. ``scopes`` is the CHECKBOX page's canonical
    comma-joined token string; :func:`apoderado_answers_from_state` splits it
    into the scope-token tuple :meth:`ApoderadoService.configure` validates.

    The substrate never validates answers against this model: it is a
    declarative slot only, and ``ApoderadoService.configure`` remains the
    single validation and persistence authority for both transports.
    """

    model_config = STRICT_FROZEN_CONFIG

    represented_nif: str = Field(min_length=1)
    scopes: str = Field(default="")


def _locale_ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


def _validate_represented_nif(page: FlowPage, canonical: str) -> ValidationVerdict:
    """Validate the represented party's tax id through the canonical identity authority.

    This is an early-refusal courtesy over the SAME law
    ``ApoderadoService.configure`` enforces at commit
    (:func:`cadrumo.core.identity.validate_identity`): the represented party
    may be a natural person (NIF / NIE) or a legal entity (CIF), so the check
    is the full authority -- the same one the wizard identity pages bind,
    never a second implementation. The service is the single guaranteed gate;
    this validator surfaces the failure in-page before the walk reaches
    review. A malformed value returns the ``wizard.errors.invalid_tax_id``
    verdict carrying only the page id; the raw answer never enters the
    diagnostic.
    """
    if not canonical:
        return ValidationVerdict.passed()
    try:
        validate_identity(canonical)
    except IdentityError:
        return ValidationVerdict.failed(_NIF_INVALID_LOCALE_KEY, page_id=page.id)
    return ValidationVerdict.passed()


register_answer_validator(REPRESENTED_NIF_VALIDATOR_ID, _validate_represented_nif)


def build_apoderado_flow_definition(catalogue: ApoderamientosCatalogue) -> FlowDefinition:
    """Return the two-page apoderado representation flow for ``catalogue``.

    The scope CHECKBOX choices are derived live from the supplied
    :class:`~cadrumo.domain.auth.apoderamientos.ApoderamientosCatalogue`, so
    a catalogue revision that adds a scope surfaces it as a choice without a
    code change here. Every page's ``domain_key`` is ``None``: an apoderado
    answer binds to no profile schema path, because representation is not a
    profile fact -- it commits to :meth:`ApoderadoService.configure`.
    """
    scope_choices = tuple(
        FlowChoice(
            value=scope.code,
            label=_locale_ref(f"cli.config.auth.apoderado.scope.{scope.code.lower()}"),
        )
        for scope in catalogue.scopes
    )
    represented_nif_page = FlowPage(
        id=REPRESENTED_NIF_PAGE_ID,
        widget=FlowWidgetKind.TEXT,
        prompt=_locale_ref(_REPRESENTED_NIF_PROMPT_LOCALE_KEY),
        format_hint=_locale_ref(_FORMAT_TAX_ID_LOCALE_KEY),
        failure_modes=(_locale_ref(_NIF_INVALID_LOCALE_KEY),),
        required=True,
        answer_type=str,
        domain_key=None,
        answer_validator_ids=(REPRESENTED_NIF_VALIDATOR_ID,),
    )
    scopes_page = FlowPage(
        id=SCOPES_PAGE_ID,
        widget=FlowWidgetKind.CHECKBOX,
        prompt=_locale_ref(_SCOPES_PROMPT_LOCALE_KEY),
        choices=scope_choices,
        required=True,
        answer_type=str,
        domain_key=None,
    )
    section = FlowSection(
        id=_APODERADO_SECTION_ID,
        title=_locale_ref(_FLOW_TITLE_LOCALE_KEY),
        items=(represented_nif_page, scopes_page),
    )
    return FlowDefinition(
        id=APODERADO_FLOW_ID,
        title=_locale_ref(_FLOW_TITLE_LOCALE_KEY),
        description=_locale_ref(_FLOW_DESCRIPTION_LOCALE_KEY),
        sections=(section,),
        answers_model=ApoderadoFlowAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def apoderado_answers_from_state(state: FlowState) -> tuple[str, tuple[str, ...]]:
    """Project a committed flow state into ``(represented_nif, scope_tokens)``.

    The scopes CHECKBOX canonical answer is a comma-joined token string; it
    is split back into the ordered token tuple
    :meth:`ApoderadoService.configure` validates against the catalogue. The
    represented-nif token is returned verbatim for the same service call --
    the service remains the single validation and persistence authority.
    """
    represented_nif = state.answers.get(REPRESENTED_NIF_PAGE_ID, "")
    scopes_raw = state.answers.get(SCOPES_PAGE_ID, "")
    scope_tokens = tuple(token for token in scopes_raw.split(",") if token.strip())
    return represented_nif, scope_tokens


def run_apoderado_flow(
    service: ApoderadoService,
    *,
    bucket_id: str,
    input: Input | None = None,
    output: Output | None = None,
) -> ApoderadoConfiguration:
    """Drive one apoderado door and persist its reviewed answer atomically.

    The CLI supplies the real service and leaves prompt devices unbound for an
    operator terminal. Headless callers bind real prompt-toolkit devices; the
    same line frontend, flow validators, and service writer then execute with
    no callback substitute or post-flow persistence step.
    """
    from ..flows.line_frontend import LineFlowFrontend

    definition = build_apoderado_flow_definition(service.catalogue)
    state, _projection = LineFlowFrontend(
        definition,
        input=input,
        output=output,
    ).run(mode=FlowMode.MODIFY)
    represented_nif, scope_tokens = apoderado_answers_from_state(state)
    return service.configure(
        bucket_id=bucket_id,
        represented_nif=represented_nif,
        scope_tokens=scope_tokens,
    )


__all__ = [
    "APODERADO_FLOW_ID",
    "APODERADO_FLOW_LOCALE_KEYS",
    "REPRESENTED_NIF_PAGE_ID",
    "REPRESENTED_NIF_VALIDATOR_ID",
    "SCOPES_PAGE_ID",
    "ApoderadoFlowAnswers",
    "apoderado_answers_from_state",
    "build_apoderado_flow_definition",
    "run_apoderado_flow",
]
