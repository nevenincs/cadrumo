"""Strict legal-citation transport projections."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....application.registry.corpus import (
    RegistryCitationArticleProjection,
    RegistryCitationReferenceProjection,
    RegistryCorpusIssueProjection,
    RegistryTopicProjection,
)
from ....core.errors.severity import BaseSeverity
from .._registry_corpus_payloads import CitationListResult, CitationShowResult, CitationVerifyResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _topic() -> RegistryTopicProjection:
    return RegistryTopicProjection(
        slug="iva",
        title="IVA",
        body="Impuesto sobre el Valor Añadido",
        legal_refs=("ley-37-1992:art-1",),
    )


def _reference() -> RegistryCitationReferenceProjection:
    return RegistryCitationReferenceProjection(
        id="ley-37-1992",
        kind="ley",
        number="37/1992",
        title="Ley del IVA",
        published_at="1992-12-29",
        boe_id="BOE-A-1992-28740",
        boe_url="https://www.boe.es/buscar/doc.php?id=BOE-A-1992-28740",
        articulo_count=1,
        short_title="LIVA",
    )


def test_citation_payloads_preserve_typed_application_projections() -> None:
    topic = _topic()
    reference = _reference()
    article = RegistryCitationArticleProjection(
        numero="1",
        titulo="Naturaleza y ámbito de aplicación",
        summary="El impuesto grava entregas y servicios.",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a1",
        cite="Ley 37/1992, art. 1",
    )
    issue = RegistryCorpusIssueProjection(
        level=BaseSeverity.ERROR,
        code="legal-catalogue-validation",
        message="reference is missing a corpus document",
        reference_id="ley-37-1992:art-1",
    )

    listed = CitationListResult(reference_count=1, topic_count=1, topics=[topic], references=[reference])
    shown = CitationShowResult(reference=reference, articulo=article, related_topics=[topic])
    verified = CitationVerifyResult(
        reference_count=1, issue_count=1, passed=False, topic_count=1, topics=[topic], issues=[issue]
    )

    assert listed.references == [reference]
    assert shown.articulo == article
    assert verified.issues == [issue]


def test_citation_payloads_reject_malformed_nested_legal_rows() -> None:
    reference = _reference().model_dump(mode="json")
    reference["id"] = ""
    with pytest.raises(ValidationError):
        CitationListResult.model_validate({"reference_count": 1, "topic_count": 0, "references": [reference]})

    issue = RegistryCorpusIssueProjection(
        level=BaseSeverity.ERROR,
        code="legal-catalogue-validation",
        message="reference is missing a corpus document",
    ).model_dump(mode="json")
    # ``model_dump(mode="json")`` renders the strict enum field to its plain
    # JSON string value; restore the enum instance here so the malformed-row
    # assertion below still refuses for the field this test targets (a blank
    # ``message``), not for an incidental ``level`` type mismatch introduced
    # by the dict round-trip. ``model_validate_json`` (real JSON text) accepts
    # the string form directly -- only the python-dict path needs this.
    issue["level"] = BaseSeverity.ERROR
    issue["message"] = ""
    with pytest.raises(ValidationError):
        CitationVerifyResult.model_validate(
            {"reference_count": 1, "issue_count": 1, "passed": False, "topic_count": 0, "issues": [issue]},
        )
