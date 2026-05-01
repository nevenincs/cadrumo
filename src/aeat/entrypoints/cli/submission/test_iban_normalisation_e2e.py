"""IBAN normalisation E2E guarantee.

The ``validate_iban_flag`` callback strips whitespace /
hyphens and upper-cases the IBAN before the flag value reaches
``build_303_headers``. that guarantee end-to-end:
Kent pasting the IBAN in any of its common human-typed forms
(spaces every 4 chars, hyphens, lowercase, mixed case) must
produce byte-identical export output.

Without this lock, a future refactor that moves validation /
normalisation elsewhere could silently break Kent's diff-against-
receipt workflow — two exports of the same draft-with-different-
paste-format would appear to differ at the DP303DID byte level.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]

_runner = CliRunner()


def _unwrap_result(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output)["result"])


_IBAN_CANONICAL = "ES9121000418450200051332"
_IBAN_VARIANTS = [
    _IBAN_CANONICAL,
    "ES91 2100 0418 4502 0005 1332",
    "ES91-2100-0418-4502-0005-1332",
    "es9121000418450200051332",
    "es91 2100 0418 4502 0005 1332",
    "  ES91 2100 0418 4502 0005 1332  ",
]


def _write_draft(tmp_path: Path) -> Path:
    payload = {
        "draft_id": "IBAN-NORM-001",
        "modelo": "303",
        "period": "2024Q1",
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {"01": "10000.00"},
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _export_with_iban(tmp_path: Path, iban: str, out_name: str) -> Path:
    draft = _write_draft(tmp_path)
    out = tmp_path / out_name
    result = _runner.invoke(
        app,
        [
            "export",
            str(draft),
            "--output-dir",
            str(out),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "D",
            "--iban",
            iban,
        ],
    )
    assert result.exit_code == 0, f"iban={iban!r} failed: {result.stdout}"
    return out / "X1234567L20241T.303"


class TestIbanNormalisationE2E:
    def test_every_variant_produces_identical_bytes(self, tmp_path: Path) -> None:
        """All human-typed IBAN variants must export byte-identical files.

        If this fails, the or end-to-end path
        let a non-canonical form reach ``serialise_envelope`` — future Kent
        diff-against-receipt workflows would show spurious differences.
        """
        canonical_file = _export_with_iban(tmp_path, _IBAN_CANONICAL, "canonical")
        canonical_bytes = canonical_file.read_bytes()

        for i, variant in enumerate(_IBAN_VARIANTS):
            if variant == _IBAN_CANONICAL:
                continue
            out = _export_with_iban(tmp_path, variant, f"variant-{i}")
            variant_bytes = out.read_bytes()
            assert variant_bytes == canonical_bytes, (
                f"IBAN variant {variant!r} produced different bytes than "
                f"canonical {_IBAN_CANONICAL!r}. Normalisation leaked — a "
                f"non-canonical form reached serialise_envelope."
            )

    def test_normalised_iban_appears_in_dp303did_without_spaces(self, tmp_path: Path) -> None:
        """The stamped IBAN in DP303DID_F006 must contain no whitespace,
        hyphens, or lowercase — the canonical upper-case no-separator form."""
        file = _export_with_iban(tmp_path, "es91 2100 0418 4502 0005 1332", "out")
        verify = _runner.invoke(app, ["verify", str(file), "--json"])
        assert verify.exit_code == 0, verify.stdout
        doc = _unwrap_result(verify.stdout)
        iban_value = None
        fields = cast(dict[str, Any], doc["fields"])
        for fid, val in fields.items():
            if "IBA" in fid:  # DP303DID_F006_DOMICILIACI_N_DEVOLUCI_N_IBA
                iban_value = val
                break
        assert iban_value is not None, "IBAN field not surfaced in verify output"
        assert _IBAN_CANONICAL in iban_value, (
            f"stamped IBAN {iban_value!r} did not contain the normalised canonical form {_IBAN_CANONICAL!r}"
        )
        # Make sure no spaces or hyphens leaked into the canonical portion.
        iban_portion = iban_value.strip()
        assert " " not in iban_portion and "-" not in iban_portion, (
            f"normalised IBAN leaked separators: {iban_portion!r}"
        )
