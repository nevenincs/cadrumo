"""Canonical AEAT liquidación-clave identifier."""

from __future__ import annotations

from typing import Annotated

from pydantic import StringConstraints

__all__ = ["AeatClaveLiquidacion"]


AeatClaveLiquidacion = Annotated[str, StringConstraints(min_length=1, max_length=64)]
"""AEAT's identifier for the liquidación a debt row settles."""
