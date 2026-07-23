"""``config profile censo file`` refusal contract while extraction is unpinned."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke_with_artefact(tmp_path: Path, payload: bytes):
    artefact = tmp_path / "certificado.pdf"
    artefact.write_bytes(payload)
    return invoke_cached_cli(["--format", "json", "config", "profile", "censo", "file", "--file", str(artefact)])


def _stderr_document(result) -> dict:
    """Extract the JSON error document from stderr (line-scanned: logging may interleave)."""
    stderr = result.stderr if result.stderr_bytes is not None else ""
    for line in stderr.splitlines():
        candidate = line.strip()
        if candidate.startswith("{"):
            parsed = json.loads(candidate)
            assert isinstance(parsed, dict)
            return parsed
    raise AssertionError(f"no JSON document on stderr: {stderr[:400]!r}")


def test_non_pdf_artefact_refuses_with_the_registered_parse_code(tmp_path: Path) -> None:
    result = _invoke_with_artefact(tmp_path, b"not a certificate")
    assert result.exit_code != 0
    document = _stderr_document(result)
    assert document["error"]["code"] == "FAIL_CERTIFICADO_CENSAL_PARSE"
    assert "profile edit" in (document["error"].get("suggestion") or "")


def test_pdf_artefact_refuses_while_extraction_is_unpinned(tmp_path: Path) -> None:
    result = _invoke_with_artefact(tmp_path, b"%PDF-1.7 specimen-free")
    assert result.exit_code != 0
    document = _stderr_document(result)
    assert document["error"]["code"] == "FAIL_CERTIFICADO_CENSAL_PARSE"


def test_missing_artefact_is_refused_at_the_cli_boundary(tmp_path: Path) -> None:
    result = invoke_cached_cli(
        ["--format", "json", "config", "profile", "censo", "file", "--file", str(tmp_path / "absent.pdf")],
    )
    assert result.exit_code != 0
