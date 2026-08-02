"""The bucket-scoped bulk resources: templates, and the in-process refusal.

Calculation observations and evidence rows are ENCRYPTED per-bucket state; the
session-less server process cannot decrypt them, so they are template-only
resources resolved by re-running the owning read verb as a subprocess. These
tests pin that the templates are advertised, that the concrete resource list does
NOT enumerate them (they are per-record and dynamic), and that an in-process
``read_harness_resource`` REFUSES them rather than reading in a context with no
active bucket session.
"""

from __future__ import annotations

import pytest

from .._resources import (
    BUCKET_SCOPED_RESOURCE_KINDS,
    HarnessResourceKind,
    HarnessResourceNotFoundError,
    list_harness_resource_templates,
    list_harness_resources,
    read_harness_resource,
    resource_mime_type,
    resource_uri,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_observations_and_evidence_templates_are_advertised() -> None:
    templates = {template.kind: template.uri_template for template in list_harness_resource_templates()}
    assert templates[HarnessResourceKind.OBSERVATIONS] == "cadrumo://observations/{name}"
    assert templates[HarnessResourceKind.EVIDENCE] == "cadrumo://evidence/{name}"


def test_bucket_scoped_kinds_are_not_concretely_listed() -> None:
    # The concrete resource list enumerates the shipped bundled tree only; the
    # per-record bucket resources are addressable by template, not enumerable.
    listed_kinds = {ref.kind for ref in list_harness_resources()}
    assert not (listed_kinds & BUCKET_SCOPED_RESOURCE_KINDS)


@pytest.mark.parametrize("kind", sorted(BUCKET_SCOPED_RESOURCE_KINDS))
def test_in_process_read_refuses_a_bucket_scoped_resource(kind: HarnessResourceKind) -> None:
    with pytest.raises(HarnessResourceNotFoundError):
        read_harness_resource(resource_uri(kind, "some-id"))


def test_resource_uri_round_trips_for_bucket_kinds() -> None:
    for kind in BUCKET_SCOPED_RESOURCE_KINDS:
        assert resource_uri(kind, "rev-1") == f"cadrumo://{kind.value}/rev-1"


def test_bucket_scoped_kinds_advertise_json_while_bundled_kinds_advertise_markdown() -> None:
    # The MCP server's bulk-resource read branch sources its response
    # `mime_type` from this same canonical map, so a bucket-scoped kind can
    # never advertise markdown while its read response is JSON (or vice
    # versa) - the finding this regression pins.
    for kind in HarnessResourceKind:
        expected = "application/json" if kind in BUCKET_SCOPED_RESOURCE_KINDS else "text/markdown"
        assert resource_mime_type(kind) == expected


def test_advertised_template_mime_type_matches_the_canonical_resource_mime_type() -> None:
    for template in list_harness_resource_templates():
        assert template.mime_type == resource_mime_type(template.kind)
