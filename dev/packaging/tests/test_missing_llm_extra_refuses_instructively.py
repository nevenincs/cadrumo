"""Installed-core proof for every guarded local-inference surface.

The developer environment includes the ``llm`` dependencies, so absence cannot
be established there.  This module instead builds the committed product cohort
and runs the production package from a clean core-only virtual environment.
The optional probe is consequently absent because its distribution was never
installed, rather than because import resolution was intercepted.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from cadrumo import llm
from cadrumo.core import LLM_EXTRA
from cadrumo.core.directory_scan import scan_directory

from .._smoke_common import (
    build_companion_wheels,
    build_wheel,
    create_pip_venv,
    head_extract,
    install_targets_with_pip,
    isolated_product_env,
    venv_python_path,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter, pytest.mark.serial]

# dev/packaging/tests -> parents[3] is the repository root. Stated because
# the depth silently retargets on a move: these files carried the depth they
# had under src/, which resolved ABOVE the repository and built a wheel from
# a directory with no pyproject.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if not (_REPO_ROOT / "pyproject.toml").is_file():  # pragma: no cover - configuration guard
    _message = f"packaging gate lost the repository root: {_REPO_ROOT}"
    raise RuntimeError(_message)
_MARKER = "SURFACE_OUTCOMES:"

# Every operator-reachable guarded entry point is driven with core-only typed
# inputs. The source-derived coverage check below fails if a new production
# guard is not represented here.
_GUARDED_SURFACES: tuple[tuple[str, str], ...] = (
    ("rasterise_pdf_pages_to_base64_png", "rasterise_pdf_pages_to_base64_png(b'%PDF-1.4\\n')"),
    ("transcribe_document_images", "transcribe_document_images(_PAGES, source_content_sha256='0' * 64)"),
    ("extract_invoice_fields_from_text", "extract_invoice_fields_from_text(_TRANSCRIPTION)"),
    ("LocalVisionDocumentTranscriber", "LocalVisionDocumentTranscriber()"),
    ("TextInvoiceFieldExtractor", "TextInvoiceFieldExtractor()"),
    ("LocalTextLLMClassifier", "LocalTextLLMClassifier(spec=None)"),
    ("LocalVisionLLMClassifier", "LocalVisionLLMClassifier(spec=None)"),
    ("SemanticColumnRoleMapper", "SemanticColumnRoleMapper()"),
    ("SupplyNatureProposer", "SupplyNatureProposer()"),
)


@pytest.fixture(scope="module")
def installed_core_environment(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build one complete core-only cohort where the LLM extra is genuinely absent."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required to build the installed core cohort"

    work_dir = tmp_path_factory.mktemp("missing-llm-extra-boundary")
    build_root = head_extract(_REPO_ROOT, work_dir)
    root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
    data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
    venv = create_pip_venv(work_dir, f"{sys.version_info.major}.{sys.version_info.minor}")
    install_targets_with_pip(
        work_dir,
        (str(root_wheel.resolve()), *(str(wheel.resolve()) for wheel in data_wheels)),
        venv,
    )
    return work_dir, venv_python_path(venv)


def _guarded_definition_names() -> frozenset[str]:
    """Derive exported definitions that call the real LLM extra guard."""
    # Derived from the imported package, never from this file's own depth. The
    # depth was right while this test lived inside the llm package; after the
    # move to dev/packaging/tests the same arithmetic scanned the packaging
    # tooling, where no guard exists, so the derivation was empty and the
    # inventory below compared nothing against nothing.
    if llm.__file__ is None:  # pragma: no cover - namespace package guard
        message = "the llm package has no file location to scan"
        raise RuntimeError(message)
    package = Path(llm.__file__).resolve().parent
    exported = frozenset(llm.__all__)
    derived: set[str] = set()
    for path in scan_directory(package, pattern="*.py", recursive=True):
        if "tests" in path.relative_to(package).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if any(
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "require_optional_extra"
                and any(isinstance(arg, ast.Name) and arg.id == "LLM_EXTRA" for arg in child.args)
                for child in ast.walk(node)
            ):
                derived.add(node.name)
    return frozenset(derived) & exported


def _isolated_environment(work_dir: Path) -> dict[str, str]:
    """Keep the subprocess outside the checkout and host product state."""
    environment = isolated_product_env(work_dir / "product-state")
    environment.pop("PYTHONPATH", None)
    return environment


def _drive_surfaces(work_dir: Path, python: Path) -> dict[str, object]:
    """Drive actual production entry points inside the core-only installed cohort."""
    surfaces = json.dumps([{"name": name, "call": call} for name, call in _GUARDED_SURFACES])
    code = textwrap.dedent(
        f"""
        import json
        from pathlib import Path

        import cadrumo
        from cadrumo.application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
        from cadrumo.core import (
            FieldOrigin,
            ImageMediaType,
            LLM_EXTRA,
            LOCAL_TRANSPORT_LABEL,
            MissingOptionalExtraError,
            optional_extra_available,
        )
        from cadrumo.llm import (
            LocalTextLLMClassifier,
            LocalVisionDocumentTranscriber,
            LocalVisionLLMClassifier,
            MultimodalImageInput,
            SemanticColumnRoleMapper,
            TextInvoiceFieldExtractor,
            extract_invoice_fields_from_text,
            rasterise_pdf_pages_to_base64_png,
            transcribe_document_images,
        )

        _PAGES = (MultimodalImageInput.from_base64("aGk=", ImageMediaType.PNG),)
        _TRANSCRIPTION = DocumentTranscription(
            text="factura",
            page_count=1,
            source_content_sha256="0" * 64,
            transcriber=TranscriberIdentity(
                origin=FieldOrigin.TEXT_LAYER,
                name="boundary",
                transport=LOCAL_TRANSPORT_LABEL,
                revision="installed-core",
            ),
        )

        outcomes = []
        for surface in json.loads({surfaces!r}):
            try:
                eval(surface["call"])
            except MissingOptionalExtraError as exc:
                outcomes.append(
                    {{
                        "name": surface["name"],
                        "outcome": "refused",
                        "extra": exc.extra.model_dump(mode="json"),
                    }}
                )
            except ModuleNotFoundError as exc:
                outcomes.append({{"name": surface["name"], "outcome": "module-not-found", "type": type(exc).__name__}})
            except BaseException as exc:
                outcomes.append({{"name": surface["name"], "outcome": "other", "type": type(exc).__name__}})
            else:
                outcomes.append({{"name": surface["name"], "outcome": "succeeded"}})

        print(
            {_MARKER!r}
            + json.dumps(
                {{
                    "cadrumo_file": str(Path(cadrumo.__file__).resolve()),
                    "extra_available": optional_extra_available(LLM_EXTRA),
                    "outcomes": outcomes,
                }},
                sort_keys=True,
            )
        )
        """,
    )
    completed = subprocess.run(  # noqa: S603 - resolved executable, fixed argv, no shell
        [str(python), "-c", code],
        cwd=work_dir,
        env=_isolated_environment(work_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    line = next((row for row in completed.stdout.splitlines() if row.startswith(_MARKER)), None)
    assert line is not None, completed.stdout
    report = json.loads(line.removeprefix(_MARKER))
    assert isinstance(report, dict)
    typed_report: dict[str, object] = {}
    for key, value in report.items():
        assert isinstance(key, str), "JSON object keys must be strings"
        typed_report[key] = value
    return typed_report


def test_the_driven_inventory_covers_every_guarded_entry_point() -> None:
    """A newly guarded production definition cannot silently escape the real lane."""
    derived = _guarded_definition_names()
    assert derived, "no production require_optional_extra(LLM_EXTRA) guard was found"
    driven = {name for name, _call in _GUARDED_SURFACES}
    assert not derived - driven, (
        f"guarded production entry points not driven by this lane: {sorted(derived - driven)!r}"
    )


@pytest.mark.timeout(900)
def test_every_guarded_surface_preserves_the_registered_extra_facts(
    installed_core_environment: tuple[Path, Path],
) -> None:
    """Every guarded surface refuses in a genuine no-extra product install."""
    work_dir, python = installed_core_environment
    report = _drive_surfaces(work_dir, python)

    assert Path(str(report["cadrumo_file"])).is_relative_to(python.parents[1])
    assert report["extra_available"] is False
    outcomes = report["outcomes"]
    assert isinstance(outcomes, list) and outcomes
    expected_names = {name for name, _call in _GUARDED_SURFACES}
    observed_names = {entry["name"] for entry in outcomes if isinstance(entry, dict)}
    assert observed_names == expected_names
    expected_extra = LLM_EXTRA.model_dump(mode="json")
    wrong = [
        entry
        for entry in outcomes
        if not isinstance(entry, dict) or entry.get("outcome") != "refused" or entry.get("extra") != expected_extra
    ]
    assert not wrong, f"installed core LLM surfaces did not preserve the registered typed extra: {wrong!r}"
