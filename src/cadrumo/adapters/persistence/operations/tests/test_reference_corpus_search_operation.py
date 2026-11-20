"""The registered corpus search, run through the real supervisor over a real encrypted profile."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.application.corpus_search import runtime as corpus_runtime
from cadrumo.application.corpus_search.citation_lookup import bundled_citation_lookup
from cadrumo.application.corpus_search.lexical_index import bundled_corpus_html_root
from cadrumo.application.corpus_search.models import RetrievalMode
from cadrumo.application.corpus_search.search_operation import (
    REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
    ReferenceCorpusSearchRequest,
    ReferenceCorpusSearchResult,
    build_reference_corpus_search_definition,
    build_reference_corpus_search_registration,
)
from cadrumo.application.corpus_search.terminology import search_terminology
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.capabilities import OperationConflictScope, OperationSensitiveInputPolicy
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.operation_definition import OperationDefinition
from cadrumo.application.operations.registry import OperationPublicDefinitionRegistrationV1
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.operations import (
    OperationDurability,
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability, DisclosureCategory

from .profile_operation_supervisor import SettledOperation, SupervisedProfile, supervised_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

# LGT art. 27 carries the recargo for late filing; the other article is a distractor.
_SAMPLE_STEMS = ("ley-58-2003-art-27", "ley-27-2014-art-7")
_CITATION_ID = "ley-58-2003:art-27.2"
_QUERY_MARKER = "recargo"


@pytest.fixture
def sample_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Serve a small real corpus subset through an isolated index cache."""
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    for stem in _SAMPLE_STEMS:
        name = f"{stem}.html.extracted.json"
        shutil.copy2(bundled_corpus_html_root() / name, corpus_root / name)
    monkeypatch.setattr(corpus_runtime, "bundled_corpus_html_root", lambda: corpus_root)
    with override_settings(cadrumo_storage_root=tmp_path / "corpus-storage"):
        yield


def _composed() -> tuple[tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1], ...]:
    definition = build_reference_corpus_search_definition()
    return ((definition, build_reference_corpus_search_registration(definition)),)


def _payload(profile: SupervisedProfile, **fields: object) -> ReferenceCorpusSearchRequest:
    return ReferenceCorpusSearchRequest.model_validate(
        {"profile_id": profile.profile_id, "output_language": OutputLanguage.ES, **fields}
    )


def _search(profile: SupervisedProfile, **fields: object) -> SettledOperation:
    return profile.run(
        definition_id=REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile.profile_id)),
        payload=_payload(profile, **fields),
    )


def test_a_query_settles_with_no_effect_under_the_held_publication_pin(tmp_path: Path, sample_corpus: None) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        settled = _search(profile, query=_QUERY_MARKER, limit=3)
        found = profile.result(settled, ReferenceCorpusSearchResult)

    assert settled.receipt.condition is OperationTerminalCondition.SUCCEEDED
    assert settled.receipt.effect is OperationEffect.NONE
    assert found.profile_id == profile.profile_id
    assert found.retrieval.mode is RetrievalMode.LEXICAL_ONLY
    assert 0 < len(found.retrieval.hits) <= 3
    assert {hit.corpus_ref.partition("#")[0] for hit in found.retrieval.hits} == {
        "corpus/normatives/html/ley-58-2003-art-27.html"
    }
    with bundled_indexed_authority().operation() as operation:
        assert found.authority_generation == operation.pin().logical_generation
    assert "iva-recargo-equivalencia" in {hit.concept_id for hit in found.terminology}


def test_an_exact_citation_resolves_the_published_verbatim_evidence(tmp_path: Path, sample_corpus: None) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        found = profile.result(_search(profile, query=f"  {_CITATION_ID}  "), ReferenceCorpusSearchResult)

    assert found.retrieval.mode is RetrievalMode.CITATION
    assert found.retrieval.hits == ()
    with bundled_indexed_authority().operation() as operation:
        published = bundled_citation_lookup((_CITATION_ID,), operation=operation).resolve(_CITATION_ID)
    assert found.retrieval.citation == published


def test_terminology_is_worded_in_the_requested_language(tmp_path: Path, sample_corpus: None) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        spanish = profile.result(_search(profile, query=_QUERY_MARKER, limit=2), ReferenceCorpusSearchResult)
        english = profile.result(
            _search(profile, query=_QUERY_MARKER, limit=2, output_language=OutputLanguage.EN),
            ReferenceCorpusSearchResult,
        )

    assert spanish.output_language is OutputLanguage.ES
    assert english.output_language is OutputLanguage.EN
    assert spanish.terminology == search_terminology(_QUERY_MARKER, locale="es", limit=2)
    assert english.terminology == search_terminology(_QUERY_MARKER, locale="en", limit=2)
    assert spanish.terminology != english.terminology


def test_a_query_with_no_searchable_terms_is_refused_without_a_result(tmp_path: Path, sample_corpus: None) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        settled = _search(profile, query="\u00bf?")

    assert settled.receipt.condition is OperationTerminalCondition.REFUSED
    assert settled.receipt.result_ref is None
    assert settled.receipt.effect is OperationEffect.NONE


def test_the_search_is_declared_ephemeral_so_the_query_is_never_journaled() -> None:
    definition = build_reference_corpus_search_definition()
    contract = build_reference_corpus_search_registration(definition).contract

    assert contract.durability is OperationDurability.EPHEMERAL
    assert contract.permitted_effects == frozenset({OperationEffect.NONE})
    assert contract.conflict_scope is OperationConflictScope.NONE
    assert contract.sensitive_input is OperationSensitiveInputPolicy.NONE


def test_a_search_for_another_profile_is_refused_in_the_worker(tmp_path: Path, sample_corpus: None) -> None:
    other = uuid4()
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        settled = profile.run(
            definition_id=REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(other)),
            payload=ReferenceCorpusSearchRequest(
                profile_id=other, query=_QUERY_MARKER, output_language=OutputLanguage.ES
            ),
        )

    assert settled.receipt.condition is OperationTerminalCondition.REFUSED
    assert settled.receipt.result_ref is None


def test_access_is_the_signed_in_profile_own_period_independent_read(tmp_path: Path, sample_corpus: None) -> None:
    with supervised_profile(tmp_path / "profile", _composed()) as profile:
        request = OperationRequest(
            definition_id=REFERENCE_CORPUS_SEARCH_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile.profile_id)),
            payload=_payload(profile, query=_QUERY_MARKER),
        )
        context = OperationAccessContext(
            profile_id=profile.profile_id,
            destination_id=uuid4(),
            action=AccessAction.RESULT,
            frontend=OperationFrontendProjection.CLI,
            contract=profile.registry.lookup_public_contract(REFERENCE_CORPUS_SEARCH_DEFINITION_ID),
            published_authority=Availability.AVAILABLE,
        )
        resolved = resolve_operation_access(registry=profile.registry, request=request, context=context)
        with pytest.raises(ProfileAccessRefusedError) as foreign:
            resolve_operation_access(
                registry=profile.registry, request=request, context=replace(context, profile_id=uuid4())
            )

    assert resolved.request.period_independent
    assert resolved.request.periods == frozenset()
    assert not resolved.policy.requires_all_periods
    assert {item.category for item in resolved.policy.disclosures} == {DisclosureCategory.PROFILE_VALUES}
    assert foreign.value.reason is AccessDenialCode.PROFILE_MISMATCH
