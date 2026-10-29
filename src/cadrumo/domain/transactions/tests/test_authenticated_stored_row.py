"""An authenticated stored-row decode skips only the derived-id re-hash.

The secure store authenticates each stored row under the AEAD binding of its
namespace, object key, schema version and revision, and the transaction id is
that object key. A row decoded through
:func:`validate_authenticated_stored_transaction_json` therefore skips the
re-hash of its id and nothing else: every structural, field and dated registry
refusal still fires, and every other construction path validates in full.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.type_adapters import STRICT_STR_KEYED_MAPPING_ADAPTER
from ...calculations.registry.authority import bundled_indexed_authority
from ..models import Transaction, validate_authenticated_stored_transaction_json
from .varied_ledger_seed import varied_transactions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_ENTRY_POINT = "validate_authenticated_stored_transaction_json"
_PRIVATE_CONTEXT_NAMES = frozenset({"_AUTHENTICATED_STORED_ROW", "_AuthenticatedStoredRow"})
_MODELS_PATH = Path("src/cadrumo/domain/transactions/models.py")
_REPOSITORY_PATH = Path("src/cadrumo/adapters/persistence/profile/transactions.py")
#: The only functions allowed to decode a row as authenticated: the repository's
#: read paths, each running on bytes the store decrypted in the same call.
_AUTHENTICATED_READERS = frozenset({"_decode_catalogue_row", "_decode_targeted_row"})


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _payload(transaction: Transaction) -> dict[str, object]:
    return STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(json.loads(transaction.model_dump_json()))


def _authenticated(payload: dict[str, object]) -> Transaction:
    return validate_authenticated_stored_transaction_json(Transaction, json.dumps(payload).encode("utf-8"))


def _full(payload: dict[str, object]) -> Transaction:
    return Transaction.model_validate_json(json.dumps(payload))


def _row(predicate: Callable[[Transaction], bool]) -> dict[str, object]:
    for transaction in varied_transactions():
        if predicate(transaction):
            return _payload(transaction)
    raise AssertionError("the varied seed carries no matching row")


def _another_row_id(payload: dict[str, object]) -> str:
    for transaction in varied_transactions():
        if transaction.transaction_id != payload["transaction_id"]:
            return transaction.transaction_id
    raise AssertionError("the varied seed carries a single row")


@pytest.mark.parametrize("count", [1, 7, 96, 193])
def test_an_authenticated_decode_equals_a_full_decode(count: int) -> None:
    """Values, JSON form and set fields match for every row shape the seed reaches."""
    for row in varied_transactions(count):
        stored = row.model_dump_json()

        authenticated = validate_authenticated_stored_transaction_json(Transaction, stored.encode("utf-8"))
        full = Transaction.model_validate_json(stored)

        assert authenticated == full == row
        assert authenticated.model_dump_json() == full.model_dump_json() == stored
        assert authenticated.model_dump(mode="python") == full.model_dump(mode="python")
        assert authenticated.model_fields_set == full.model_fields_set


def test_only_the_derived_id_rehash_is_skipped() -> None:
    """A row whose id no longer derives from its raw record loads only when authenticated."""
    payload = _row(lambda _row: True)
    payload["transaction_id"] = _another_row_id(payload)

    with pytest.raises(ValidationError) as caught:
        _full(payload)
    assert [error["msg"] for error in caught.value.errors()] == [
        "Value error, transaction_id must match the stable hash derived from raw",
    ]

    restored = _authenticated(payload)
    assert restored.transaction_id == payload["transaction_id"]


def _raw(payload: dict[str, object]) -> dict[str, object]:
    raw = payload["raw"]
    assert isinstance(raw, dict)
    return STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(raw)


def _negative_raw_amount(payload: dict[str, object]) -> None:
    raw = _raw(payload)
    raw["amount"] = "-1.00"
    payload["raw"] = raw


def _set(field: str, value: object) -> Callable[[dict[str, object]], None]:
    def mutate(payload: dict[str, object]) -> None:
        payload[field] = value

    return mutate


def _gross_mismatch(payload: dict[str, object]) -> None:
    payload["taxable_base"] = "99.00"


def _has_tax_substrate(row: Transaction) -> bool:
    return (
        row.taxable_base is not None
        and row.iva_amount is not None
        and row.raw.currency == "EUR"
        and row.cash_accounting_treatment == "none"
        and row.exemption_article is None
    )


def _plain(row: Transaction) -> bool:
    return row.raw.currency == "EUR" and row.cash_accounting_treatment == "none" and row.concepto_ingreso is None


#: Each refusal the authenticated decode keeps, with a row that reaches it.
_KEPT_REFUSALS: dict[str, tuple[Callable[[Transaction], bool], Callable[[dict[str, object]], None]]] = {
    "negative raw amount": (_plain, _negative_raw_amount),
    "unknown plain enum": (_plain, _set("direction", "sideways")),
    "absent required enum": (_plain, _set("direction", None)),
    "naive lifecycle timestamp": (_plain, _set("modified_at", "2026-01-01T00:00:00")),
    "non-UTC lifecycle timestamp": (_plain, _set("created_at", "2026-01-01T00:00:00+01:00")),
    "negative tax amount": (_has_tax_substrate, _set("iva_amount", "-21.00")),
    "percentage IVA rate": (_has_tax_substrate, _set("iva_rate", "21")),
    "unknown field": (_plain, _set("unexpected", "value")),
    "malformed id": (_plain, _set("transaction_id", "not-a-hex-id")),
    "blank foreign key": (_plain, _set("category_id", "   ")),
    "business share without MIXED": (_plain, _set("business_pct", "0.50")),
    "half-applied FX conversion": (_plain, _set("fx_rate", "1.10")),
    "undeclared registry token": (_plain, _set("concepto_ingreso", "bogus_concepto")),
    "undeclared cash-accounting treatment": (_plain, _set("cash_accounting_treatment", "deferred")),
    "undeclared identification state": (_plain, _set("counterparty_identification_state", "XX")),
    "gross that does not reconstitute": (_has_tax_substrate, _gross_mismatch),
}


@pytest.mark.parametrize("refusal", sorted(_KEPT_REFUSALS))
def test_every_kept_refusal_fires_identically_on_an_authenticated_row(refusal: str) -> None:
    """The authenticated decode refuses exactly what the full decode refuses, in the same words."""
    predicate, mutate = _KEPT_REFUSALS[refusal]
    payload = _row(predicate)
    mutate(payload)

    with pytest.raises(ValidationError) as full:
        _full(payload)
    with pytest.raises(ValidationError) as authenticated:
        _authenticated(payload)

    assert _comparable(authenticated.value) == _comparable(full.value)
    assert _comparable(full.value)


def _comparable(error: ValidationError) -> list[tuple[object, ...]]:
    """Each refusal's location, kind, words and registered cause type."""
    comparable: list[tuple[object, ...]] = []
    for detail in error.errors(include_url=False):
        raised = detail.get("ctx", {}).get("error")
        cause = type(raised.__cause__) if isinstance(raised, BaseException) else None
        comparable.append((detail["loc"], detail["type"], detail["msg"], cause))
    return comparable


