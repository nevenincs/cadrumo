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
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.optional_extras import LLM_EXTRA
from .._smoke_common import build_companion_wheels, build_wheel, create_pip_venv, head_extract, install_targets_with_pip, isolated_product_env, venv_python_path
pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter, pytest.mark.serial]
_REPO_ROOT = Path(__file__).resolve().parents[3]

@pytest.fixture(autouse=True)
def _repository_root_resolved() -> None:
    """Fail this module's tests if the depth arithmetic retargeted.

    Checked per test rather than at import. Collection must stay side-effect
    free, and a guard that raises during collection reports a broken module
    rather than a named gate that lost its root, which is harder to act on.
    """
    assert (_REPO_ROOT / 'pyproject.toml').is_file(), f'packaging gate lost the repository root: {_REPO_ROOT}'
_MARKER = 'SURFACE_OUTCOMES:'
_GUARDED_SURFACES: tuple[tuple[str, str], ...] = (('rasterise_pdf_pages_to_base64_png', "rasterise_pdf_pages_to_base64_png(b'%PDF-1.4\\n')"), ('transcribe_document_images', "transcribe_document_images(_PAGES, source_content_sha256='0' * 64)"), ('extract_invoice_fields_from_text', 'extract_invoice_fields_from_text(_TRANSCRIPTION)'), ('LocalVisionDocumentTranscriber', 'LocalVisionDocumentTranscriber()'), ('TextInvoiceFieldExtractor', 'TextInvoiceFieldExtractor()'), ('LocalTextLLMClassifier', 'LocalTextLLMClassifier(spec=None)'), ('LocalVisionLLMClassifier', 'LocalVisionLLMClassifier(spec=None)'), ('SemanticColumnRoleMapper', 'SemanticColumnRoleMapper()'), ('SupplyNatureProposer', 'SupplyNatureProposer()'))
_DEFINING_MODULES: dict[str, str] = {'rasterise_pdf_pages_to_base64_png': 'cadrumo.llm.providers.local', 'transcribe_document_images': 'cadrumo.llm.evidence_draft_vision', 'extract_invoice_fields_from_text': 'cadrumo.llm.evidence_draft_text', 'LocalVisionDocumentTranscriber': 'cadrumo.llm.evidence_draft_vision', 'TextInvoiceFieldExtractor': 'cadrumo.llm.evidence_draft_text', 'LocalTextLLMClassifier': 'cadrumo.llm.text_classifier', 'LocalVisionLLMClassifier': 'cadrumo.llm.vision_classifier', 'SemanticColumnRoleMapper': 'cadrumo.llm.column_role_mapping', 'SupplyNatureProposer': 'cadrumo.llm.supply_nature_proposal', 'MultimodalImageInput': 'cadrumo.llm.models'}

