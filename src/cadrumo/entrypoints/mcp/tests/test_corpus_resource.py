"""Real-behavior tests for the cadrumo://corpus/{ref} resource."""

from __future__ import annotations

import pytest

from .._resources import (
    HarnessResourceKind,
    HarnessResourceNotFoundError,
    list_harness_resource_templates,
    read_harness_resource,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_corpus_template_is_advertised() -> None:
    templates = {template.kind: template.uri_template for template in list_harness_resource_templates()}
    assert templates[HarnessResourceKind.CORPUS] == "cadrumo://corpus/{name}"


def test_corpus_resource_resolves_a_citation_id_to_verbatim_text() -> None:
    content = read_harness_resource("cadrumo://corpus/ley-58-2003:art-27.2")
    assert content.ref.kind is HarnessResourceKind.CORPUS
    assert "extempor" in content.text.lower()


def test_corpus_resource_resolves_a_corpus_ref_to_verbatim_text() -> None:
    content = read_harness_resource("cadrumo://corpus/corpus/normatives/html/ley-58-2003-art-27.html#a27-2")
    assert "extempor" in content.text.lower()


def test_unknown_corpus_reference_is_not_found() -> None:
    with pytest.raises(HarnessResourceNotFoundError):
        read_harness_resource("cadrumo://corpus/corpus/normatives/html/does-not-exist.html#a1")
