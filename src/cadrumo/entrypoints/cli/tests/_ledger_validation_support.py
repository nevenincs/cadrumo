"""Shared real-CLI harness for ledger validation-path tests."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....core.config import override_settings
from ....domain.user_profile.values import UserProfileFact
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session, set_active_test_profile_facts
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ._cli_json_support import _json_object
from ._ledger_llm_support import _import_one_transaction

_PROFILE_ID = "9e0f3a2b-5d1c-4a77-9b2d-27ed6d6c7f10"
_PROFILE_LABEL = "tester"


def _invoke(args: Sequence[str], *, env: Mapping[str, str] | None = None) -> Result:
    return invoke_cached_cli(args, env=env)


@contextmanager
def open_bucket_session(tmp_path: Path) -> Iterator[None]:
    """Open the shared real-CLI ledger session against an isolated storage root.

    The registered profile is minimal PLUS a declared IVA block, and the second
    half is load-bearing rather than convenience. Every ledger path that
    resolves an IVA treatment -- add, allocate, split, evidence confirm --
    consults the deadlines profile, which refuses outright for a taxpayer whose
    IVA axes were never declared. That refusal is correct in production: an
    undeclared Modelo 303 composition is not a general one. In this harness it
    arrives before any behaviour under test, so a suite asserting a
    non-negative-amount refusal instead reads an incomplete-profile refusal and
    fails on a message it never mentions.

    Declared HERE rather than per suite because the cause is the harness, not
    any one file: when the IVA block became mandatory, roughly thirty ledger
    CLI modules went red on this single reason at once, and a per-suite
    declaration would have been thirty copies of one fact.
    """
    dispose_engine()
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_PROFILE_ID),
    ):
        register_minimal_profile(profile_id=_PROFILE_ID, display_name=_PROFILE_LABEL)
        _declare_general_regime_iva_profile()
        try:
            yield
        finally:
            dispose_engine()


def import_validation_transaction(tmp_path: Path) -> str:
    """Import this suite's one CSV row through the real CLI, returning its id.

    The import itself is not this module's to implement: writing a statement,
    driving ``ledger import`` and reading the id back is one behaviour with one
    home, and a second copy of it drifted here under a name claiming it also
    created a profile, which it never did. Only the scenario data is local.
    """
    return _import_one_transaction(
        tmp_path,
        payee="Client SL",
        reference="Invoice 1",
        amount="-50.00",
        marker="n26-001",
    )


def _set_profile_axis(key: str, value: str) -> None:
    set_active_test_profile_facts((UserProfileFact(path=key, value=value),))


#: The IVA axes the deadlines profile demands before it will answer for a
#: taxpayer, with the values of an ordinary general-regime filer.
#:
#: The composition is the one axis with no defensible default -- an undeclared
#: composition is not a general one -- and the four booleans are opt-in special
#: regimes this taxpayer is not in. They are declared together because the
#: profile refuses on the whole set: satisfying one surfaces the next, which
#: reads as a sequence of unrelated failures rather than one incomplete
#: profile.
_GENERAL_REGIME_IVA_AXES: tuple[tuple[str, str | bool], ...] = (
    ("iva.m303_regime_composition", "general"),
    ("iva.redeme_enrolled", False),
    ("iva.cash_accounting_regime_enrolled", False),
    ("iva.voluntary_sii_enrolled", False),
    ("iva.hydrocarbon_deposit_advance_payment_deduction_entitled", False),
)

#: The filer's own fiscal-address postcode, which is a TERRITORIAL fact rather
#: than an IVA-regime one and so is named apart from the block above.
#:
#: It separates the peninsula from Canarias and from Ceuta y Melilla, is never
#: read off an invoice, and became mandatory on every confirm path -- so a
#: harness omitting it reads an incomplete-profile refusal in place of whatever
#: the suite meant to assert, for the same reason and at the same scale the IVA
#: block did. A peninsular code, because these suites are domestic.
#:
#: The path comes from the production constant rather than a literal, so a
#: rename reaches this harness through the type checker instead of through a
#: red suite nobody can attribute.
_FILER_FISCAL_ADDRESS_AXES: tuple[tuple[str, str | bool], ...] = ((FILER_POSTCODE_FACT_PATH, "28013"),)


def _declare_general_regime_iva_profile() -> None:
    """Complete the minimal profile for a domestic general-regime filer.

    ``register_minimal_profile`` deliberately registers the smallest profile
    that can hold a bucket, which includes neither the IVA axes nor the fiscal
    address. Any CLI path that resolves an IVA treatment -- notably
    ``evidence confirm`` -- then refuses with an incomplete-profile error
    before reaching the behaviour under test, so a suite exercising that path
    must declare them.

    Both blocks are declared here, and the postcode is not an afterthought: the
    filer's own territory decides the treatment of every operation, so a
    confirm path refuses without it exactly as it refuses without a declared
    Modelo 303 composition. Two mandatory blocks, one incomplete profile.

    Written in ONE update rather than one per axis, so the profile is never
    observed half-declared by anything reading between writes.
    """
    set_active_test_profile_facts(
        UserProfileFact(path=path, value=value)
        for path, value in (*_GENERAL_REGIME_IVA_AXES, *_FILER_FISCAL_ADDRESS_AXES)
    )


def _add_eligible_mixed_expense() -> str:
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-02-10",
            "--amount",
            "60.50",
            "--direction",
            "OUTGOING",
            "--description",
            "phone bill",
            "--taxable-base",
            "50.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "10.50",
        ],
        env={"CADRUMO_OUTPUT_LANGUAGE": "en"},
    )
    assert result.exit_code == 0, result.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_json(result.output)
    transaction_id = _json_object(payload["result"])["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _flatten_box(text: str) -> str:
    return " ".join(text.replace("│", " ").split())


def _assert_pipeline_managed_state_refusal(flat: str, output: str) -> None:
    assert "set automatically" in flat, output
    assert "cannot be assigned by hand" in flat, output
    assert "BUSINESS, PERSONAL, MIXED" in flat, output
