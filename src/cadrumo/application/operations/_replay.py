"""Generic exclusive cursor accepted by public operation observation requests."""

from typing import Annotated

from pydantic import Field

OperationEventCursor = Annotated[int, Field(ge=0)]

__all__ = ["OperationEventCursor"]
