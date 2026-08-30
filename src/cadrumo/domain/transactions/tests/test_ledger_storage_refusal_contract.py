"""The ledger-storage key-derivation refusals render as their key, never as prose.

:class:`~cadrumo.domain.transactions.LedgerStorageError` resolves its
operator-facing text from a registered message key, but ``str(exc)`` prefers
``args[0]``.  A raise site that passes an authored sentence positionally
*alongside* the key therefore stays green under a key-and-context assertion
while the English sentence keeps reaching tracebacks, structured logs and every
boundary that renders the exception directly -- in every locale.  The runtime
assertions here are deliberately *absence* assertions: they require ``str(exc)``
to be exactly the key, which is false the moment a positional argument returns.

The AST sweep is the second, independent proof.  It refuses message text
supplied either positionally or through ``message=``; the keyword form is the
shape a scan that only inspects ``node.args`` cannot see at all.

A third shape has no raise site to scan: prose, or a wrong key, baked into a
constructor default.  ``LedgerStorageError`` once defaulted
``translated_message`` to its own key as a literal, which
:class:`~cadrumo.domain.transactions.LedgerNoActiveBucketError` inherited
verbatim -- so the subclass rendered the parent's ``FAIL_FINANCIAL_LEDGER_STORAGE``
key instead of its own registered ``REFUSED_FINANCIAL_LEDGER_NO_ACTIVE_BUCKET``
key, and no raise-site scan could have detected it.  The default now resolves
through the registry, and that is pinned below.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.errors import get_registered_error_code
from .. import repository as _repository_module
from ..errors import LedgerNoActiveBucketError, LedgerStorageError
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..repository import _LEDGER_STORAGE_MESSAGE_KEY, transaction_index_object_key, transaction_object_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The error classes whose raise sites this module polices.  Every other
#: exception the module could name belongs to a different owner's contract.
_PINNED_ERROR_NAMES = ("LedgerStorageError", "LedgerNoActiveBucketError")

#: The key-derivation helpers that must still raise a pinned refusal.  Without
#: this anchor a rename would empty the AST sweep and let it pass vacuously.
_EXPECTED_RAISING_FUNCTIONS = frozenset(
    {
        "transaction_index_object_key",
        "transaction_object_key",
    },
)

assert _repository_module.__file__ is not None
_REPOSITORY_SOURCE = Path(_repository_module.__file__)


class TestTheStatedKeyIsTheRegisteredKey:
    """The module constant is the class's own registered key, not a restatement."""

    def test_module_constant_equals_the_registered_key(self) -> None:
        assert get_registered_error_code(LedgerStorageError).message_key == _LEDGER_STORAGE_MESSAGE_KEY

    def test_the_registered_code_is_the_ledger_storage_code(self) -> None:
        assert get_registered_error_code(LedgerStorageError).code == "FAIL_FINANCIAL_LEDGER_STORAGE"


class TestRefusalsCarryNoAuthoredSentence:
    """Every reachable key-derivation refusal renders as its key, never as English."""

    def test_blank_bucket_on_the_index_key_renders_the_key(self) -> None:
        with pytest.raises(LedgerStorageError) as excinfo:
            transaction_index_object_key("   ")

        assert str(excinfo.value) == "errors.fail.fail_financial_ledger_storage"
        assert excinfo.value.context == {
            "repository": "transaction_catalogue",
            "operation": "index_object_key",
            "blank_field": "bucket_id",
        }

    def test_blank_bucket_on_the_row_key_renders_the_key(self) -> None:
        with pytest.raises(LedgerStorageError) as excinfo:
            transaction_object_key("   ", "tx-1")

        assert str(excinfo.value) == "errors.fail.fail_financial_ledger_storage"
        assert excinfo.value.context == {
            "repository": "transaction_catalogue",
            "operation": "object_key",
            "blank_field": "bucket_id",
        }

    def test_blank_transaction_id_on_the_row_key_renders_the_key(self) -> None:
        with pytest.raises(LedgerStorageError) as excinfo:
            transaction_object_key("bucket-7", "   ")

        assert str(excinfo.value) == "errors.fail.fail_financial_ledger_storage"
        assert excinfo.value.context == {
            "repository": "transaction_catalogue",
            "operation": "object_key",
            "blank_field": "transaction_id",
        }

    def test_the_discriminating_fact_survives_as_a_machine_fact(self) -> None:
        """The two blank-field cases stay distinguishable without prose.

        Dropping the sentence must not collapse two different refusals into one
        indistinguishable outcome: the field that was blank is what a caller
        needs, and it now travels as a locale-neutral fact rather than as an
        English noun embedded in a sentence.
        """
        with pytest.raises(LedgerStorageError) as bucket_case:
            transaction_object_key("   ", "tx-1")
        with pytest.raises(LedgerStorageError) as transaction_case:
            transaction_object_key("bucket-7", "   ")

        assert bucket_case.value.context is not None
        assert transaction_case.value.context is not None
        assert bucket_case.value.context["blank_field"] != transaction_case.value.context["blank_field"]
        assert str(bucket_case.value) == str(transaction_case.value)


class TestTheConstructorDefaultResolvesPerClass:
    """A bare construction renders the constructed class's own registered key."""

    def test_bare_ledger_storage_error_renders_its_own_key(self) -> None:
        error = LedgerStorageError()

        assert str(error) == get_registered_error_code(LedgerStorageError).message_key
        assert error.translated_message == "errors.fail.fail_financial_ledger_storage"

    def test_bare_no_active_bucket_error_renders_its_own_key_not_the_parents(self) -> None:
        error = LedgerNoActiveBucketError()

        registered = get_registered_error_code(LedgerNoActiveBucketError).message_key
        assert error.translated_message == registered
        assert error.translated_message == "errors.refused.refused_financial_ledger_no_active_bucket"
        assert error.translated_message != get_registered_error_code(LedgerStorageError).message_key
        assert str(error) == registered

    def test_an_explicit_key_still_wins_over_the_registry_fallback(self) -> None:
        """The one live raise site supplies its own key; the fallback must not override it."""
        error = LedgerNoActiveBucketError(
            translated_message="application.workflow.errors.no_active_profile_bucket",
        )

        assert error.translated_message == "application.workflow.errors.no_active_profile_bucket"


