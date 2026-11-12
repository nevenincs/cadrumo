"""Assemble the grouped read of related profile rows from the record and the ledger.

The relation between rows is the schema's: a field declaring ``references_section``
holds the row key of a row in that section. A group is headed by a row of the
kind's section that names no other stored row; every row naming a row already in
the group joins it as a member, under the row it names. A row that names another
row but is reached from no head (two accessories naming each other) heads a group
of its own, so no stored row of the kind's section is left out.

Ledger rows join the group whose row they name, through the ledger field that
carries a reference to that section. Every ledger row is read, in any lifecycle
state, because a row in any state keeps the rental row it names from removal.

Facts read here are private; nothing in this module logs them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...core.config import override_settings
from ...core.i18n.render import tr
from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION, rows_from_facts
from ..ledger.entry_options_operation import ENTRY_OPTION_LABEL_PREFIX
from ..operations.error_detail import served_words_language
from ..operations.public_scalar import PublicDecimal
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_path_values
from .record_group_contracts import (
    PROFILE_RECORD_GROUPS_MAX_RESULT_BYTES,
    ProfileRecordGroupItem,
    ProfileRecordGroupKind,
    ProfileRecordGroupsRefusalCode,
    ProfileRecordGroupsRequest,
    ProfileRecordGroupsResult,
    ProfileRecordGroupStreamItem,
    ProfileRecordLedgerRowItem,
    ProfileRecordMemberItem,
)
from .record_group_words import group_kind_words, ledger_row_kind_words, member_kind_words, refusal_words, row_actions
from .record_row_words import record_relation_words, record_row_summary_words, summarised_sections

if TYPE_CHECKING:
    from ...core.external_constants import OutputLanguage
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.transactions.models import Transaction
    from ...domain.user_profile.schema import ProfileSchemaDefinition

type LedgerRowsLoader = Callable[[str], Iterable[Transaction]]
"""Read every ledger row of one profile, in any lifecycle state, without writing it."""

_HEAD_SECTIONS: Final[Mapping[ProfileRecordGroupKind, str]] = {
    ProfileRecordGroupKind.RENTAL_PROPERTY: INMUEBLE_SECTION,
}
_LEDGER_LINKS: Final[Mapping[str, Callable[[Transaction], str | None]]] = {
    INMUEBLE_SECTION: lambda row: row.inmueble_ref,
    ARRENDAMIENTO_SECTION: lambda row: row.arrendamiento_ref,
}
_CONCEPT_WORDS_PREFIX: Final = f"{ENTRY_OPTION_LABEL_PREFIX}gasto_capital_inmobiliario."


@dataclass(frozen=True, slots=True)
class _Row:
    section_key: str
    row_key: int
    values: Mapping[str, str]

    @property
    def ref(self) -> str:
        return f"{self.section_key}.{self.row_key}"


@dataclass(frozen=True, slots=True)
class _Edge:
    child: str
    parent: str
    relation: tuple[str, str]


def _stored_rows(path_values: Mapping[str, str], sections: Iterable[str]) -> dict[str, _Row]:
    rows: dict[str, _Row] = {}
    for section_key in sections:
        for row_key, values in sorted(rows_from_facts(section_key, path_values).items()):
            row = _Row(section_key, row_key, values)
            rows[row.ref] = row
    return rows


def _edges(rows: Mapping[str, _Row], schema: ProfileSchemaDefinition) -> tuple[_Edge, ...]:
    """Return each stored reference from one row to another stored row, in row order."""
    edges: list[_Edge] = []
    for row in rows.values():
        for section_key, field_key, target in schema.row_references():
            named = row.values.get(field_key) if section_key == row.section_key else None
            parent = f"{target}.{named}" if named is not None else None
            if parent is not None and parent in rows and parent != row.ref:
                edges.append(_Edge(child=row.ref, parent=parent, relation=(section_key, field_key)))
    return tuple(edges)


def _members(head: str, children: Mapping[str, list[_Edge]], placed: set[str]) -> tuple[_Edge, ...]:
    """Walk breadth first from ``head``, taking each row not yet placed in a group, and mark it placed."""
    members: list[_Edge] = []
    frontier = [head]
    while frontier:
        fresh = [edge for edge in children.get(frontier.pop(0), ()) if edge.child not in placed]
        placed.update(edge.child for edge in fresh)
        members.extend(fresh)
        frontier.extend(edge.child for edge in fresh)
    return tuple(members)


def _group_order(
    rows: Mapping[str, _Row], edges: tuple[_Edge, ...], head_section: str
) -> list[tuple[str, tuple[_Edge, ...]]]:
    """Return each group as its head ref and its member edges, breadth first from the head."""
    children: dict[str, list[_Edge]] = {}
    for edge in edges:
        children.setdefault(edge.parent, []).append(edge)
    naming = {edge.child for edge in edges}
    candidates = [ref for ref, row in rows.items() if row.section_key == head_section]
    placed: set[str] = set()
    groups: list[tuple[str, tuple[_Edge, ...]]] = []
    for head in (*(ref for ref in candidates if ref not in naming), *candidates):
        if head not in placed:
            placed.add(head)
            groups.append((head, _members(head, children, placed)))
    return groups


def _ledger_index(rows: Mapping[str, _Row], ledger_rows: Iterable[Transaction]) -> dict[str, list[Transaction]]:
    index: dict[str, list[Transaction]] = {}
    for transaction in ledger_rows:
        for section_key, link in _LEDGER_LINKS.items():
            named = link(transaction)
            ref = f"{section_key}.{named}" if named is not None else None
            if ref is not None and ref in rows:
                index.setdefault(ref, []).append(transaction)
    return index


def _ledger_item(
    group_key: str, linked: tuple[str, Transaction], place: tuple[int, int], language: OutputLanguage
) -> ProfileRecordLedgerRowItem:
    """Serve one ledger row at ``place``, its index among the group's ``total`` ledger rows."""
    linked_ref, transaction = linked
    concept = None if transaction.gasto_capital_inmobiliario is None else str(transaction.gasto_capital_inmobiliario)
    return ProfileRecordLedgerRowItem(
        group_key=group_key,
        linked_ref=linked_ref,
        transaction_id=transaction.transaction_id,
        booked_date=transaction.raw.booked_date,
        amount=PublicDecimal(decimal=str(transaction.raw.amount)),
        currency=transaction.raw.currency,
        direction=transaction.direction,
        description=transaction.raw.description,
        lifecycle_state=transaction.lifecycle_state,
        concept=concept,
        concept_words=None if concept is None else tr(f"{_CONCEPT_WORDS_PREFIX}{concept}"),
        concept_words_language=None if concept is None else language,
        kind_words=ledger_row_kind_words(),
        kind_words_language=language,
        ledger_row_index=place[0],
        ledger_row_total=place[1],
    )