@pytest.fixture(scope='module')
def installed_core_environment(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build one complete core-only cohort where the LLM extra is genuinely absent."""
    uv = shutil.which('uv')
    assert uv is not None, 'uv is required to build the installed core cohort'
    work_dir = tmp_path_factory.mktemp('missing-llm-extra-boundary')
    build_root = head_extract(_REPO_ROOT, work_dir)
    root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
    data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
    venv = create_pip_venv(work_dir, f'{sys.version_info.major}.{sys.version_info.minor}')
    install_targets_with_pip(work_dir, (str(root_wheel.resolve()), *(str(wheel.resolve()) for wheel in data_wheels)), venv)
    return (work_dir, venv_python_path(venv))

def _guarded_definition_names() -> frozenset[str]:
    """Derive exported definitions that call the real LLM extra guard."""
    if llm.__file__ is None:
        message = 'the llm package has no file location to scan'
        raise RuntimeError(message)
    package = Path(llm.__file__).resolve().parent
    derived: set[str] = set()
    for path in scan_directory(package, pattern='*.py', recursive=True):
        if 'tests' in path.relative_to(package).parts:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            if any((isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and (child.func.id == 'require_optional_extra') and any((isinstance(arg, ast.Name) and arg.id == 'LLM_EXTRA' for arg in child.args)) for child in ast.walk(node))):
                derived.add(node.name)
    return frozenset(derived)

def _isolated_environment(work_dir: Path) -> dict[str, str]:
    """Keep the subprocess outside the checkout and host product state."""
    environment = isolated_product_env(work_dir / 'product-state')
    _dp_pop('dev/packaging/tests/test_missing_llm_extra_refuses_instructively.py:147:pop', environment, 'PYTHONPATH', None)
    return environment

def _drive_surfaces(work_dir: Path, python: Path) -> dict[str, object]:
    """Drive actual production entry points inside the core-only installed cohort."""
    surfaces = json.dumps([{'name': name, 'call': call} for name, call in _GUARDED_SURFACES])
    by_module: dict[str, set[str]] = {}
    for surface in sorted({name for name, _call in _GUARDED_SURFACES} | {'MultimodalImageInput'}):
        by_module.setdefault(_DEFINING_MODULES[surface], set()).add(surface)
    llm_imports = chr(10).join((f"        from {module} import {', '.join(sorted(names))}" for module, names in sorted(by_module.items())))
    code = textwrap.dedent(f'\n        import json\n        from pathlib import Path\n\n        import cadrumo\n        from cadrumo.application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity\n        from cadrumo.core.field_origin import FieldOrigin\n        from cadrumo.core.image_media_type import ImageMediaType\n        from cadrumo.core.optional_extras import (\n            LLM_EXTRA,\n            MissingOptionalExtraError,\n            optional_extra_available,\n        )\n        from cadrumo.core.provenance_stamp import LOCAL_TRANSPORT_LABEL\n{llm_imports}\n\n        _PAGES = (MultimodalImageInput.from_base64("aGk=", ImageMediaType.PNG),)\n        _TRANSCRIPTION = DocumentTranscription(\n            text="factura",\n            page_count=1,\n            source_content_sha256="0" * 64,\n            transcriber=TranscriberIdentity(\n                origin=FieldOrigin.TEXT_LAYER,\n                name="boundary",\n                transport=LOCAL_TRANSPORT_LABEL,\n                revision="installed-core",\n            ),\n        )\n\n        outcomes = []\n        for surface in json.loads({surfaces!r}):\n            try:\n                eval(surface["call"])\n            except MissingOptionalExtraError as exc:\n                outcomes.append(\n                    {{\n                        "name": surface["name"],\n                        "outcome": "refused",\n                        "extra": exc.extra.model_dump(mode="json"),\n                    }}\n                )\n            except ModuleNotFoundError as exc:\n                outcomes.append({{"name": surface["name"], "outcome": "module-not-found", "type": type(exc).__name__}})\n            except BaseException as exc:\n                outcomes.append({{"name": surface["name"], "outcome": "other", "type": type(exc).__name__}})\n            else:\n                outcomes.append({{"name": surface["name"], "outcome": "succeeded"}})\n\n        print(\n            {_MARKER!r}\n            + json.dumps(\n                {{\n                    "cadrumo_file": str(Path(cadrumo.__file__).resolve()),\n                    "extra_available": optional_extra_available(LLM_EXTRA),\n                    "outcomes": outcomes,\n                }},\n                sort_keys=True,\n            )\n        )\n        ')
    completed = subprocess.run([str(python), '-c', code], cwd=work_dir, env=_isolated_environment(work_dir), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180, check=False)
    assert completed.returncode == 0, completed.stderr
    line = _dp_next('dev/packaging/tests/test_missing_llm_extra_refuses_instructively.py:244:next', (row for row in completed.stdout.splitlines() if row.startswith(_MARKER)), None)
    assert line is not None, completed.stdout
    report = json.loads(line.removeprefix(_MARKER))
    assert isinstance(report, dict)
    typed_report: dict[str, object] = {}
    for key, value in report.items():
        assert isinstance(key, str), 'JSON object keys must be strings'
        typed_report[key] = value
    return typed_report

def test_the_driven_inventory_covers_every_guarded_entry_point() -> None:
    """A newly guarded production definition cannot silently escape the real lane."""
    derived = _guarded_definition_names()
    assert derived, 'no production require_optional_extra(LLM_EXTRA) guard was found'
    driven = {name for name, _call in _GUARDED_SURFACES}
    assert not derived - driven, f'guarded production entry points not driven by this lane: {sorted(derived - driven)!r}'

@pytest.mark.timeout(900)
def test_every_guarded_surface_preserves_the_registered_extra_facts(installed_core_environment: tuple[Path, Path]) -> None:
    """Every guarded surface refuses in a genuine no-extra product install."""
    work_dir, python = installed_core_environment
    report = _drive_surfaces(work_dir, python)
    assert Path(str(report['cadrumo_file'])).is_relative_to(python.parents[1])
    assert report['extra_available'] is False
    outcomes = report['outcomes']
    assert isinstance(outcomes, list) and outcomes
    expected_names = {name for name, _call in _GUARDED_SURFACES}
    observed_names = {entry['name'] for entry in outcomes if isinstance(entry, dict)}
    assert observed_names == expected_names
    expected_extra = LLM_EXTRA.model_dump(mode='json')
    wrong = [entry for entry in outcomes if not isinstance(entry, dict) or entry.get('outcome') != 'refused' or entry.get('extra') != expected_extra]
    assert not wrong, f'installed core LLM surfaces did not preserve the registered typed extra: {wrong!r}'