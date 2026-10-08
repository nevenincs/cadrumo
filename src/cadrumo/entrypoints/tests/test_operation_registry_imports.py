"""Public runtime registration leaves document engines to their owning operations."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_production_registry_does_not_load_spreadsheet_or_pdf_engines() -> None:
    environment = os.environ.copy()
    environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
    probe = """
import sys
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
registry = build_production_operation_registry()
assert registry.public_contract_set.definitions
engines = {'openpyxl', 'numpy', 'pdfplumber', 'pdfminer', 'pikepdf', 'pypdfium2', 'pypdfium2_raw', 'PIL'}
assert not engines.intersection(sys.modules), sorted(engines.intersection(sys.modules))
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        probe,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=environment,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=None)
        assert process.returncode == 0, stderr.decode()
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
