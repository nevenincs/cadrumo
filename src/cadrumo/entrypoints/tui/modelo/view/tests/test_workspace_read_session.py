"""Real-projection proof for the workspace read session's identity discipline.

Every projection here comes from the real ``resolve_static_inspection_result``
over a real isolated profile and the bundled registry. Nothing is stubbed:
the axis behaviour under test is a property of what the application layer
actually produces, and a fabricated projection would prove only that this
module agrees with the fixture.
"""

from __future__ import annotations

import pytest

from ......adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ......application.modelo.workspace_models import (
    ModeloWorkspaceFacetName,
)
from ......core import OutputLanguage
from ..controller import (
    ModeloWorkspaceReadSession,
    admit_workspace_session,
    semantic_identity,
)
from ..models import ModeloWorkspaceBoundedPageV1, ModeloWorkspaceCompletePageV1
from .conftest import resolve_real_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _session(bucket_id, repository, language: OutputLanguage) -> ModeloWorkspaceReadSession:
    session, refusal = admit_workspace_session(resolve_real_result(bucket_id, repository, language))
    assert refusal is None, f"expected an admitted projection, got a refusal: {refusal}"
    assert session is not None
    return session


def test_a_real_result_opens_a_session_carrying_its_semantic_identity(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository, OutputLanguage.ES)

    assert session.identity == semantic_identity(session.projection)
    assert session.identity.selected_revision_id == session.projection.target.law_selected_revision_id


def test_a_language_switch_is_a_locale_only_refresh_and_not_staleness(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """The same workspace in another language must not invalidate the session."""
    bucket_id, repository = bucket_and_repository
    spanish = _session(bucket_id, repository, OutputLanguage.ES)
    english = resolve_real_result(bucket_id, repository, OutputLanguage.EN).projection

    assert spanish.is_stale_against(english) is False
    assert spanish.is_locale_only_refresh(english) is True


def test_the_locale_axes_actually_move_across_a_language_switch(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Anti-tautology for the refresh proof: the locale coordinate really changed.

    Asserting only that the semantic axes held would pass just as well if the
    re-read had done nothing at all. The refresh is only demonstrated when
    the locale axes are shown to have moved WHILE the semantic axes did not.
    """
    bucket_id, repository = bucket_and_repository
    spanish = _session(bucket_id, repository, OutputLanguage.ES)
    english = resolve_real_result(bucket_id, repository, OutputLanguage.EN).projection

    assert english.locale.requested_language is OutputLanguage.EN
    assert spanish.projection.locale.requested_language is OutputLanguage.ES
    assert semantic_identity(english) == spanish.identity
    assert english.locale != spanish.projection.locale
    assert english.baseline.token != spanish.baseline_token

    # The catalogue digest is deliberately NOT asserted to differ. This
    # revision key has no English entry, so the English read falls back to
    # Spanish and reports the SPANISH shard's digest -- identical to the
    # Spanish read's. The requested/resolved split on the summary is what
    # keeps the two reads distinguishable, and it is the axis the session
    # compares.
    assert english.locale.resolved_language is OutputLanguage.ES
    assert english.baseline.locale_catalogue_digest == spanish.projection.baseline.locale_catalogue_digest


def test_the_semantic_identity_ignores_every_locale_bearing_field(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Two languages, one workspace: identity is equal though the baselines differ."""
    bucket_id, repository = bucket_and_repository
    spanish = resolve_real_result(bucket_id, repository, OutputLanguage.ES).projection
    english = resolve_real_result(bucket_id, repository, OutputLanguage.EN).projection

    assert semantic_identity(spanish) == semantic_identity(english)
    assert spanish.baseline != english.baseline


def test_a_static_inspection_session_reports_its_facet_continuations_honestly(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Cursor custody: the schema facet answers, and the graded-only facets are absent.

    A static inspection carries no materialization or provenance facet at
    all, so the session must report no continuation for them rather than
    inventing a complete one.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository, OutputLanguage.ES)

    assert session.cursor_for(ModeloWorkspaceFacetName.MATERIALIZATION) is None
    assert session.cursor_for(ModeloWorkspaceFacetName.PROVENANCE) is None
    assert session.has_more(ModeloWorkspaceFacetName.SCHEMA) == (
        session.projection.schema_facet.next_cursor is not None
    )


def test_a_session_is_frozen_so_a_refresh_cannot_mutate_it_underneath_a_renderer(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository, OutputLanguage.ES)

    with pytest.raises(AttributeError):
        session.projection = session.projection  # type: ignore[misc]


def test_the_session_discloses_boundedness_as_a_two_arm_answer_not_a_flag(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """Boundedness is part of the session contract, so a caller must handle both arms.

    A ``has_more`` flag can simply not be read; a discriminated pair cannot
    be rendered without deciding which arm it is. That is what stops a
    bounded page reaching an operator disguised as the whole set while no
    page-turn entry point exists.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository, OutputLanguage.ES)

    for facet in ModeloWorkspaceFacetName:
        completeness = session.page_completeness(facet)
        assert isinstance(completeness, ModeloWorkspaceCompletePageV1 | ModeloWorkspaceBoundedPageV1)
        assert (completeness.kind == "bounded") == session.has_more(facet)


def test_a_facet_the_admission_does_not_carry_reads_as_complete_not_bounded(
    bucket_and_repository: tuple[str, WorkUnitCatalogueRepository],
) -> None:
    """A static inspection has no materialization facet, and absence is not truncation.

    Reporting an absent facet as bounded would invite a destination to show
    a "more rows exist" affordance for rows that do not exist at all.
    """
    bucket_id, repository = bucket_and_repository
    session = _session(bucket_id, repository, OutputLanguage.ES)

    assert session.projection.materialization_facet is None
    assert session.page_completeness(ModeloWorkspaceFacetName.MATERIALIZATION).kind == "complete"
