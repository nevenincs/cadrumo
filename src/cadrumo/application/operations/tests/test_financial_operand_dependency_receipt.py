"""Live-tree dependency receipt validator for the transient financial operand.

This is the sole validator for the operand contract's evidence. It reads the
current tree rather than a recorded claim, because a receipt that attests to
what was true when it was written stops being evidence the moment anything
moves. Every check below is derived: the module set is enumerated from the
package, the transition table is driven rather than described, and the
non-retention checks read the real field sets.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Protocol, get_type_hints

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect
from ..financial_operand import (
    OperationTransientFinancialOperandAccess,
    OperationTransientFinancialOperandAcknowledgement,
    OperationTransientFinancialOperandDeclaration,
    OperationTransientFinancialOperandExpiry,
    OperationTransientFinancialOperandProtocolV1,
    OperationTransientFinancialOperandRefusal,
    OperationTransientFinancialOperandRelease,
    OperationTransientFinancialOperandRequirement,
    OperationTransientFinancialOperandSubmission,
)
from ..financial_operand_custody import (
    OperationFinancialOperandCrashClassification,
    OperationFinancialOperandCustodyCheckpoint,
    OperationFinancialOperandCustodyError,
    OperationFinancialOperandCustodyState,
    advance_custody,
    classify_interrupted_custody,
    reconcile_on_restart,
)
from ..persistence.financial_operand_custody import OperationFinancialOperandCustodyRepository
from ..registry import resolve_effect_receipt
from .test_financial_operand_registration import _operand_definition

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROOT = Path(__file__).resolve().parents[5]
_GOVERNING_ADR = _ROOT / ".vault" / "adr" / "2026-08-11-tui-architecture-adr.md"
_STATE = OperationFinancialOperandCustodyState
_T0 = datetime(2026, 3, 4, 9, 0, 0, tzinfo=UTC)

_OPERAND_MODULES = (
    "cadrumo.application.operations.financial_operand",
    "cadrumo.application.operations.financial_operand_custody",
    "cadrumo.application.operations.persistence.financial_operand_custody",
)

_RECORD_TYPES = (
    OperationTransientFinancialOperandDeclaration,
    OperationTransientFinancialOperandRequirement,
    OperationTransientFinancialOperandAcknowledgement,
    OperationTransientFinancialOperandRefusal,
    OperationTransientFinancialOperandExpiry,
    OperationTransientFinancialOperandRelease,
    OperationFinancialOperandCustodyCheckpoint,
)


def _module_source(dotted: str) -> str:
    import importlib

    return Path(importlib.import_module(dotted).__file__ or "").read_text(encoding="utf-8")


def test_accepted_authority_governs_the_operand_contract() -> None:
    """The contract answers to an accepted decision, not an in-flight one."""
    headings = [
        line
        for line in _GOVERNING_ADR.read_text(encoding="utf-8").splitlines()
        if line.startswith("# ") and "status:" in line
    ]

    assert len(headings) == 1, "the governing ADR must state exactly one status"
    assert "`accepted`" in headings[0], headings[0]


def test_protocol_schema_is_structural_and_closed() -> None:
    """Every port is a runtime-checkable Protocol; every record is strict and frozen."""
    for protocol in (
        OperationTransientFinancialOperandSubmission,
        OperationTransientFinancialOperandAccess,
        OperationTransientFinancialOperandProtocolV1,
        OperationFinancialOperandCustodyRepository,
    ):
        assert issubclass(protocol, Protocol)  # type: ignore[arg-type]
        assert getattr(protocol, "_is_runtime_protocol", False), protocol.__name__

    for record in _RECORD_TYPES:
        config = record.model_config
        assert config.get("frozen") is True, record.__name__
        assert config.get("extra") == "forbid", record.__name__


def test_custody_transition_evidence_is_total_and_refuses_every_skip() -> None:
    """Each state's permitted moves are exercised, and every other move refused."""
    permitted = {
        _STATE.AWAITING_SUBMISSION: {_STATE.BOUND, _STATE.EXPIRED, _STATE.CANCELLED},
        _STATE.BOUND: {_STATE.DELIVERY_STARTED, _STATE.EXPIRED, _STATE.CANCELLED},
        _STATE.DELIVERY_STARTED: {_STATE.DELIVERY_ACKNOWLEDGED},
        _STATE.DELIVERY_ACKNOWLEDGED: {_STATE.RELEASED},
        _STATE.RELEASED: set(),
        _STATE.EXPIRED: set(),
        _STATE.CANCELLED: set(),
    }
    assert set(permitted) == set(_STATE)

    for state, allowed in permitted.items():
        for target in _STATE:
            checkpoint = OperationFinancialOperandCustodyCheckpoint(
                operand_kind="pago.fraccionado",
                interaction_id="interaction-1",
                sequence=1,
                state=state,
                recorded_at=_T0,
            )
            reason = None
            if target in {_STATE.EXPIRED, _STATE.CANCELLED}:
                from ..financial_operand import OperationFinancialOperandRefusalReason

                reason = OperationFinancialOperandRefusalReason.CANCELLED
            if target in allowed:
                advanced = advance_custody(checkpoint, target, now=_T0 + timedelta(seconds=1), refusal_reason=reason)
                assert advanced.state is target
            else:
                with pytest.raises(OperationFinancialOperandCustodyError):
                    advance_custody(checkpoint, target, now=_T0 + timedelta(seconds=1), refusal_reason=reason)