def _member_item(group_key: str, edge: _Edge, row: _Row, language: OutputLanguage) -> ProfileRecordMemberItem:
    return ProfileRecordMemberItem(
        group_key=group_key,
        row_ref=row.ref,
        parent_ref=edge.parent,
        section_key=row.section_key,
        row_key=str(row.row_key),
        relation=".".join(edge.relation),
        relation_words=record_relation_words(*edge.relation),
        relation_words_language=language,
        summary_words=record_row_summary_words(row.section_key, row.row_key, row.values),
        summary_words_language=language,
        kind_words=member_kind_words(row.section_key),
        kind_words_language=language,
        actions=row_actions(row.section_key, language),
    )


def _group_items(
    group: tuple[str, tuple[_Edge, ...]],
    rows: Mapping[str, _Row],
    ledger: Mapping[str, list[Transaction]],
    kind: ProfileRecordGroupKind,
    language: OutputLanguage,
) -> tuple[ProfileRecordGroupStreamItem, ...]:
    head, edges = rows[group[0]], group[1]
    linked = sorted(
        (
            (ref, transaction)
            for ref in (head.ref, *(edge.child for edge in edges))
            for transaction in ledger.get(ref, ())
        ),
        key=lambda pair: (pair[1].raw.booked_date, pair[1].transaction_id),
    )
    members = tuple(_member_item(head.ref, edge, rows[edge.child], language) for edge in edges)
    head_item = ProfileRecordGroupItem(
        group_key=head.ref,
        payload_kind=kind,
        section_key=head.section_key,
        row_key=str(head.row_key),
        summary_words=record_row_summary_words(head.section_key, head.row_key, head.values),
        summary_words_language=language,
        member_count=len(members),
        ledger_row_count=len(linked),
        kind_words=group_kind_words(kind),
        kind_words_language=language,
        actions=row_actions(head.section_key, language),
    )
    return (
        head_item,
        *members,
        *(_ledger_item(head.ref, pair, (index, len(linked)), language) for index, pair in enumerate(linked)),
    )


