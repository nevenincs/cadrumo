"""What a door's refusal of a settled result means, judged from the receipt that settled it.

A door refuses a result its receipt does not support. When that receipt
committed nothing, or its operation's definition declares no effect that
changes records, the refusal is an ordinary invalid frame. Any other receipt
may already have saved the change, so the door reports the outcome as unknown,
keeping the invalid frame as its reason; a retry is then not known to be safe.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import pytest

from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.core.operations import OperationEffect
from cadrumo.entrypoints.tui.operations.outcome import OperationOutcomeUnknownError
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

#: The effects a definition may declare without being able to change records.
_RECORDS_UNCHANGED = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})


def may_have_saved(effect: OperationEffect, contract: OperationPublicDefinitionContractV1) -> bool:
    """Whether a receipt with ``effect`` under ``contract`` may have saved a change."""
    return effect is not OperationEffect.NONE and not contract.permitted_effects <= _RECORDS_UNCHANGED


@contextmanager
def raises_unsupported_result(
    effect: OperationEffect, contract: OperationPublicDefinitionContractV1
) -> Generator[None]:
    """Expect the door to refuse a result its ``effect`` receipt under ``contract`` does not support."""
    if may_have_saved(effect, contract):
        with pytest.raises(OperationOutcomeUnknownError) as unknown:
            yield
        assert unknown.value.effect is effect
        assert isinstance(unknown.value.reason, RefusalError)
        assert unknown.value.reason.reason is RefusalCode.INVALID_FRAME
        return
    with pytest.raises(RefusalError) as refused:
        yield
    assert refused.value.reason is RefusalCode.INVALID_FRAME


__all__ = ["may_have_saved", "raises_unsupported_result"]
