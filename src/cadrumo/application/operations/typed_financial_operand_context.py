"""Executor-only one-shot access to the registered typed financial batch."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from pydantic import BaseModel

from .financial_operand_contract import (
    OperationFinancialOperandRefusalCode,
    OperationFinancialOperandRefusedError,
    OperationTransientFinancialOperandDeclarationV1,
    OperationTransientFinancialOperandRequirementV1,
)
from .typed_financial_operand_submission import OperationTypedFinancialOperandBroker


class BoundTypedFinancialOperandAccess:
    """Bind the executor to its immutable invocation requirement and private declaration."""

    def __init__(
        self,
        *,
        broker: OperationTypedFinancialOperandBroker | None,
        declaration: OperationTransientFinancialOperandDeclarationV1 | None,
        requirement: OperationTransientFinancialOperandRequirementV1 | None,
    ) -> None:
        """Retain only application-owned custody coordinates, never the operand itself."""
        self._broker = broker
        self._declaration = declaration
        self._requirement = requirement

    @asynccontextmanager
    async def consume[OperandT: BaseModel](self, operand_type: type[OperandT]) -> AsyncIterator[OperandT]:
        """Take the complete exact model once and release the access scope's reference."""
        broker, declaration, requirement = self._broker, self._declaration, self._requirement
        if broker is None or declaration is None or requirement is None:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.UNKNOWN_REQUIREMENT)
        if operand_type is not declaration.operand_type:
            raise OperationFinancialOperandRefusedError(OperationFinancialOperandRefusalCode.WRONG_MODEL)
        async with broker.consume(requirement, declaration) as operand:
            try:
                yield cast(OperandT, operand)
            finally:
                del operand