def _authored_message_sites(path: Path) -> list[tuple[str, int]]:
    """Return every pinned construction in ``path`` that supplies message text.

    Both shapes count: a positional argument and a ``message=`` keyword.  The
    walk inspects constructions rather than only ``raise`` statements, so a
    refusal that is built and returned is caught alongside one that is raised.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in _PINNED_ERROR_NAMES:
            continue
        if node.args or any(keyword.arg == "message" for keyword in node.keywords):
            offenders.append((node.func.id, node.lineno))
    return offenders


def _pinned_construction_sites() -> tuple[tuple[str, ast.Call], ...]:
    """Return ``(enclosing_qualname, call)`` for each pinned construction."""
    tree = ast.parse(_REPOSITORY_SOURCE.read_text(encoding="utf-8"))
    found: list[tuple[str, ast.Call]] = []

    def walk(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                walk(child, (*scope, child.name))
                continue
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id in _PINNED_ERROR_NAMES
            ):
                found.append((".".join(scope), child))
            walk(child, scope)

    walk(tree, ())
    return tuple(found)


class TestEveryPinnedSiteIsStructurallyClean:
    """No pinned construction may reintroduce an authored sentence."""

    def test_the_expected_functions_still_construct_a_refusal(self) -> None:
        assert {qualname for qualname, _ in _pinned_construction_sites()} == _EXPECTED_RAISING_FUNCTIONS

    def test_no_pinned_site_supplies_message_text(self) -> None:
        assert _authored_message_sites(_REPOSITORY_SOURCE) == []

    def test_every_pinned_site_states_the_registered_key_constant(self) -> None:
        stated: dict[str, str] = {}
        for qualname, call in _pinned_construction_sites():
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            assert "translated_message" in keywords, qualname
            value = keywords["translated_message"]
            assert isinstance(value, ast.Name), qualname
            assert value.id == "_LEDGER_STORAGE_MESSAGE_KEY", qualname
            stated[qualname] = value.id

        assert set(stated) == _EXPECTED_RAISING_FUNCTIONS

    def test_no_pinned_site_carries_command_prose_in_its_facts(self) -> None:
        """The retired default recovery for this code was an executable command."""
        for qualname, call in _pinned_construction_sites():
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            context = keywords.get("context")
            assert isinstance(context, ast.Dict), qualname
            for value in context.values:
                assert isinstance(value, ast.Constant), qualname
                assert isinstance(value.value, str), qualname
                assert "aeat" not in value.value, qualname
                assert " --" not in value.value, qualname

    def test_the_scan_detects_both_shapes_it_guards_against(self, tmp_path: Path) -> None:
        """Prove the sweep bites on a positional sentence and on ``message=``."""
        positional = tmp_path / "positional.py"
        positional.write_text(
            "raise LedgerStorageError(\n"
            '    "bucket_id must not be blank",\n'
            "    translated_message=_LEDGER_STORAGE_MESSAGE_KEY,\n"
            ")\n",
            encoding="utf-8",
        )
        keyword = tmp_path / "keyword.py"
        keyword.write_text(
            "raise LedgerStorageError(\n"
            '    message="bucket_id must not be blank",\n'
            "    translated_message=_LEDGER_STORAGE_MESSAGE_KEY,\n"
            ")\n",
            encoding="utf-8",
        )
        returned = tmp_path / "returned.py"
        returned.write_text(
            'error = LedgerNoActiveBucketError("no active bucket")\n',
            encoding="utf-8",
        )
        clean = tmp_path / "clean.py"
        clean.write_text(
            "raise LedgerStorageError(\n    translated_message=_LEDGER_STORAGE_MESSAGE_KEY,\n)\n",
            encoding="utf-8",
        )

        assert _authored_message_sites(positional) == [("LedgerStorageError", 1)]
        assert _authored_message_sites(keyword) == [("LedgerStorageError", 1)]
        assert _authored_message_sites(returned) == [("LedgerNoActiveBucketError", 1)]
        assert _authored_message_sites(clean) == []


class TestTheNonNegativeAmountRefusalStillBites:
    """Migrating refusal messaging must not weaken the amount/direction contract.

    A ledger transaction stores a non-negative magnitude; flow direction is
    carried solely by ``direction``.  The refusal is asserted by type and by the
    rejected field, not by its text: that message is not migrated by this
    module, so pinning its English here would only entrench it.
    """

    @staticmethod
    def _raw(amount: Decimal) -> RawTransaction:
        return RawTransaction(
            provider_transaction_id="row-1",
            booked_date=date(2026, 4, 6),
            amount=amount,
            currency="EUR",
            description="statement row",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256="e" * 64,
                source_row_index=1,
                source_format=SourceFormat.MANUAL,
                ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
                provider_name="manual",
            ),
            raw_fields={"amount": str(amount)},
        )

    def test_a_negative_amount_is_refused(self) -> None:
        with pytest.raises(ValidationError) as excinfo:
            self._raw(Decimal("-1.00"))

        assert any(error["loc"] == ("amount",) for error in excinfo.value.errors())

    def test_a_non_negative_amount_is_accepted(self) -> None:
        assert self._raw(Decimal("0.00")).amount == Decimal("0.00")
        assert self._raw(Decimal("12.34")).amount == Decimal("12.34")
