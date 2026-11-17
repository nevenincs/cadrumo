"""Every registered result that serves a ledger transaction names its link fields in the operator's language.

``ledger view`` and ``ledger list`` take the operator's language on the request and name each
transaction's link fields in it. A mutation that returns the same transaction projection must take the
language from the same source, or its result names the same row in another language.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import UnionType
from typing import get_args, get_origin

import pytest
from pydantic import BaseModel

from cadrumo.application.ledger.transaction_projection import LedgerTransactionProjection
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _models_in(annotation: object) -> Iterator[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    if get_origin(annotation) is not None or isinstance(annotation, UnionType):
        for argument in get_args(annotation):
            yield from _models_in(argument)


def _serves_transaction(model: type[BaseModel], seen: set[type[BaseModel]]) -> bool:
    if model is LedgerTransactionProjection:
        return True
    if model in seen:
        return False
    seen.add(model)
    return any(
        _serves_transaction(nested, seen)
        for field in model.model_fields.values()
        for nested in _models_in(field.annotation)
    )


def _names_the_language(request: type[BaseModel]) -> bool:
    return any(
        OutputLanguage in set(get_args(field.annotation)) | {field.annotation}
        for field in request.model_fields.values()
    )


def test_every_result_serving_a_ledger_transaction_takes_the_operator_language() -> None:
    registry = build_production_operation_registry()
    serving = {
        definition.definition_id: definition.request_type
        for definition in registry.definitions
        if definition.result_type is not None and _serves_transaction(definition.result_type, set())
    }

    assert {"ledger.view", "ledger.list"} <= {identifier.removeprefix("app.") for identifier in serving}, sorted(
        serving
    )
    silent = sorted(identifier for identifier, request in serving.items() if not _names_the_language(request))
    assert silent == [], silent
