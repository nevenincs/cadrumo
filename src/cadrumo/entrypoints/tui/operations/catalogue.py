"""Every registered operation, as the Operations destination lists, groups and searches them.

The catalogue is a projection of the operation registry and of nothing else:
it has one entry for each public contract the registry publishes, so an
operation registered later is offered without a change here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType

from pydantic import BaseModel

from ....application.operations.registry import OperationPublicDefinitionContractV1, OperationRegistry
from ....core.hashing import sha256_hex


@dataclass(frozen=True, slots=True)
class OperationCatalogueEntryV1:
    """One registered operation and the typed input a person submits for it.

    ``input_type`` is the registered request model, except for an operation
    that declares a transient financial operand: every frontend submits the
    typed operator input for those, and the runtime builds the request from it.
    """

    contract: OperationPublicDefinitionContractV1
    summary: str
    input_type: type[BaseModel]
    input_json_schema: Mapping[str, object]
    #: The model the registered public result schema binds, which a result
    #: projector may make another model than the executor's own result.
    result_type: type[BaseModel] | None
    typed_operator_input: bool

    @property
    def definition_id(self) -> str:
        """Return the operation's registered identity."""
        return self.contract.definition_id

    @property
    def accepts_replay_key(self) -> bool:
        """Report whether a submission may carry a replay key.

        The typed operator input has no registered request to bind a key to, so
        the runtime refuses a key there on every frontend.
        """
        return not self.typed_operator_input

    @property
    def family(self) -> str:
        """Return the leading segment the operation's identity is grouped under."""
        return self.definition_id.split(".", 1)[0]

    @property
    def focus_token(self) -> str:
        """Return the stable token a navigation focus carries for this operation."""
        return sha256_hex(self.definition_id.encode("utf-8"))

    def matches(self, terms: tuple[str, ...]) -> bool:
        """Report whether every search term occurs in the identity or the description."""
        haystack = f"{self.definition_id} {self.summary}".casefold()
        return all(term in haystack for term in terms)


class OperationCatalogueV1:
    """The immutable, identity-ordered inventory of registered operations."""

    __slots__ = ("_by_id", "_by_token", "_entries")

    def __init__(self, entries: tuple[OperationCatalogueEntryV1, ...]) -> None:
        """Index the entries by identity and by focus token."""
        self._entries = entries
        self._by_id = MappingProxyType({entry.definition_id: entry for entry in entries})
        self._by_token = MappingProxyType({entry.focus_token: entry for entry in entries})

    @property
    def entries(self) -> tuple[OperationCatalogueEntryV1, ...]:
        """Return every registered operation in identity order."""
        return self._entries

    def entry(self, definition_id: str) -> OperationCatalogueEntryV1 | None:
        """Return one operation by its registered identity."""
        return self._by_id.get(definition_id)

    def entry_for_token(self, focus_token: str) -> OperationCatalogueEntryV1 | None:
        """Return the operation a navigation focus token names."""
        return self._by_token.get(focus_token)

    def search(self, query: str) -> tuple[OperationCatalogueEntryV1, ...]:
        """Return the operations whose identity or description holds every word of ``query``."""
        terms = tuple(query.casefold().split())
        return tuple(entry for entry in self._entries if entry.matches(terms))

    def grouped(self, query: str = "") -> tuple[tuple[str, tuple[OperationCatalogueEntryV1, ...]], ...]:
        """Return the matching operations under their families, in family order."""
        families: dict[str, list[OperationCatalogueEntryV1]] = {}
        for entry in self.search(query):
            families.setdefault(entry.family, []).append(entry)
        return tuple((family, tuple(families[family])) for family in sorted(families))


def _summary(schema: Mapping[str, object]) -> str:
    description = schema.get("description")
    return " ".join(description.split()) if isinstance(description, str) else ""


def build_operation_catalogue(registry: OperationRegistry) -> OperationCatalogueV1:
    """Project every public contract of ``registry`` onto one catalogue entry."""
    entries: list[OperationCatalogueEntryV1] = []
    for contract in registry.public_contract_set.definitions:
        definition = registry.lookup(contract.definition_id)
        typed_operator_input = contract.transient_financial_operand is not None
        if typed_operator_input:
            # Imported on use: only the two operations that take the typed operator input need it.
            from ....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
            from ....application.operations.registry_schema_validation import strict_model_json_schema

            input_type: type[BaseModel] = ModeloEditOperatorInputV2
            schema: Mapping[str, object] = strict_model_json_schema(ModeloEditOperatorInputV2)
        else:
            input_type = definition.request_type
            schema = registry.describe_public_definition(contract.definition_id).request_json_schema
        entries.append(
            OperationCatalogueEntryV1(
                contract=contract,
                summary=_summary(schema),
                input_type=input_type,
                input_json_schema=schema,
                result_type=(
                    None
                    if contract.result_schema is None
                    else registry.lookup_public_schema_binding(contract.result_schema).model_type
                ),
                typed_operator_input=typed_operator_input,
            )
        )
    return OperationCatalogueV1(tuple(entries))


class OperationCatalogueSourceV1:
    """Build the catalogue once, on first use, for every surface that offers operations.

    Composing the registry imports every operation family, so it is deferred
    until a person opens the destination or searches the palette, and callers
    read it off the event loop.
    """

    def __init__(self, registry: Callable[[], OperationRegistry]) -> None:
        """Retain the registry door without composing anything."""
        self._registry = registry
        self._catalogue: OperationCatalogueV1 | None = None
        self._lock = Lock()

    def load(self) -> OperationCatalogueV1:
        """Return the catalogue, composing the registry on the first call only."""
        with self._lock:
            if self._catalogue is None:
                self._catalogue = build_operation_catalogue(self._registry())
            return self._catalogue


__all__ = [
    "OperationCatalogueEntryV1",
    "OperationCatalogueSourceV1",
    "OperationCatalogueV1",
    "build_operation_catalogue",
]
