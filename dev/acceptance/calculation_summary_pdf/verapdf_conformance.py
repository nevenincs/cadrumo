"""Validate calculation summaries with veraPDF: PDF/A-3a, PDF/A-3u and PDF/UA-1.

The product's own tests check the machine-checkable structure a summary must
have. This recipe asks an independent validator the same question, the way an
archive or an accessibility audit would: it renders synthetic summaries in every
supported language -- one short, one long enough to repeat its table headers
across pages -- and runs veraPDF's ``3a``, ``3u`` and ``ua1`` profiles over them.
It then proves the validator has teeth by running three negative controls, each
a genuine summary with exactly one conformance defect introduced, and requiring
the validator to refuse every one.

veraPDF is a development oracle, never a product dependency. The jar is fetched
from Maven Central's literal origin once, refused unless its bytes match the
digest pinned here, and cached under the checkout's development cache. Java must
be on PATH; without it the recipe exits with the missing-tool code rather than
reporting success.

Human-judgement conditions of the Matterhorn Protocol -- whether the reading order
makes sense, whether a header really describes its cells -- are outside what any
validator proves, and this recipe does not claim them.

Run with ``just test-calculation-summary-pdf``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

import pikepdf
from pikepdf import Name

from cadrumo.adapters.outbound.calculation_summary_pdf.tests.summary_report_support import (
    render_summary,
    synthetic_report,
    synthetic_report_rows,
)
from cadrumo.application.modelo.calculation_report import ModeloCalculationReportRow
from cadrumo.application.modelo.calculation_summary_pdf_ports import CSV_ATTACHMENT_NAME
from cadrumo.core.external_constants import OutputLanguage
from dev._paths import REPO_ROOT
from dev.cache_root import dev_cache_dir
from dev.exit_codes import FAILED, OK, TOOL_MISSING
from dev.packaging.command_execution import run_command

VERAPDF_VERSION: Final[str] = "1.28.2"
VERAPDF_JAR_PATH: Final[str] = (
    f"org/verapdf/apps/greenfield-apps/{VERAPDF_VERSION}/greenfield-apps-{VERAPDF_VERSION}.jar"
)
VERAPDF_JAR_SHA256: Final[str] = "687d4d8bcfec48c9f7e931cf78ed061f1eeccfba55d4cdc000ba9b4d8aa46ce6"
"""SHA-256 of the pinned jar, whose SHA-1 is the one Maven Central publishes beside it."""

POSITIVE_FLAVOURS: Final[tuple[str, ...]] = ("3a", "3u", "ua1")
_MAIN_CLASS: Final[str] = "org.verapdf.apps.GreenfieldCliWrapper"
_TIMEOUT_SECONDS: Final[float] = 900.0
_LONG_REPORT_ROW_COUNT: Final[int] = 140


@dataclass(frozen=True, slots=True)
class Verdict:
    """One validator verdict on one file under one profile."""

    file: str
    flavour: str
    compliant: bool
    failed_rules: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Expectation:
    """A file, the profile it is validated against, and whether it must pass."""

    path: Path
    flavour: str
    must_comply: bool


def jar_path() -> Path:
    """Return where the pinned jar is cached."""
    return dev_cache_dir("verapdf") / VERAPDF_VERSION / Path(VERAPDF_JAR_PATH).name


def require_pinned_jar(jar: Path) -> None:
    """Refuse a jar whose bytes are not the pinned release."""
    digest = hashlib.sha256(jar.read_bytes()).hexdigest()
    if digest != VERAPDF_JAR_SHA256:
        raise SystemExit(
            f"veraPDF {VERAPDF_VERSION} jar digest mismatch at {jar}\n"
            f"  expected {VERAPDF_JAR_SHA256}\n  got      {digest}\nRefusing to run an unverified validator.",
        )


def ensure_jar() -> Path:
    """Return the verified cached jar, fetching it from Maven Central when absent."""
    jar = jar_path()
    if not jar.is_file():
        jar.parent.mkdir(parents=True, exist_ok=True)
        staged = jar.with_suffix(".download")
        with urllib.request.urlopen(f"https://repo1.maven.org/maven2/{VERAPDF_JAR_PATH}", timeout=300) as response:
            staged.write_bytes(response.read())
        require_pinned_jar(staged)
        staged.replace(jar)
    require_pinned_jar(jar)
    return jar


def parse_verdicts(document: str) -> tuple[Verdict, ...]:
    """Read every job's verdict out of veraPDF's JSON report."""
    report = json.loads(document)["report"]
    verdicts: list[Verdict] = []
    for job in report["jobs"]:
        validation = job["validationResult"]
        results = validation if isinstance(validation, list) else [validation]
        for result in results:
            failed = tuple(
                f"{rule['clause']}-{rule['testNumber']} ({rule['failedChecks']}x)"
                for rule in result.get("details", {}).get("ruleSummaries", [])
            )
            verdicts.append(
                Verdict(
                    file=Path(job["itemDetails"]["name"]).name,
                    flavour=str(result.get("profileName", "")),
                    compliant=bool(result["compliant"]),
                    failed_rules=failed,
                ),
            )
    return tuple(verdicts)


def _long_rows() -> tuple[ModeloCalculationReportRow, ...]:
    """Return enough rows, across several sections, to repeat table headers over pages."""
    template = synthetic_report_rows()
    rows: list[ModeloCalculationReportRow] = []
    for index in range(_LONG_REPORT_ROW_COUNT):
        base = template[index % len(template)]
        rows.append(
            base.model_copy(
                update={
                    "casilla_id": f"L{index:03d}",
                    "number": f"{index + 1:03d}" if base.number != template[-1].number else base.number,
                    "section_path": (f"seccion_{index // 35}",),
                    "value": base.value + Decimal(index) if isinstance(base.value, Decimal) else base.value,
                },
            ),
        )
    return tuple(rows)


def _without_csv_relationship(pdf: pikepdf.Pdf) -> None:
    del pdf.attachments[CSV_ATTACHMENT_NAME].obj.AFRelationship


def _with_untagged_heading(pdf: pikepdf.Pdf) -> None:
    page = pdf.pages[0]
    instructions = list(pikepdf.parse_content_stream(page))
    opening = next(
        index
        for index, instruction in enumerate(instructions)
        if str(instruction.operator) == "BDC" and instruction.operands[0] == Name.H1
    )
    closing = next(index for index in range(opening, len(instructions)) if str(instructions[index].operator) == "EMC")
    del instructions[closing]
    del instructions[opening]
    page.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(instructions))


def _without_extension_schema(pdf: pikepdf.Pdf) -> None:
    packet = pdf.Root.Metadata.read_bytes()
    marker = packet.index(b"xmlns:pdfaExtension=")
    start = packet.rindex(b"<rdf:Description", 0, marker)
    end = packet.index(b"</rdf:Description>", start) + len(b"</rdf:Description>")
    pdf.Root.Metadata.write(packet[:start] + packet[end:])


NEGATIVE_CONTROLS: Final[tuple[tuple[str, str, Callable[[pikepdf.Pdf], None]], ...]] = (
    ("no-afrelationship", "3a", _without_csv_relationship),
    ("untagged-heading", "ua1", _with_untagged_heading),
    ("no-extension-schema", "3a", _without_extension_schema),
)
"""Each defect, the profile that must refuse it, and how it is introduced."""


def with_defect(payload: bytes, defect: Callable[[pikepdf.Pdf], None]) -> bytes:
    """Return ``payload`` with one conformance defect introduced."""
    with pikepdf.open(io.BytesIO(payload)) as pdf:
        defect(pdf)
        output = io.BytesIO()
        pdf.save(output)
    return output.getvalue()


def write_fixtures(directory: Path) -> tuple[Expectation, ...]:
    """Render every fixture and negative control into ``directory``; return what each must do."""
    directory.mkdir(parents=True, exist_ok=True)
    expectations: list[Expectation] = []
    for language in OutputLanguage:
        for shape, rows in (("short", None), ("long", _long_rows())):
            path = directory / f"summary-{language.value}-{shape}.pdf"
            path.write_bytes(render_summary(synthetic_report(language, rows=rows)).payload)
            expectations.extend(Expectation(path, flavour, must_comply=True) for flavour in POSITIVE_FLAVOURS)
    genuine = render_summary(synthetic_report(OutputLanguage.ES)).payload
    for name, flavour, defect in NEGATIVE_CONTROLS:
        path = directory / f"negative-{name}.pdf"
        path.write_bytes(with_defect(genuine, defect))
        expectations.append(Expectation(path, flavour, must_comply=False))
    return tuple(expectations)


def validate(java: str, jar: Path, flavour: str, files: Iterable[Path]) -> tuple[Verdict, ...]:
    """Run one veraPDF profile over ``files``."""
    arguments = [str(path) for path in files]
    result = run_command(
        [java, "-cp", str(jar), _MAIN_CLASS, "--flavour", flavour, "--format", "json", *arguments],
        cwd=REPO_ROOT,
        timeout_seconds=_TIMEOUT_SECONDS,
        errors="replace",
    )
    if not result.stdout.strip():
        raise SystemExit(f"veraPDF produced no report for {flavour}: {result.stderr[-800:]}")
    return parse_verdicts(result.stdout)


def unmet(expectations: Iterable[Expectation], verdicts: dict[tuple[str, str], Verdict]) -> list[str]:
    """Return one line per expectation the validator's verdicts do not meet."""
    problems: list[str] = []
    for expectation in expectations:
        verdict = verdicts.get((expectation.path.name, expectation.flavour))
        if verdict is None:
            problems.append(f"{expectation.path.name} [{expectation.flavour}]: no verdict")
        elif verdict.compliant is not expectation.must_comply:
            wanted = "compliant" if expectation.must_comply else "refused"
            problems.append(
                f"{expectation.path.name} [{expectation.flavour}]: expected {wanted}; "
                f"failed rules: {', '.join(verdict.failed_rules) or 'none'}",
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Render, validate and report; exit non-zero on any unmet expectation."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=dev_cache_dir("verapdf") / "calculation-summary-fixtures",
        help="Directory the fixtures are written to and validated in.",
    )
    options = parser.parse_args(argv)
    java = shutil.which("java")
    if java is None:
        print("java is not on PATH; veraPDF cannot run", file=sys.stderr)
        return TOOL_MISSING
    jar = ensure_jar()
    expectations = write_fixtures(options.output_dir)
    verdicts: dict[tuple[str, str], Verdict] = {}
    for flavour in sorted({expectation.flavour for expectation in expectations}):
        files = [expectation.path for expectation in expectations if expectation.flavour == flavour]
        for verdict in validate(java, jar, flavour, files):
            verdicts[(verdict.file, flavour)] = verdict
    for expectation in expectations:
        verdict = verdicts.get((expectation.path.name, expectation.flavour))
        state = "missing" if verdict is None else ("compliant" if verdict.compliant else "refused")
        print(f"{expectation.flavour:4} {state:9} {expectation.path.name}")
    problems = unmet(expectations, verdicts)
    for problem in problems:
        print(f"UNMET {problem}", file=sys.stderr)
    print(f"veraPDF {VERAPDF_VERSION}: {len(expectations) - len(problems)} of {len(expectations)} expectations met")
    return FAILED if problems else OK


if __name__ == "__main__":
    raise SystemExit(main())