@pytest.mark.parametrize(
    "context",
    [
        {"skipped_checks": frozenset({"derived_transaction_id"})},
        {"derived_transaction_id": True},
        frozenset({"derived_transaction_id"}),
        "derived_transaction_id",
    ],
)
def test_no_context_value_of_its_own_skips_the_rehash(context: object) -> None:
    """Only the private authenticated-row context skips a check; a lookalike does not."""
    payload = _row(lambda _row: True)
    payload["transaction_id"] = _another_row_id(payload)

    with pytest.raises(ValidationError):
        Transaction.model_validate_json(json.dumps(payload), context=context)
    with pytest.raises(ValidationError):
        Transaction.model_validate(_authenticated(payload).model_dump(), context=context)


def _source_files() -> Iterator[Path]:
    for top in ("src", "dev"):
        for path in sorted((_REPOSITORY_ROOT / top).rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def _references(tree: ast.AST, names: frozenset[str]) -> Iterator[tuple[ast.AST, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in names:
            yield node, node.id
        elif isinstance(node, ast.Attribute) and node.attr in names:
            yield node, node.attr
        elif isinstance(node, ast.alias) and node.name in names:
            yield node, node.name


def _enclosing_functions(tree: ast.AST) -> dict[ast.AST, str]:
    owners: dict[ast.AST, str] = {}
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            for node in ast.walk(function):
                owners[node] = function.name
    return owners


def _is_test_module(relative: Path) -> bool:
    return "tests" in relative.parts


def test_only_the_repository_read_paths_decode_a_row_as_authenticated() -> None:
    """TEETH: wiring the authenticated decode into any other path, a write included, fails here."""
    offenders: list[str] = []
    for path in _source_files():
        relative = path.relative_to(_REPOSITORY_ROOT)
        source = path.read_text(encoding="utf-8")
        if _ENTRY_POINT not in source and not any(name in source for name in _PRIVATE_CONTEXT_NAMES):
            continue
        tree = ast.parse(source)
        owners = _enclosing_functions(tree)
        for node, name in _references(tree, frozenset({_ENTRY_POINT}) | _PRIVATE_CONTEXT_NAMES):
            if relative == _MODELS_PATH:
                continue
            if name in _PRIVATE_CONTEXT_NAMES:
                offenders.append(f"{relative}:{getattr(node, 'lineno', '?')} references {name}")
                continue
            if _is_test_module(relative):
                continue
            if relative == _REPOSITORY_PATH and (
                isinstance(node, ast.alias) or owners.get(node) in _AUTHENTICATED_READERS
            ):
                continue
            offenders.append(f"{relative}:{getattr(node, 'lineno', '?')} in {owners.get(node, '<module>')}")

    assert offenders == []


def test_the_gate_sees_the_repository_read_paths() -> None:
    """The caller gate is only as good as its view of the real call sites."""
    tree = ast.parse((_REPOSITORY_ROOT / _REPOSITORY_PATH).read_text(encoding="utf-8"))
    owners = _enclosing_functions(tree)
    callers = {
        owners.get(node)
        for node, _name in _references(tree, frozenset({_ENTRY_POINT}))
        if not isinstance(node, ast.alias)
    }

    assert callers == _AUTHENTICATED_READERS