def record_group_items(
    path_values: Mapping[str, str],
    *,
    schema: ProfileSchemaDefinition,
    kind: ProfileRecordGroupKind,
    ledger_rows: Iterable[Transaction],
    language: OutputLanguage,
) -> tuple[ProfileRecordGroupStreamItem, ...]:
    """Return every group of ``kind``: its head, its members and its ledger rows, in group order."""
    rows = _stored_rows(path_values, sorted(summarised_sections()))
    edges = _edges(rows, schema)
    ledger = _ledger_index(rows, ledger_rows)
    return tuple(
        item
        for group in _group_order(rows, edges, _HEAD_SECTIONS[kind])
        for item in _group_items(group, rows, ledger, kind, language)
    )


def ledger_rows_digest(items: Iterable[ProfileRecordGroupStreamItem]) -> str:
    """Fingerprint the ledger rows a stream serves, so a continuation can tell they moved."""
    digest = hashlib.sha256()
    for item in items:
        if isinstance(item, ProfileRecordLedgerRowItem):
            digest.update(json.dumps(item.model_dump(mode="json"), sort_keys=True).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def _refused(
    common: dict[str, object], code: ProfileRecordGroupsRefusalCode, *, total_items: int
) -> ProfileRecordGroupsResult:
    """Refuse the page with the served words of ``code``; the output language is already bound."""
    return ProfileRecordGroupsResult.model_validate(
        {
            **common,
            "outcome": "refused",
            "refusal_code": code,
            "refusal_words": refusal_words(code),
            "refusal_words_language": served_words_language(),
            "total_items": total_items,
        }
    )


def _page(
    request: ProfileRecordGroupsRequest,
    common: dict[str, object],
    stream: tuple[ProfileRecordGroupStreamItem, ...],
) -> ProfileRecordGroupsResult:
    """Return the longest page within the item and byte bounds, refusing an item that fits no page."""
    if request.cursor > len(stream):
        return _refused(common, ProfileRecordGroupsRefusalCode.STALE_REVISION, total_items=len(stream))
    candidates = stream[request.cursor : request.cursor + request.limit]

    def page_for(count: int) -> ProfileRecordGroupsResult:
        end = request.cursor + count
        return ProfileRecordGroupsResult.model_validate(
            {
                **common,
                "outcome": "page",
                "total_items": len(stream),
                "items": candidates[:count],
                "next_cursor": end if end < len(stream) else None,
            }
        )

    def fits(page: ProfileRecordGroupsResult) -> bool:
        return len(page.model_dump_json().encode("utf-8")) <= PROFILE_RECORD_GROUPS_MAX_RESULT_BYTES

    whole = page_for(len(candidates))
    if fits(whole):
        return whole
    low, high = 0, len(candidates) - 1
    while low < high:
        count = (low + high + 1) // 2
        if fits(page_for(count)):
            low = count
        else:
            high = count - 1
    if low == 0 and candidates:
        return _refused(common, ProfileRecordGroupsRefusalCode.ITEM_TOO_LARGE, total_items=len(stream))
    return page_for(low)


def read_profile_record_groups(
    request: ProfileRecordGroupsRequest,
    *,
    authority_operation: PinnedAuthorityOperation,
    ledger_rows: LedgerRowsLoader,
) -> ProfileRecordGroupsResult:
    """Build one bounded page of the groups from the exact current encrypted record and its ledger."""
    profile_id = str(request.profile_id)
    decode = authority_operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    with override_settings(cadrumo_output_language=request.output_language.value):
        stream = record_group_items(
            record_to_path_values(record),
            schema=decode.schema,
            kind=request.group_kind,
            ledger_rows=ledger_rows(profile_id),
            language=served_words_language(),
        )
        common: dict[str, object] = {
            "profile_id": request.profile_id,
            "group_kind": request.group_kind,
            "record_revision": record.record_revision,
            "content_digest": record.content_digest,
            "ledger_digest": ledger_rows_digest(stream),
            "cursor": request.cursor,
        }
        if request.expected_revision is not None and (
            request.expected_revision != record.record_revision
            or request.expected_content_digest != record.content_digest
            or request.expected_ledger_digest != common["ledger_digest"]
        ):
            return _refused(common, ProfileRecordGroupsRefusalCode.STALE_REVISION, total_items=0)
        return _page(request, common, stream)


__all__ = [
    "LedgerRowsLoader",
    "ledger_rows_digest",
    "read_profile_record_groups",
    "record_group_items",
]
