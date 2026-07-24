"""The cotejo censal compare-select page family for the setup flow's phase 8.

The cotejo reconciles the operator's staged flow answers against a parsed
Certificado de Situación Censal (procedure G313). For every certified
censo fact that maps to a flow answer AND disagrees with it, the phase
renders one instance of the substrate's generic
:class:`~cadrumo.application.flows.FlowPage` COMPARE_SELECT kind offering
three arms: KEEP the flow answer, ADOPT the certificate value, or DEFER
the decision. Adopting writes the certificate value as a profile fact
carrying the non-official artefact provenance token (the registered-values
suffix projection already renders it); deferring records a typed divergence
the profile read surface later flags. The operator is always the authority
— nothing auto-overwrites.

Unlike the descendant group (a static repeating group spliced at
definition build), the cotejo pages are DYNAMIC over runtime data: their
candidate values are the operator's staged answer and the ingested
certificate value, neither known at definition-build time. So the pages
are built from a parsed :class:`~cadrumo.domain.censo.CertificadoSituacionCensal`
plus the current answer map, then spliced through the same post-bridge
decoration seam the descendant group uses (:func:`attach_cotejo_pages`,
mirroring :func:`~cadrumo.application.wizard.attach_descendant_group`).

Dormancy (honest, recorded, not hidden): the inbound censo parser refuses
every document while its layout extraction is unpinned (no issued-specimen
exists), so no live walk ever ingests a certificate and the WHOLE cotejo
family is unreachable live today. The builders below are exercised
synthetically — tests construct a :class:`CertificadoSituacionCensal`
directly and drive keep / adopt / defer — never through a parsed PDF.

Every ``wizard.setup.cotejo.*`` copy reference is declared as a module
constant so the locale scaffold's static usage scanner treats it as live;
the four-locale copy is authored through the locales CLI.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.flows import DEFER_TOKEN, CopyRefKind, FlowWidgetKind
from ..flows import CopyRef, FlowChoice, FlowDefinition, FlowPage, FlowSection

if TYPE_CHECKING:
    from ...domain.censo import CertificadoSituacionCensal
    from ...domain.user_profile import UserProfileFact
    from ..user_profile import CensoDivergence
    from ._models import WizardFlow

#: Section id the cotejo compare-select pages are spliced into (appended
#: after every phase section, before the substrate review surface).
COTEJO_SECTION_ID = "cotejo"

#: Page id prefix: one COMPARE_SELECT page per reconcilable axis, keyed by
#: the mapped question's id (``cotejo-<question-id>``).
_COTEJO_PAGE_PREFIX = "cotejo-"

# --- copy references (new wizard.setup.cotejo.* locale keys) ----------------

_SECTION_TITLE_LOCALE_KEY = "wizard.setup.cotejo.title"
_COMPARE_PROMPT_LOCALE_KEY = "wizard.setup.cotejo.compare.prompt"
_COMPARE_HELP_LOCALE_KEY = "wizard.setup.cotejo.compare.help"
_KEEP_LABEL_LOCALE_KEY = "wizard.setup.cotejo.keep.label"
_KEEP_PROVENANCE_LOCALE_KEY = "wizard.setup.cotejo.keep.provenance"
_ADOPT_LABEL_LOCALE_KEY = "wizard.setup.cotejo.adopt.label"
_ADOPT_PROVENANCE_LOCALE_KEY = "wizard.setup.cotejo.adopt.provenance"

#: Every net-new locale key this module references, for the scaffold gate.
COTEJO_LOCALE_KEYS: tuple[str, ...] = (
    _SECTION_TITLE_LOCALE_KEY,
    _COMPARE_PROMPT_LOCALE_KEY,
    _COMPARE_HELP_LOCALE_KEY,
    _KEEP_LABEL_LOCALE_KEY,
    _KEEP_PROVENANCE_LOCALE_KEY,
    _ADOPT_LABEL_LOCALE_KEY,
    _ADOPT_PROVENANCE_LOCALE_KEY,
)


_COMBINING_MARK_RE = re.compile(r"[̀-ͯ]")
_WHITESPACE_RE = re.compile(r"\s+")


def _canonical(text: str) -> str:
    """Canonical comparison form for cotejo disagreement detection.

    The sole live axis today is free-form Spanish prose the operator types
    against text extracted from a PDF, so a bare ``==`` spawns a false
    divergence page on a case, accent, or whitespace variant
    (``"Consultoria informatica"`` vs ``"CONSULTORÍA  INFORMÁTICA "``). This
    folds accents (NFKD + combining-mark strip), case-folds, and collapses
    every internal/edge whitespace run to a single space so only a GENUINE
    difference reconciles. It is a comparison key only — never persisted;
    the adopted / kept values are always the verbatim originals.
    """
    normalised = unicodedata.normalize("NFKD", text)
    without_marks = _COMBINING_MARK_RE.sub("", normalised)
    return _WHITESPACE_RE.sub(" ", without_marks.casefold()).strip()


def _locale_ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


class CotejoAxis(BaseModel):
    """One reconcilable cotejo axis: a flow answer that disagrees with the artefact.

    ``page_id`` is the COMPARE_SELECT page id; ``domain_key`` the schema
    path the answer binds to; ``flow_value`` the operator's staged answer
    (the KEEP candidate); ``artefact_value`` the certificate value (the
    ADOPT candidate); ``source`` the non-official artefact provenance token.
    """

    model_config = STRICT_FROZEN_CONFIG

    page_id: str = Field(min_length=1)
    domain_key: str = Field(min_length=1)
    flow_value: str = Field(min_length=1)
    artefact_value: str = Field(min_length=1)
    source: str = Field(min_length=1)


def cotejo_axes(
    flow: WizardFlow,
    certificado: CertificadoSituacionCensal,
    answers: Mapping[str, str],
) -> tuple[CotejoAxis, ...]:
    """Return the reconcilable axes for a certificate against the flow answers.

    Projects the certificate onto candidate facts
    (:func:`~cadrumo.domain.censo.censo_facts_from_certificado`), then keeps
    only the axes where a mapped wizard question holds a staged answer that
    DISAGREES with the certificate value. An axis absent from the answers,
    or one whose answer already equals the certificate, is not a
    reconciliation — the former is display-only certificate evidence, the
    latter nothing to decide.
    """
    from ...domain.censo import censo_facts_from_certificado

    question_by_key = {
        question.profile_key: question
        for section in flow.sections
        for question in section.questions
        if question.profile_key is not None
    }
    axes: list[CotejoAxis] = []
    for fact in censo_facts_from_certificado(certificado):
        question = question_by_key.get(fact.path)
        if question is None or fact.value is None:
            continue
        flow_value = answers.get(question.id)
        artefact_value = str(fact.value)
        if not flow_value or _canonical(flow_value) == _canonical(artefact_value):
            continue
        axes.append(
            CotejoAxis(
                page_id=f"{_COTEJO_PAGE_PREFIX}{question.id}",
                domain_key=fact.path,
                flow_value=flow_value,
                artefact_value=artefact_value,
                source=fact.source,
            ),
        )
    return tuple(axes)


def _compare_page(axis: CotejoAxis) -> FlowPage:
    """Build one COMPARE_SELECT page for a reconcilable axis.

    The KEEP candidate carries the operator's staged answer, the ADOPT
    candidate the certificate value; each declares its provenance copy (the
    COMPARE_SELECT validator requires it). The engine supplies the reserved
    DEFER arm, so it is never declared as a choice. ``default`` is the KEEP
    value so a scripted or unattended walk retains the operator's own answer
    rather than silently adopting the artefact.
    """
    return FlowPage(
        id=axis.page_id,
        widget=FlowWidgetKind.COMPARE_SELECT,
        prompt=_locale_ref(_COMPARE_PROMPT_LOCALE_KEY),
        help=_locale_ref(_COMPARE_HELP_LOCALE_KEY),
        choices=(
            FlowChoice(
                value=axis.flow_value,
                label=_locale_ref(_KEEP_LABEL_LOCALE_KEY),
                provenance=_locale_ref(_KEEP_PROVENANCE_LOCALE_KEY),
            ),
            FlowChoice(
                value=axis.artefact_value,
                label=_locale_ref(_ADOPT_LABEL_LOCALE_KEY),
                provenance=_locale_ref(_ADOPT_PROVENANCE_LOCALE_KEY),
            ),
        ),
        default=axis.flow_value,
        required=True,
        answer_type=str,
        domain_key=axis.domain_key,
    )


def build_cotejo_pages(
    flow: WizardFlow,
    certificado: CertificadoSituacionCensal,
    answers: Mapping[str, str],
) -> tuple[FlowPage, ...]:
    """Return one COMPARE_SELECT page per reconcilable cotejo axis (possibly empty)."""
    return tuple(_compare_page(axis) for axis in cotejo_axes(flow, certificado, answers))


def attach_cotejo_pages(definition: FlowDefinition, pages: tuple[FlowPage, ...]) -> FlowDefinition:
    """Return ``definition`` with the cotejo pages spliced as a trailing section.

    The post-bridge decoration seam mirroring
    :func:`~cadrumo.application.wizard.attach_descendant_group`: the cotejo
    section appends after every phase section so the substrate review
    surface renders it last, and every earlier answer the pages compare
    against is already committed. A no-op when ``pages`` is empty (a
    certificate that agrees with, or has no counterpart for, every answer
    yields no reconciliation and no section).
    """
    if not pages:
        return definition
    section = FlowSection(
        id=COTEJO_SECTION_ID,
        title=_locale_ref(_SECTION_TITLE_LOCALE_KEY),
        items=tuple(pages),
    )
    return definition.model_copy(update={"sections": (*definition.sections, section)})


def cotejo_outcome(
    flow: WizardFlow,
    certificado: CertificadoSituacionCensal,
    answers: Mapping[str, str],
    cotejo_answers: Mapping[str, str],
) -> tuple[tuple[UserProfileFact, ...], tuple[CensoDivergence, ...]]:
    """Project committed cotejo decisions into adopted facts and deferred divergences.

    For each reconcilable axis, the committed COMPARE_SELECT answer is one
    of: the ADOPT (certificate) value → an adopted
    :class:`~cadrumo.domain.user_profile.UserProfileFact` stamped with the
    artefact provenance token; the reserved DEFER token → a typed
    :class:`~cadrumo.application.user_profile.CensoDivergence` recording the
    unadopted evidence; or the KEEP (flow-answer) value / anything else →
    the operator retained their own answer, so nothing is written here (the
    answer already stands at its own path). The adopt discrimination uses
    the SAME canonical fold (:func:`_canonical`) as the disagreement
    detection, so a keep decision on a value that only differs from the
    certificate by case / accent / whitespace can never be misrouted to a
    spurious adopt. Returns ``(adopted_facts, divergences)`` for
    :func:`~cadrumo.application.user_profile.apply_cotejo` to commit.
    """
    from ...domain.user_profile import UserProfileFact
    from ..user_profile import CensoDivergence

    adopted: list[UserProfileFact] = []
    divergences: list[CensoDivergence] = []
    for axis in cotejo_axes(flow, certificado, answers):
        decision = cotejo_answers.get(axis.page_id)
        if decision == DEFER_TOKEN:
            divergences.append(
                CensoDivergence(axis=axis.domain_key, artefact_value=axis.artefact_value, source=axis.source),
            )
        elif decision is not None and _canonical(decision) == _canonical(axis.artefact_value):
            adopted.append(UserProfileFact(path=axis.domain_key, value=axis.artefact_value, source=axis.source))
    return tuple(adopted), tuple(divergences)


__all__ = [
    "COTEJO_LOCALE_KEYS",
    "COTEJO_SECTION_ID",
    "CotejoAxis",
    "attach_cotejo_pages",
    "build_cotejo_pages",
    "cotejo_axes",
    "cotejo_outcome",
]
