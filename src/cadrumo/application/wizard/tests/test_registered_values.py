"""Real-behavior tests for the registered-values review projection.

These exercise :func:`project_registered_values` against the real setup
catalogue and hand-built :class:`UserProfileRecord`s (no mocks): every
profile-bound page of a populated record appears, closed-set tokens
resolve to their catalogue-declared choice LABEL, booleans render as the
localized yes/no pair, a SECRET value passes through UNMASKED at this
layer (the review screen owns masking, through its widget-kind lookup —
that ownership is proven, not merely asserted, by
``test_secret_answer_is_masked_in_the_echo_and_the_review_table`` in
``entrypoints/tui/tests/test_flow_tui_app.py``, which drives a real
SECRET page with a non-empty registered value through the rendered
table), and the non-official-evidence suffix is appended exactly when the
underlying fact carries the ``censo_artefact_g313`` provenance token.

Assertions read expected labels from the catalogue's declared label copy
and the localized yes/no keys — key identity, never hardcoded prose.

Coordinated transient: the ``registered-non-official-suffix`` locale leaf
lands in the coordinator's serialized locale pass right after this code
commits. Until then :func:`tr` returns its humanised fallback; the suffix
test asserts the projection appends exactly ``tr(<suffix-key>)``, so it
holds against the fallback now and the landed string later (KEY IDENTITY).
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from ....core.external_constants import (
    PROVENANCE_SOURCE_CENSO_ARTEFACT,
    PROVENANCE_SOURCE_MANUAL_CLI,
)
from ....core.i18n import Translatable as tr
from ....core.i18n import tr as _tr
from ....domain.deadlines import IVARegime
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord, new_profile_id
from .._catalogue import SETUP_FLOW
from .._format_hints import REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY
from .._models import WizardFlow, WizardQuestion, WizardSection, WizardWidget
from .._registered_values import project_registered_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The suffix key is a coordinated transient (see module docstring). The test
# below asserts against ``tr(...)`` of the key, so it is robust to the leaf
# landing later; this marks which assertions ride the transient.
_SUFFIX_IS_COORDINATED_TRANSIENT = True


def _choice_label_key(question_id: str, token: str) -> str:
    """Return the catalogue-declared label copy key for a question's choice."""
    for section in SETUP_FLOW.sections:
        for question in section.questions:
            if question.id == question_id:
                for choice in question.choices:
                    if choice.value == token:
                        return str(choice.label)
    raise AssertionError(f"no choice {token!r} on question {question_id!r}")


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=new_profile_id(),
        facts=facts,
    )


def test_projection_covers_every_profile_bound_page_on_record() -> None:
    """Every profile-bound page whose fact is on record contributes an entry.

    Coverage is not scoped to changed pages: three facts on three distinct
    profile keys yield three registered entries keyed by their page id.
    """
    record = _record(
        UserProfileFact(path="identity.name", value="Operator"),
        UserProfileFact(path="iva.regime", value=IVARegime.SIMPLIFICADO.value),
        UserProfileFact(path="iva.roi_enrolled", value=True),
    )

    registered = project_registered_values(SETUP_FLOW, record)

    assert {"name", "iva-regime", "iva-roi-enrolled"} <= set(registered)


def test_closed_set_token_renders_as_its_choice_label() -> None:
    """A SELECT token resolves to the catalogue's declared choice label."""
    record = _record(UserProfileFact(path="iva.regime", value=IVARegime.SIMPLIFICADO.value))

    registered = project_registered_values(SETUP_FLOW, record)

    expected = _tr(_choice_label_key("iva-regime", IVARegime.SIMPLIFICADO.value))
    assert registered["iva-regime"] == expected


def test_boolean_renders_as_localized_yes_no_pair() -> None:
    """A CONFIRM fact renders the localized yes/no pair, not a raw token."""
    yes_record = _record(UserProfileFact(path="iva.roi_enrolled", value=True))
    no_record = _record(UserProfileFact(path="iva.roi_enrolled", value=False))

    assert project_registered_values(SETUP_FLOW, yes_record)["iva-roi-enrolled"] == _tr("flows.confirm.yes")
    assert project_registered_values(SETUP_FLOW, no_record)["iva-roi-enrolled"] == _tr("flows.confirm.no")


