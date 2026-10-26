"""The veraPDF oracle refuses what it must, without needing Java to prove it.

The validator run itself needs Java and the pinned jar; these cases prove the
parts of the recipe that decide what its run means: an unpinned jar is refused,
a verdict the fixtures did not expect is reported, and each negative control
really carries the one defect it is named for.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pikepdf
import pytest
from pikepdf import Name

from cadrumo.adapters.outbound.calculation_summary_pdf.tests.summary_report_support import (
    render_summary,
    synthetic_report,
)
from cadrumo.application.modelo.calculation_summary_pdf_ports import CSV_ATTACHMENT_NAME

from ..verapdf_conformance import (
    NEGATIVE_CONTROLS,
    Expectation,
    parse_verdicts,
    require_pinned_jar,
    unmet,
    with_defect,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_jar_whose_bytes_are_not_the_pinned_release_is_refused(tmp_path: Path) -> None:
    impostor = tmp_path / "greenfield-apps.jar"
    impostor.write_bytes(b"PK\x03\x04 not the release")

    with pytest.raises(SystemExit, match="digest mismatch"):
        require_pinned_jar(impostor)


def test_a_verdict_contrary_to_the_expectation_is_reported(tmp_path: Path) -> None:
    report = {
        "report": {
            "jobs": [
                {
                    "itemDetails": {"name": str(tmp_path / "good.pdf")},
                    "validationResult": [{"compliant": True, "profileName": "PDF/A-3A", "details": {}}],
                },
                {
                    "itemDetails": {"name": str(tmp_path / "negative.pdf")},
                    "validationResult": {
                        "compliant": True,
                        "profileName": "PDF/A-3A",
                        "details": {"ruleSummaries": []},
                    },
                },
            ],
        },
    }
    verdicts = {(verdict.file, "3a"): verdict for verdict in parse_verdicts(json.dumps(report))}

    problems = unmet(
        (
            Expectation(tmp_path / "good.pdf", "3a", must_comply=True),
            Expectation(tmp_path / "negative.pdf", "3a", must_comply=False),
            Expectation(tmp_path / "unvalidated.pdf", "3a", must_comply=True),
        ),
        verdicts,
    )

    assert problems == [
        "negative.pdf [3a]: expected refused; failed rules: none",
        "unvalidated.pdf [3a]: no verdict",
    ]


def test_each_negative_control_carries_exactly_its_named_defect() -> None:
    genuine = render_summary(synthetic_report()).payload
    defects = {name: with_defect(genuine, defect) for name, _flavour, defect in NEGATIVE_CONTROLS}

    with pikepdf.open(io.BytesIO(defects["no-afrelationship"])) as pdf:
        assert "/AFRelationship" not in pdf.attachments[CSV_ATTACHMENT_NAME].obj
    with pikepdf.open(io.BytesIO(defects["untagged-heading"])) as pdf:
        operands = [
            instruction.operands[0]
            for instruction in pikepdf.parse_content_stream(pdf.pages[0])
            if str(instruction.operator) == "BDC"
        ]
        assert Name.H1 not in operands
    with pikepdf.open(io.BytesIO(defects["no-extension-schema"])) as pdf:
        assert b"pdfaExtension" not in pdf.Root.Metadata.read_bytes()
    with pikepdf.open(io.BytesIO(genuine)) as pdf:
        assert "/AFRelationship" in pdf.attachments[CSV_ATTACHMENT_NAME].obj
        assert b"pdfaExtension" in pdf.Root.Metadata.read_bytes()