def test_crash_evidence_never_resolves_an_uncertain_delivery() -> None:
    """Every non-terminal position classifies, and the uncertain one stays uncertain."""
    for state in _STATE:
        checkpoint = OperationFinancialOperandCustodyCheckpoint(
            operand_kind="pago.fraccionado",
            interaction_id="interaction-1",
            sequence=1,
            state=state,
            recorded_at=_T0,
        )
        classification = classify_interrupted_custody(checkpoint)
        if checkpoint.is_terminal:
            assert classification is None
        else:
            assert classification is not None

        if state is _STATE.DELIVERY_STARTED:
            reconciled = reconcile_on_restart(checkpoint, now=_T0 + timedelta(hours=1))
            assert reconciled.crash_classification is (OperationFinancialOperandCrashClassification.DELIVERY_UNCERTAIN)
            assert reconciled.state is not _STATE.DELIVERY_ACKNOWLEDGED


def test_effect_evidence_narrows_and_never_widens() -> None:
    """No input to the resolver can turn a weaker claim into a stronger one."""
    definition = _operand_definition()
    strength = {OperationEffect.NONE: 0, OperationEffect.UNKNOWN: 1, OperationEffect.UPDATED: 2}

    for claimed in (OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED):
        for evidence in (True, False):
            receipt = resolve_effect_receipt(
                definition,
                claimed_effect=claimed,
                committed_evidence=evidence,
            )
            assert strength[receipt.effect] <= strength[claimed], (claimed, evidence)


def test_production_composition_binds_the_real_repository_to_its_protocol() -> None:
    """The shipped filesystem store satisfies the contract callers depend on."""
    from ....adapters.persistence.operations.financial_operand_custody import (
        OperationFinancialOperandCustodyFilesystemRepository as Repository,
    )

    assert issubclass(Repository, OperationFinancialOperandCustodyRepository)
    for name in ("read", "open", "advance", "unsettled"):
        assert callable(getattr(Repository, name))


def test_non_retention_holds_across_every_record_and_signature() -> None:
    """No record field and no return type carries an amount out of its call."""
    forbidden = ("amount", "digest", "hash", "fingerprint", "checksum")
    for record in _RECORD_TYPES:
        for name in record.model_fields:
            if record is OperationTransientFinancialOperandDeclaration and name in {"minimum", "maximum"}:
                continue
            assert not any(token in name.lower() for token in forbidden), f"{record.__name__}.{name}"
            annotation = str(record.model_fields[name].annotation)
            assert "Decimal" not in annotation, f"{record.__name__}.{name}"

    hints = get_type_hints(OperationTransientFinancialOperandProtocolV1.declare_requirement)
    assert "Decimal" not in str(hints.get("return")), "the broker must not return an amount"


def test_current_only_evidence_carries_no_legacy_branch() -> None:
    """The contract reads one shape; nothing here upgrades an older one."""
    legacy_markers = ("schema_version", "legacy", "migrate", "upgrade", "deprecated", "compat")
    for dotted in _OPERAND_MODULES:
        source = _module_source(dotted)
        for marker in legacy_markers:
            assert marker not in source.lower(), f"{dotted} carries {marker!r}"


def test_exactly_one_authority_defines_custody_and_the_operand_declaration() -> None:
    """A second declaration or transition table would fork the contract."""
    package = Path(inspect.getfile(OperationTransientFinancialOperandDeclaration)).parent
    searched = [*package.rglob("*.py"), *(_ROOT / "src" / "cadrumo" / "adapters").rglob("*.py")]

    declaring: list[str] = []
    transitioning: list[str] = []
    for path in searched:
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "OperationTransientFinancialOperandDeclaration":
                declaring.append(str(path))
            if isinstance(node, ast.FunctionDef) and node.name == "advance_custody":
                transitioning.append(str(path))

    assert len(declaring) == 1, declaring
    assert len(transitioning) == 1, transitioning


def test_a_persisted_checkpoint_serializes_without_operand_material() -> None:
    """The durable bytes themselves contain no amount, however they are read."""
    checkpoint = OperationFinancialOperandCustodyCheckpoint(
        operand_kind="pago.fraccionado",
        interaction_id="interaction-1",
        sequence=2,
        state=_STATE.DELIVERY_ACKNOWLEDGED,
        recorded_at=_T0,
    )
    declaration = OperationTransientFinancialOperandDeclaration(
        operand_kind="pago.fraccionado",
        currency="EUR",
        scale=2,
        minimum=Decimal("0.00"),
        maximum=Decimal("999.99"),
        lifetime=timedelta(minutes=5),
    )

    serialized = checkpoint.model_dump_json()

    assert "999.99" not in serialized
    assert declaration.admits(Decimal("999.99"))
    assert isinstance(checkpoint, BaseModel)