def test_free_text_value_passes_through_verbatim() -> None:
    """A plain text fact is surfaced unchanged (display convention passthrough)."""
    record = _record(UserProfileFact(path="identity.name", value="Operator"))

    registered = project_registered_values(SETUP_FLOW, record)

    assert registered["name"] == "Operator"


class _SecretAnswers(BaseModel):
    """Trivial answers model for the synthetic secret-probe flow."""


def _secret_only_flow() -> WizardFlow:
    """A one-question flow whose sole page is a SECRET widget.

    The setup catalogue carries no SECRET page, so the no-premasking
    property is proven against the generic projection with a synthetic
    flow: the projection must never mask, since the review screen owns
    masking through its widget-kind lookup.
    """
    return WizardFlow(
        id="secretprobe",
        title=tr("wizard.secretprobe.title"),
        description=tr("wizard.secretprobe.description"),
        answers_model=_SecretAnswers,
        sections=(
            WizardSection(
                id="s",
                title=tr("wizard.secretprobe.section"),
                questions=(
                    WizardQuestion(
                        id="api-token",
                        profile_key="preferences.api_token",
                        widget=WizardWidget.SECRET,
                        prompt=tr("wizard.secretprobe.api-token.prompt"),
                        choices=(),
                        answer_type=str,
                    ),
                ),
            ),
        ),
    )


def test_secret_value_is_not_pre_masked() -> None:
    """The projection passes a SECRET value through unmasked; the screen masks.

    This layer must NOT pre-mask: a second masking authority here could
    only drift from the review screen's widget-kind lookup. That the
    screen genuinely does mask the registered column (not merely that
    this layer refrains) is the separate claim proven by
    ``test_secret_answer_is_masked_in_the_echo_and_the_review_table``.
    """
    flow = _secret_only_flow()
    record = _record(UserProfileFact(path="preferences.api_token", value="s3cr3t-token"))

    registered = project_registered_values(flow, record)

    assert registered["api-token"] == "s3cr3t-token"


def test_artefact_sourced_fact_carries_the_non_official_suffix() -> None:
    """A fact sourced from the G313 artefact appends the non-official suffix.

    KEY IDENTITY (coordinated transient): the projection appends exactly
    ``tr(REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY)`` to the display
    string, and a same-value manual-CLI fact carries no suffix.
    """
    assert _SUFFIX_IS_COORDINATED_TRANSIENT
    artefact_record = _record(
        UserProfileFact(
            path="censo.activity_start_date",
            value="2020-01-15",
            source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
        ),
    )
    manual_record = _record(
        UserProfileFact(
            path="censo.activity_start_date",
            value="2020-01-15",
            source=PROVENANCE_SOURCE_MANUAL_CLI,
        ),
    )

    suffix = _tr(REGISTERED_NON_OFFICIAL_SUFFIX_LOCALE_KEY)
    assert project_registered_values(SETUP_FLOW, artefact_record)["activity-start-date"] == f"2020-01-15 {suffix}"
    assert project_registered_values(SETUP_FLOW, manual_record)["activity-start-date"] == "2020-01-15"


def test_a_cleared_path_is_not_rendered() -> None:
    """A deliberately cleared fact contributes no entry.

    Behaviour-preservation guard for the move onto the shared effective-fact
    projection. The value-only projection OMITTED a cleared path, so it was
    skipped incidentally; the effective-fact projection RETAINS it with a null
    value so the deletion stays visible, and the renderer must skip it
    explicitly instead. Without this, the migration could regress into
    rendering a cleared field as an empty or ``None`` string and nothing would
    catch it.
    """
    cleared = _record(
        UserProfileFact(path="censo.activity_start_date", value="2020-01-15"),
        UserProfileFact(path="censo.activity_start_date", value=None),
    )
    populated = _record(UserProfileFact(path="censo.activity_start_date", value="2020-01-15"))

    cleared_ids = set(project_registered_values(SETUP_FLOW, cleared))
    populated_ids = set(project_registered_values(SETUP_FLOW, populated))

    assert populated_ids - cleared_ids, "the populated record must render a page the cleared one does not"
    assert not any("None" in value for value in project_registered_values(SETUP_FLOW, cleared).values())
