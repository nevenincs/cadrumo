"""H7 conformance gate: no raw portal markup relays into a tool result.

The security policy makes the untrusted-external-content
boundary a contract. AEAT portal HTML / justificante text is untrusted input to
the model (a prompt-injection vector), so the live-family (``app.live.*``) pull
verbs relay their observations only through TYPED envelope fields — a
justificante's CSV code, an expediente id, a notification's ``observaciones``
text, typed dates and amounts — never a raw HTML/markup blob that would carry
unsanitised portal markup straight into the model context.

This gate drives the real ``SCHEMA_REGISTRY`` output models for the live family
and asserts the no-raw-markup invariant on their fields (recursively, through
nested ``$defs``). The invariant holds trivially today, but the gate LOCKS it: an
in-test negative control proves the detector fires the moment a raw-markup field
(``raw_html`` / ``page_source`` / ``body_markup`` ...) is introduced, so a future
schema that adds one fails here rather than silently relaying portal markup.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import Field

from ....core.json_contract import SCHEMA_REGISTRY, OutputSchema
from .._tools import build_tool_descriptors

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LIVE_PREFIX = "app.live."

# Field-name fragments that imply a field would carry raw HTML/markup / a full
# rendered portal body rather than a typed, extracted value. A live-family result
# field whose name contains any of these is a raw-markup relay and violates H7.
_MARKUP_SUBSTRINGS: tuple[str, ...] = (
    "html",
    "markup",
    "raw_body",
    "raw_content",
    "raw_text",
    "rawbody",
    "page_source",
    "pagesource",
    "innerhtml",
    "inner_html",
    "outerhtml",
    "outer_html",
    "dom_tree",
    "domtree",
    "xml_body",
    "body_xml",
    "rendered_body",
    "portal_body",
)


def _walk_property_names(schema: object, out: set[str]) -> None:
    """Collect every declared property name from a JSON schema, recursively."""
    if not isinstance(schema, dict):
        return
    properties = schema.get("properties")
    if isinstance(properties, dict):
        out.update(str(name) for name in properties)
    for defs in (schema.get("$defs"), schema.get("definitions")):
        if isinstance(defs, dict):
            for sub in defs.values():
                _walk_property_names(sub, out)
    for nested_key in ("items", "additionalProperties", "contains"):
        _walk_property_names(schema.get(nested_key), out)
    for combinator in ("anyOf", "oneOf", "allOf", "prefixItems"):
        members = schema.get(combinator)
        if isinstance(members, list):
            for member in members:
                _walk_property_names(member, out)


def _markup_fields(schema: dict[str, Any]) -> list[str]:
    """Return the property names in ``schema`` that imply a raw-markup relay."""
    names: set[str] = set()
    _walk_property_names(schema, names)
    return sorted(name for name in names if any(token in name.lower() for token in _MARKUP_SUBSTRINGS))


def _live_family_schemas() -> dict[str, dict[str, Any]]:
    """Populate the registry (as production does) and return live-family schemas."""
    build_tool_descriptors()  # drives the CLI payload discovery that fills SCHEMA_REGISTRY
    return {key: SCHEMA_REGISTRY[key].model_json_schema() for key in SCHEMA_REGISTRY if key.startswith(_LIVE_PREFIX)}


def test_live_family_result_schemas_carry_no_raw_markup_field() -> None:
    schemas = _live_family_schemas()
    # Anti-vacuity: the live family must actually be present, and it must include
    # the pull verbs whose payloads originate from the AEAT portal.
    assert len(schemas) >= 20, f"live family under-populated ({len(schemas)}); registry not driven"
    pull_keys = [key for key in schemas if key.rsplit(".", 1)[-1].startswith("pull")]
    assert len(pull_keys) >= 5, f"expected the app.live.*.pull* verbs to be present, saw {pull_keys}"

    offenders: dict[str, list[str]] = {}
    for key, schema in schemas.items():
        markup = _markup_fields(schema)
        if markup:
            offenders[key] = markup
    assert offenders == {}, (
        "live-family result schemas relay raw portal markup instead of typed fields: "
        f"{offenders}. Extract typed fields from the portal content; never surface a raw "
        "HTML/markup blob to the model."
    )


def test_detector_flags_a_raw_markup_relay_field() -> None:
    # Anti-tautology negative control: a schema that DOES declare a raw-markup
    # field is caught. Proves the gate above would fail the moment such a field
    # were added to a live-family result model. This model is never registered.
    class _RawPortalRelay(OutputSchema):
        expediente_id: str = Field(min_length=1)
        raw_html: str = Field(min_length=1)

    flagged = _markup_fields(_RawPortalRelay.model_json_schema())
    assert flagged == ["raw_html"], f"detector missed the raw-markup relay field: {flagged}"

    # A nested raw-markup field (via $defs) is caught too.
    class _Row(OutputSchema):
        page_source: str = Field(min_length=1)

    class _RawPortalRelayNested(OutputSchema):
        rows: tuple[_Row, ...] = ()

    assert _markup_fields(_RawPortalRelayNested.model_json_schema()) == ["page_source"]


def test_typed_portal_fields_are_not_false_flagged() -> None:
    # A typed value model that extracts portal content into named fields (a CSV
    # verification code, an id, an observaciones text note, a source URL) is NOT
    # a markup relay: the detector must leave it clean, or it would force the very
    # inlining H7 forbids to be worked around.
    class _TypedPortalObservation(OutputSchema):
        justificante_csv: str = Field(min_length=1)
        expediente_id: str = Field(min_length=1)
        observaciones: str = ""
        source_url: str = ""

    assert _markup_fields(_TypedPortalObservation.model_json_schema()) == []
