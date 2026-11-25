"""Typed JSON payload for the commands that enter one value of a declaration by hand.

This module uses :class:`OutputSchema`, the declared output contract.
"""

from __future__ import annotations

from typing import Literal

from ...core.identity.bucket import BucketId
from ...core.json_contract import OutputSchema


class WorkManualEntryResult(OutputSchema):
    """JSON envelope for the ``aeat app modelo work`` commands that enter one value by hand.

    They are ``set-value``, ``override``, ``attest-no-amount`` and ``attest-prior-value``.

    ``intent`` is the edit staged, as its stable token. The entry is addressed
    by ``casilla_id`` for a box value and by ``binding_id`` for an override, a
    statement of no amount or a stated figure of an earlier return.
    ``value_text`` is the value as the box shows it, in the output language;
    it is ``None`` for a statement of no amount.
    ``applied`` is ``False`` when the command only showed the change and its
    check because it was not confirmed; nothing was recorded then.
    """

    bucket_id: BucketId
    work_unit_id: str
    modelo: str
    filing_year: int
    intent: Literal["set_typed_value", "set_override_value", "attest_no_amount", "attest_prior_value"]
    casilla_id: str | None = None
    binding_id: str | None = None
    value_text: str | None = None
    applied: bool
    findings: list[str]
    receipt_id: str | None = None
    calculation_revision_id: str | None = None


__all__ = ["WorkManualEntryResult"]
