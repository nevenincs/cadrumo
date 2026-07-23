"""Render-time copy resolution and page-copy assembly over real sources.

Every scenario drives the copy assembler through the public
``cadrumo.application.flows`` facade. Locale keys resolve against the real
bundled catalogue; ``SCHEMA_FIELD`` references resolve through real
resolver functions this module registers — genuine resolver
implementations returning strings from a literal namespace table, not
mocks.

Registry assumption: the copy-source registry is process-global with no
unregister verb. This module registers only ``SCHEMA_FIELD`` resolvers,
each scoped to its own reference namespace and returning ``None`` outside
it, so it coexists with any other ``SCHEMA_FIELD`` registrant (the modelo
work wizard registers one under the ``modelo-work:`` namespace) without
collision. It never registers ``TERMINOLOGY_CONCEPT``, which no production
code registers either, so that kind stays genuinely resolver-less for the
unregistered-kind refusal. Registration happens at module scope because
the sibling flow test modules touch no copy sources.

Assertions read the resolver's own returned strings and error message
*keys*, never localized prose.
"""

from __future__ import annotations

import pytest

from ....core.flows import CopyRefKind, FlowWidgetKind
from ....core.i18n import tr
from .. import (
    CopyRef,
    FlowChoice,
    FlowCopyResolutionError,
    FlowPage,
    assemble_page_copy,
    register_copy_source,
    resolve_copy,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A real bundled locale key present in the shipped catalogue.
_REAL_LOCALE_KEY = "wizard.setup.title"

# Namespace-scoped SCHEMA_FIELD table this module owns end-to-end.
_SCHEMA_TABLE: dict[str, str] = {
    "schema-test:prompt": "PROMPT-COPY",
    "schema-test:help": "HELP-COPY",
    "schema-test:hint": "HINT-COPY",
    "schema-test:failure": "FAILURE-COPY",
    "schema-test:choice-label": "CHOICE-LABEL",
    "schema-test:choice-desc": "CHOICE-DESC",
    "schema-test:choice-prov": "CHOICE-PROV",
}


def _resolve_schema_test(ref: str) -> str | None:
    """Resolve the ``schema-test:`` namespace; ``None`` for anything else."""
    return _SCHEMA_TABLE.get(ref)


def _resolve_namespace_a(ref: str) -> str | None:
    """Resolve only the ``schema-a:`` namespace."""
    return "NAMESPACE-A" if ref.startswith("schema-a:") else None


def _resolve_namespace_b(ref: str) -> str | None:
    """Resolve only the ``schema-b:`` namespace."""
    return "NAMESPACE-B" if ref.startswith("schema-b:") else None


# Three distinct SCHEMA_FIELD resolvers, each scoped to a disjoint
# namespace. Resolution tries them in registration order, first non-None
# winning, so disjoint namespaces make the composition order-independent.
register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_schema_test)
register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_namespace_a)
register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_namespace_b)


def _schema_ref(ref: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=ref)


def test_locale_key_resolves_against_the_real_catalogue() -> None:
    ref = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=_REAL_LOCALE_KEY)
    resolved = resolve_copy(ref)

    # Resolves through the canonical tr catalogue, not a raw key leak.
    assert resolved == tr(_REAL_LOCALE_KEY)
    assert resolved != _REAL_LOCALE_KEY


def test_unresolvable_locale_key_refuses_loudly() -> None:
    ref = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="flows.__definitely_absent_key__")
    with pytest.raises(FlowCopyResolutionError) as excinfo:
        resolve_copy(ref)

    assert excinfo.value.translated_message == "application.flows.errors.copy_locale_key_unresolved"


def test_kind_without_a_registered_resolver_refuses() -> None:
    # No production or test code registers TERMINOLOGY_CONCEPT.
    ref = CopyRef(kind=CopyRefKind.TERMINOLOGY_CONCEPT, ref="tema-anything")
    with pytest.raises(FlowCopyResolutionError) as excinfo:
        resolve_copy(ref)

    assert excinfo.value.translated_message == "application.flows.errors.copy_source_unregistered"
    context = excinfo.value.context
    assert context is not None
    assert context["kind"] == CopyRefKind.TERMINOLOGY_CONCEPT.value


def test_registered_resolvers_present_but_none_match_refuses() -> None:
    # SCHEMA_FIELD has resolvers, but none claim this namespace.
    ref = _schema_ref("schema-unclaimed:field")
    with pytest.raises(FlowCopyResolutionError) as excinfo:
        resolve_copy(ref)

    assert excinfo.value.translated_message == "application.flows.errors.copy_ref_unresolved"


def test_second_distinct_resolver_dispatches_by_namespace_in_order() -> None:
    # Two distinct resolvers on the same kind, each serving a disjoint
    # namespace; resolution consults them in registration order.
    assert resolve_copy(_schema_ref("schema-a:x")) == "NAMESPACE-A"
    assert resolve_copy(_schema_ref("schema-b:y")) == "NAMESPACE-B"


def test_assemble_page_copy_composes_every_slot_including_choices() -> None:
    page = FlowPage(
        id="p_assemble",
        widget=FlowWidgetKind.SELECT,
        prompt=_schema_ref("schema-test:prompt"),
        help=_schema_ref("schema-test:help"),
        format_hint=_schema_ref("schema-test:hint"),
        failure_modes=(_schema_ref("schema-test:failure"),),
        choices=(
            FlowChoice(
                value="c1",
                label=_schema_ref("schema-test:choice-label"),
                description=_schema_ref("schema-test:choice-desc"),
                provenance=_schema_ref("schema-test:choice-prov"),
            ),
        ),
        answer_type=str,
    )
    copy = assemble_page_copy(page)

    assert copy.prompt == "PROMPT-COPY"
    assert copy.help == "HELP-COPY"
    assert copy.format_hint == "HINT-COPY"
    assert copy.failure_modes == ("FAILURE-COPY",)
    assert len(copy.choices) == 1
    choice = copy.choices[0]
    assert choice.value == "c1"
    assert choice.label == "CHOICE-LABEL"
    assert choice.description == "CHOICE-DESC"
    assert choice.provenance == "CHOICE-PROV"


def test_registering_the_same_callable_twice_refuses() -> None:
    with pytest.raises(FlowCopyResolutionError) as excinfo:
        register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_schema_test)

    assert excinfo.value.translated_message == "application.flows.errors.copy_source_duplicate"


def test_registering_a_locale_key_source_refuses() -> None:
    with pytest.raises(FlowCopyResolutionError) as excinfo:
        register_copy_source(CopyRefKind.LOCALE_KEY, _resolve_namespace_a)

    assert excinfo.value.translated_message == "application.flows.errors.copy_source_locale_builtin"
