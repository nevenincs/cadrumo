"""Prove the inference boundary refuses instructively in a core install.

This is the ``absent-llm`` lane. Every other lane asks whether the product
WORKS once installed; this one asks what the product SAYS when an operator
reaches a model-bearing surface without having opted into the model-bearing
dependencies. The answer must be one instructive refusal naming
``pip install cadrumo[llm]`` -- never a ``ModuleNotFoundError``, never a
traceback, never a silently absent verb.

The source-level guard is :func:`~core.require_optional_extra`, and it is
already covered where it is written. What no source-level test can establish is
whether the SHIPPED ARTIFACT actually produces the absent state: an extra whose
dependencies all arrive in the core closure anyway is nominal, its guard never
fires, and every source-level test of that guard passes against a condition no
install can reach. This lane closes that gap by installing the real cohort
without the extra and reaching the surfaces the way an operator would.

**The precondition is the load-bearing check, not a formality.** Before driving
any surface, the lane asserts that the ``llm`` extra actually probes as ABSENT
in the core install. That assertion is what makes every refusal below evidence
of a working guard rather than an accident; without it, a lane that reported
"all surfaces refused" would be equally consistent with surfaces that refuse for
some unrelated reason, and a lane that reported "nothing refused" would be
indistinguishable from a guard that is simply dormant by construction.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Final

from packaging.requirements import Requirement

from cadrumo.core import scan_directory

from .._paths import REPO_ROOT, UTF_8
from ._distribution_names import normalise_distribution_name
from ._smoke_common import (
    assert_cadrumo_version_output,
    assert_wheel_metadata_matches_pyproject,
    clean_product_env,
    create_pip_venv,
    install_targets_with_pip,
    optional_extra_registry,
    record_proof,
    relative_manifest_path,
    require_executable,
    resolve_work_dir,
    run_checked,
    venv_cadrumo_path,
    venv_python_path,
    wheel_metadata,
    write_smoke_manifest,
)
from .python_cohort import (
    PythonCohort,
    assert_installed_cohort,
    install_targets,
    load_python_cohort,
)

_UTF_8: Final[str] = UTF_8
_EXTRA: Final[str] = "llm"
_EXPECTED_EXTRA: Final[str] = "llm"

# Proof-ledger claims. Plain constants, deliberately: the contract gate reads
# them statically, so an f-string here declares a claim no assertion can be seen
# to record and the lane over-claims by construction. Anything variable about a
# proof (which requirements, how many surfaces) is printed beside it instead.
_CLAIM_EXTRA_IS_REAL: Final[str] = "llm extra adds requirements beyond the core closure"
_CLAIM_PROBE_IS_EXCLUSIVE: Final[str] = "llm probe target is exclusive to the extra"
_CLAIM_EXTRA_PROBES_ABSENT: Final[str] = "llm extra probes absent in the core install"
_CLAIM_SURFACES_REFUSE: Final[str] = "inference surfaces refuse with the declared install guidance"
_CLAIM_CORE_CLI_WORKS: Final[str] = "core CLI runs without the llm extra"
_CLAIM_GUARDED_SET_IS_DERIVED: Final[str] = "guarded surface set derived from the production guard call sites"
_CLAIM_GUARDED_SURFACES_WORK: Final[str] = "guarded surfaces do not refuse once the extra is installed"
_CLAIM_UNINSTALL_RESTORES_REFUSAL: Final[str] = "uninstalling the extra returns every guarded surface to the refusal"

#: The model-bearing surfaces of the inference boundary, each named with the
#: call that reaches it. Every entry is an operator-reachable entry point that
#: the governing decision places on the extra's side of the cut, so each must
#: refuse in a core install. The inventory is explicit rather than derived from
#: ``cadrumo.llm.__all__`` because most of that export set is interchange DTOs
#: and error types, which carry no guard and correctly import in a core install
#: -- deriving the list would silently enroll them and make the lane pass by
#: driving things that were never gated.
_INFERENCE_SURFACES: Final[tuple[tuple[str, str], ...]] = (
    (
        "rasterise_pdf_pages_to_base64_png",
        "rasterise_pdf_pages_to_base64_png(b'%PDF-1.4\\n')",
    ),
    (
        "transcribe_document_images",
        "transcribe_document_images(_PAGES, source_content_sha256='0' * 64)",
    ),
    (
        "extract_invoice_fields_from_text",
        "extract_invoice_fields_from_text(_TRANSCRIPTION)",
    ),
    (
        "LocalVisionLLMClassifier",
        "LocalVisionLLMClassifier(spec=None)",
    ),
    (
        "LocalTextLLMClassifier",
        "LocalTextLLMClassifier(spec=None)",
    ),
    # The three constructors the convenience wrappers above build. Each is
    # exported and carries the guard itself, so the derivation enrolls it and
    # the completeness claim covers it. Driven with no arguments, which every
    # one of them accepts: the guard is the first statement of ``__init__``, so
    # a bare construction reaches it before any settings or model resolution
    # could raise something else.
    (
        "LocalVisionDocumentTranscriber",
        "LocalVisionDocumentTranscriber()",
    ),
    (
        "TextInvoiceFieldExtractor",
        "TextInvoiceFieldExtractor()",
    ),
    # The tabular lane's split point: a known fixed-layout file never reaches
    # this call, an unknown header vocabulary does.
    (
        "SemanticColumnRoleMapper",
        "SemanticColumnRoleMapper()",
    ),
)


def _guard_symbol_for_the_extra(repo_root: Path) -> str:
    """Return the registry symbol the production guard is called with for this extra.

    Derived from the registry rather than hardcoded, and checked against the
    symbols :data:`OPTIONAL_EXTRAS` actually enumerates, so a renamed record
    fails here instead of silently yielding an empty guarded set below.
    """
    _extras, symbols = optional_extra_registry(repo_root)
    symbol = f"{_EXTRA.upper()}_EXTRA"
    if symbol not in symbols:
        raise SystemExit(
            f"the core optional-extra registry enumerates {sorted(symbols)!r}, which does not include "
            f"{symbol!r}; the guarded-surface derivation below has nothing to key on.",
        )
    return symbol


def _guarded_surfaces_from_production_guards(repo_root: Path, symbol: str) -> tuple[frozenset[str], frozenset[str]]:
    """Derive the guarded surfaces from the PRODUCTION guard call sites.

    Walks the AST of every non-test module under the gated subpackage for a call
    to ``require_optional_extra(<symbol>)`` and attributes it to the OUTERMOST
    enclosing definition -- the callable an operator can name. The walk is
    structural throughout: nothing here slices source text, so a guard inside a
    branch, a nested helper, or a string mentioning the guard's name cannot
    change the answer.

    Deriving beats declaring for one reason that matters to this lane's claim:
    "every guarded surface returns to the refusal" is a completeness claim, and
    a hand-kept inventory makes it a claim over a set the lane's own author
    chose. A guard added to a new entry point enrolls itself here; one added to
    a hand list only when someone remembers.

    Returns:
        ``(reachable, internal)`` -- the derived names the package exports, and
        the derived names it does not. The second set is reported rather than
        dropped: an operator cannot reach those directly, but a lane that
        silently discarded them would be capping its own denominator.
    """
    package = repo_root / "src" / "cadrumo" / "llm"
    exported = _exported_names(package / "__init__.py")
    derived: set[str] = set()
    for path in scan_directory(package, pattern="*.py", recursive=True):
        if "tests" in path.relative_to(package).parts:
            continue
        tree = ast.parse(path.read_text(encoding=_UTF_8), filename=str(path))
        derived |= _guarded_definition_names(tree, symbol)
    if not derived:
        raise SystemExit(
            f"no production call to require_optional_extra({symbol}) was found under {package}. The lane's "
            "guarded-surface set would be empty, and an empty set makes every completeness assertion below "
            "vacuously true -- which is indistinguishable from a pass.",
        )
    return frozenset(derived & exported), frozenset(derived - exported)


def _exported_names(init_path: Path) -> frozenset[str]:
    """Return the string members of the module's ``__all__``, read structurally."""
    tree = ast.parse(init_path.read_text(encoding=_UTF_8), filename=str(init_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = node.value
        if isinstance(value, ast.List | ast.Tuple | ast.Set):
            return frozenset(
                element.value
                for element in value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            )
    raise SystemExit(f"no literal __all__ found in {init_path}")


def _guarded_definition_names(tree: ast.Module, symbol: str) -> set[str]:
    """Return the outermost definition names enclosing a guard call, by AST descent."""
    found: set[str] = set()

    def contains_guard(node: ast.AST) -> bool:
        return any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "require_optional_extra"
            and any(isinstance(arg, ast.Name) and arg.id == symbol for arg in child.args)
            for child in ast.walk(node)
        )

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and contains_guard(node):
            found.add(node.name)
    return found


def _assert_the_driver_reaches_every_guarded_surface(
    reachable: frozenset[str],
    internal: frozenset[str],
) -> None:
    """Require the driver inventory to cover the derived set, and print what it does not.

    The direction of the check is the point. A derived surface the driver never
    reaches is a hole in the completeness claim and fails. A driver entry with no
    derived guard is NOT a failure -- those surfaces are driven for reachability
    rather than because they carry the guard themselves -- but it is printed, so
    the lane's coverage is legible instead of implied.
    """
    driven = {name for name, _call in _INFERENCE_SURFACES}
    unreached = sorted(reachable - driven)
    if unreached:
        raise SystemExit(
            f"these surfaces carry the production require_optional_extra({_EXTRA.upper()}_EXTRA) guard but "
            f"the lane never drives them: {unreached!r}. The lane cannot claim every guarded surface "
            "returns to the refusal while some are never reached.",
        )
    print(f"derived guarded surfaces (driven): {sorted(reachable)!r}", flush=True)
    if internal:
        print(
            f"derived guarded definitions NOT exported, so not operator-reachable and excluded from the "
            f"completeness claim: {sorted(internal)!r}",
            flush=True,
        )
    reachability_only = sorted(driven - reachable)
    if reachability_only:
        print(
            f"driven for reachability but carrying no guard of their own: {reachability_only!r}",
            flush=True,
        )
    record_proof(_CLAIM_GUARDED_SET_IS_DERIVED)


def _install_core_with_the_extra(work_dir: Path, cohort: PythonCohort, venv_path: Path) -> None:
    """Install the exact cohort WITH the extra, the state the uninstall step starts from."""
    install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=cohort.root_wheel, extras=(_EXTRA,)),
        venv_path,
    )


def _assert_guarded_surfaces_do_not_refuse(
    work_dir: Path,
    venv_path: Path,
    reachable: frozenset[str],
) -> None:
    """The positive control: with the extra installed, no guarded surface refuses.

    Without this, "the surfaces refuse after uninstall" is satisfiable by a
    surface that refuses unconditionally -- a guard wired to fire always would
    pass every assertion in this lane and be indistinguishable from a correct
    one. What is asserted is narrow and deliberate: only that the EXTRA refusal
    is absent. A guarded call driven with a deliberately empty input is expected
    to fail on its own terms, and demanding a success would be asserting the
    feature works rather than that the gate opened.
    """
    calls = json.dumps([{"name": name, "call": call} for name, call in _INFERENCE_SURFACES if name in reachable])
    outcomes = _drive_surfaces(work_dir, venv_path, calls, leaf="present-state")
    refused = [entry for entry in outcomes if entry["outcome"] in {"refused", "module-not-found"}]
    if refused:
        raise SystemExit(
            f"these guarded surfaces still reported the extra as missing WITH the extra installed: "
            f"{refused!r}. Every refusal this lane observes after the uninstall would then be evidence of "
            "nothing.",
        )
    print(f"{len(outcomes)} guarded surfaces opened with the extra installed", flush=True)
    record_proof(_CLAIM_GUARDED_SURFACES_WORK)


def _uninstall_the_extra(work_dir: Path, venv_path: Path, exclusive: frozenset[str]) -> None:
    """Remove exactly the distributions the extra adds beyond the core closure."""
    run_checked(
        [
            str(venv_python_path(venv_path)),
            "-m",
            "pip",
            "uninstall",
            "--disable-pip-version-check",
            "--yes",
            *sorted(exclusive),
        ],
        cwd=work_dir,
    )


def _assert_uninstall_restores_the_refusal(
    work_dir: Path,
    venv_path: Path,
    reachable: frozenset[str],
) -> None:
    """Every guarded surface must return to the instructive refusal after the uninstall."""
    _assert_extra_probes_absent(work_dir, venv_path)
    calls = json.dumps([{"name": name, "call": call} for name, call in _INFERENCE_SURFACES if name in reachable])
    outcomes = _drive_surfaces(work_dir, venv_path, calls, leaf="uninstalled-state")
    driven = {entry["name"] for entry in outcomes}
    if driven != set(reachable):
        raise SystemExit(f"the driver did not reach every guarded surface: missing {sorted(reachable - driven)!r}")
    wrong = [entry for entry in outcomes if entry["outcome"] != "refused" or entry.get("extra") != _EXPECTED_EXTRA]
    if wrong:
        raise SystemExit(
            "these guarded surfaces did not return to the instructive refusal after the extra was "
            f"uninstalled: {wrong!r}. A surface that keeps working once its dependencies are removed is "
            "reaching them by a path the guard does not cover.",
        )
    print(f"{len(outcomes)} guarded surfaces returned to the instructive refusal after uninstall", flush=True)
    record_proof(_CLAIM_UNINSTALL_RESTORES_REFUSAL)


def _drive_surfaces(work_dir: Path, venv_path: Path, calls: str, *, leaf: str) -> list[dict[str, str]]:
    """Drive the named surfaces in the installed venv and return their classified outcomes."""
    code = f"""
import json

from cadrumo.application.ledger import DocumentTranscription, TranscriberIdentity
from cadrumo.core import FieldOrigin, ImageMediaType, MissingOptionalExtraError
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

# Both surfaces take a TYPED argument, so the driver builds each one here rather
# than inline in the call expression. That placement is the point: Python
# evaluates arguments before the callee, so an argument that fails to construct
# raises BEFORE the guarded surface is entered -- the entry would be classified
# "other" and could never reach the refusal the lane asserts. Built outside the
# try, a broken driver fails loudly as a driver rather than masquerading as a
# surface outcome. Both constructions are core-only: typed models, no optional
# dependency.
_PAGES = (MultimodalImageInput.from_base64("aGk=", ImageMediaType.PNG),)
_TRANSCRIPTION = DocumentTranscription(
    text="factura",
    page_count=1,
    source_content_sha256="0" * 64,
    transcriber=TranscriberIdentity(origin=FieldOrigin.TEXT_LAYER, name="smoke", revision="lane"),
)

outcomes = []
for surface in json.loads({calls!r}):
    try:
        eval(surface["call"])
    except MissingOptionalExtraError as exc:
        outcomes.append({{"name": surface["name"], "outcome": "refused", "extra": exc.extra.extra}})
    except ModuleNotFoundError as exc:
        outcomes.append({{"name": surface["name"], "outcome": "module-not-found", "hint": str(exc)}})
    except BaseException as exc:
        outcomes.append(
            {{"name": surface["name"], "outcome": "other", "hint": f"{{type(exc).__name__}}: {{exc}}"}}
        )
    else:
        outcomes.append({{"name": surface["name"], "outcome": "succeeded", "hint": ""}})

print("SURFACE_OUTCOMES:" + json.dumps(outcomes))
"""
    result = run_checked(
        [str(venv_python_path(venv_path)), "-c", code],
        cwd=work_dir,
        env=_lane_env(work_dir, leaf),
    )
    marker = "SURFACE_OUTCOMES:"
    line = next((row for row in result.stdout.splitlines() if row.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"the surface driver produced no outcomes; stdout was: {result.stdout!r}")
    parsed: list[dict[str, str]] = json.loads(line[len(marker) :])
    if not parsed:
        raise SystemExit(
            "the surface driver returned an empty outcome set, so every assertion over it holds "
            "vacuously; the guarded-surface set reaching the driver was empty.",
        )
    return parsed


def _install_core_without_extras(work_dir: Path, cohort: PythonCohort, venv_path: Path) -> None:
    """Install the exact cohort with NO extras, which is this lane's whole premise."""
    install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=cohort.root_wheel, extras=()),
        venv_path,
    )


def _assert_extra_is_real_in_the_artifact(wheel: Path) -> frozenset[str]:
    """Verify the wheel declares an ``llm`` extra that adds something to core.

    An extra every one of whose requirements is ALSO an unconditional core
    requirement is nominal: installing it changes nothing, so its guard can
    never fire and this lane can never observe a refusal. Read from the built
    wheel's own metadata rather than from ``pyproject.toml``, because the wheel
    is what an operator installs and the two can drift.

    Returns:
        The distributions the extra adds beyond core -- exactly the set the
        uninstall step removes, so the removal is derived from the artifact
        rather than from a second hand-kept list that could drift from it.
    """
    requirements, provided_extras = wheel_metadata(wheel)
    if normalise_distribution_name(_EXTRA) not in provided_extras:
        raise SystemExit(f"the built wheel declares no {_EXTRA!r} extra; provides: {sorted(provided_extras)!r}")

    core_names: set[str] = set()
    extra_names: set[str] = set()
    for row in requirements:
        requirement = Requirement(row)
        name = normalise_distribution_name(requirement.name)
        marker = str(requirement.marker) if requirement.marker else ""
        if not marker:
            core_names.add(name)
        elif f'extra == "{_EXTRA}"' in marker or f"extra == '{_EXTRA}'" in marker:
            extra_names.add(name)

    if not extra_names:
        raise SystemExit(f"the built wheel's {_EXTRA!r} extra declares no requirements")
    exclusive = extra_names - core_names
    if not exclusive:
        raise SystemExit(
            f"every requirement of the {_EXTRA!r} extra ({sorted(extra_names)!r}) is also an unconditional "
            "core requirement, so installing the extra changes nothing and its guard can never fire. The "
            "extra is nominal; this lane cannot observe a refusal until at least one requirement is "
            "exclusive to it.",
        )
    print(f"{_EXTRA} extra adds {sorted(exclusive)!r} beyond the core closure", flush=True)
    record_proof(_CLAIM_EXTRA_IS_REAL)
    return frozenset(exclusive)


def _assert_probe_target_is_exclusive_to_the_extra(repo_root: Path, wheel: Path) -> None:
    """Verify the registered probe module is NOT satisfied by the core closure.

    This is the precondition the rest of the lane rests on. The guard probes one
    import name; if the distribution providing that name is an unconditional
    core requirement, then ``optional_extra_available`` is permanently true in
    every core install and ``require_optional_extra`` is a no-op. The extra can
    be perfectly real (the check above passes) while the PROBE still points at
    a package core always supplies -- the two are independent, which is why this
    is a separate assertion rather than a stronger form of the previous one.
    """
    registry_extras, _symbols = optional_extra_registry(repo_root)
    import_name = registry_extras.get(_EXTRA)
    if not import_name:
        raise SystemExit(f"the core optional-extra registry has no {_EXTRA!r} entry to probe")

    requirements, _provided = wheel_metadata(wheel)
    core_names = {
        normalise_distribution_name(requirement.name)
        for row in requirements
        if (requirement := Requirement(row)).marker is None
    }
    providing = _distributions_providing(import_name)
    supplied_by_core = providing & core_names
    if supplied_by_core:
        raise SystemExit(
            f"the {_EXTRA!r} extra probes the import name {import_name!r}, which is provided by "
            f"{sorted(supplied_by_core)!r} -- an UNCONDITIONAL core requirement of the shipped wheel. The "
            "probe therefore succeeds in every core install, require_optional_extra is a permanent no-op, "
            "and no inference surface can refuse. Repoint the registry entry at an import name supplied "
            "only by the extra.",
        )
    print(f"{_EXTRA} probe target {import_name!r} is exclusive to the extra", flush=True)
    record_proof(_CLAIM_PROBE_IS_EXCLUSIVE)


def _distributions_providing(import_name: str) -> set[str]:
    """Return the normalised distributions that provide ``import_name`` here.

    Resolved through :func:`importlib.metadata.packages_distributions` rather
    than a hand-kept table, so the mapping tracks what is actually installed
    instead of drifting from it. Falls back to the import name itself when the
    package is not installed in this environment, which is the best available
    key and keeps the check conservative.
    """
    from importlib.metadata import packages_distributions

    found = {normalise_distribution_name(name) for name in packages_distributions().get(import_name, [])}
    return found or {normalise_distribution_name(import_name)}


def _assert_extra_probes_absent(work_dir: Path, venv_path: Path) -> None:
    """Verify the installed core venv reports the extra as absent."""
    code = f"""
from cadrumo.core import LLM_EXTRA, optional_extra_available

if optional_extra_available(LLM_EXTRA):
    raise SystemExit(
        "the llm extra probes as PRESENT in a core install (probe import name "
        f"{{LLM_EXTRA.import_name!r}}), so every guard below it is dormant"
    )
if LLM_EXTRA.extra != {_EXPECTED_EXTRA!r}:
    raise SystemExit(f"unexpected extra identity: {{LLM_EXTRA.extra!r}}")
print("llm-extra-absent-ok")
"""
    run_checked(
        [str(venv_python_path(venv_path)), "-c", code],
        cwd=work_dir,
        env=_lane_env(work_dir, "probe-state"),
    )
    record_proof(_CLAIM_EXTRA_PROBES_ABSENT)


def _assert_inference_surfaces_refuse(work_dir: Path, venv_path: Path) -> None:
    """Drive every inference-adjacent surface and require the declared guidance.

    Each surface is classified rather than merely asserted, so a failure names
    WHICH surface behaved how. The two outcomes that must never appear are a
    ``ModuleNotFoundError`` (the raw deep-stack failure the guard exists to
    convert) and a successful call (a model-bearing surface running without the
    model-bearing dependencies).
    """
    surfaces = json.dumps([{"name": name, "call": call} for name, call in _INFERENCE_SURFACES])
    code = f"""
import json

from cadrumo.application.ledger import DocumentTranscription, TranscriberIdentity
from cadrumo.core import FieldOrigin, ImageMediaType, MissingOptionalExtraError
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

# Both surfaces take a TYPED argument, so the driver builds each one here rather
# than inline in the call expression. That placement is the point: Python
# evaluates arguments before the callee, so an argument that fails to construct
# raises BEFORE the guarded surface is entered -- the entry would be classified
# "other" and could never reach the refusal the lane asserts. Built outside the
# try, a broken driver fails loudly as a driver rather than masquerading as a
# surface outcome. Both constructions are core-only: typed models, no optional
# dependency.
_PAGES = (MultimodalImageInput.from_base64("aGk=", ImageMediaType.PNG),)
_TRANSCRIPTION = DocumentTranscription(
    text="factura",
    page_count=1,
    source_content_sha256="0" * 64,
    transcriber=TranscriberIdentity(origin=FieldOrigin.TEXT_LAYER, name="smoke", revision="lane"),
)

outcomes = []
for surface in json.loads({surfaces!r}):
    try:
        eval(surface["call"])
    except MissingOptionalExtraError as exc:
        outcomes.append({{"name": surface["name"], "outcome": "refused", "extra": exc.extra.extra}})
    except ModuleNotFoundError as exc:
        outcomes.append({{"name": surface["name"], "outcome": "module-not-found", "hint": str(exc)}})
    except BaseException as exc:
        outcomes.append(
            {{"name": surface["name"], "outcome": "other", "hint": f"{{type(exc).__name__}}: {{exc}}"}}
        )
    else:
        outcomes.append({{"name": surface["name"], "outcome": "succeeded", "hint": ""}})

print("SURFACE_OUTCOMES:" + json.dumps(outcomes))
"""
    result = run_checked(
        [str(venv_python_path(venv_path)), "-c", code],
        cwd=work_dir,
        env=_lane_env(work_dir, "surface-state"),
    )
    marker = "SURFACE_OUTCOMES:"
    line = next((row for row in result.stdout.splitlines() if row.startswith(marker)), None)
    if line is None:
        raise SystemExit(f"the surface driver produced no outcomes; stdout was: {result.stdout!r}")
    outcomes = json.loads(line[len(marker) :])

    driven = {entry["name"] for entry in outcomes}
    expected = {name for name, _call in _INFERENCE_SURFACES}
    if driven != expected:
        raise SystemExit(f"the driver did not reach every surface: missing {sorted(expected - driven)!r}")

    wrong = [entry for entry in outcomes if entry["outcome"] != "refused" or entry.get("extra") != _EXPECTED_EXTRA]
    if wrong:
        raise SystemExit(
            "these inference surfaces did not refuse with the declared install guidance in a core "
            f"install: {wrong!r}. Each must raise MissingOptionalExtraError naming extra {_EXPECTED_EXTRA!r}; a "
            "'module-not-found' outcome is the raw failure the guard exists to convert, and a 'succeeded' "
            "outcome is a model-bearing surface running without the model-bearing dependencies.",
        )
    print(f"{len(outcomes)} inference surfaces refused with the declared install guidance", flush=True)
    record_proof(_CLAIM_SURFACES_REFUSE)


def _assert_core_cli_still_works(work_dir: Path, venv_path: Path) -> None:
    """Verify the core CLI is unaffected: the extra is absent, not the product."""
    version = run_checked(
        [str(venv_cadrumo_path(venv_path)), "--version"],
        cwd=work_dir,
        env=_lane_env(work_dir, "cli-state"),
    )
    assert_cadrumo_version_output(version, context="in absent-llm venv")
    record_proof(_CLAIM_CORE_CLI_WORKS)


def _lane_env(work_dir: Path, leaf: str) -> dict[str, str]:
    """Return an isolated product environment rooted under ``work_dir``."""
    root = work_dir / leaf
    return {
        **clean_product_env(),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(root),
        "CADRUMO_DATABASE_URL": f"sqlite:///{(work_dir / f'{leaf}.db').as_posix()}",
        "CADRUMO_OUTPUT_LANGUAGE": "en",
    }


def main(argv: list[str] | None = None) -> int:
    """Run the absent-llm installed-wheel packaging smoke gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--python",
        default=f"{sys.version_info.major}.{sys.version_info.minor}",
        help="Expected Python major.minor for the stdlib venv.",
    )
    parser.add_argument("--work-dir", help="Empty directory for venv and absent-extra artifacts.")
    parser.add_argument(
        "--cohort-dir",
        required=True,
        type=Path,
        help="Directory containing the prebuilt immutable Python cohort.",
    )
    args = parser.parse_args(argv)

    repo_root = REPO_ROOT
    require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="absent-llm")
    print(f"absent-llm packaging smoke work dir: {work_dir}", flush=True)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    assert_wheel_metadata_matches_pyproject(repo_root, wheel)
    exclusive = _assert_extra_is_real_in_the_artifact(wheel)
    _assert_probe_target_is_exclusive_to_the_extra(repo_root, wheel)
    guard_symbol = _guard_symbol_for_the_extra(repo_root)
    reachable, internal = _guarded_surfaces_from_production_guards(repo_root, guard_symbol)
    _assert_the_driver_reaches_every_guarded_surface(reachable, internal)

    print("creating stdlib venv and installing the cohort with NO extras", flush=True)
    venv_path = create_pip_venv(work_dir, args.python)
    _install_core_without_extras(work_dir, cohort, venv_path)
    assert_installed_cohort(
        venv_python_path(venv_path),
        cohort,
        root_artifact=wheel,
        cwd=work_dir,
    )
    _assert_extra_probes_absent(work_dir, venv_path)
    _assert_inference_surfaces_refuse(work_dir, venv_path)
    _assert_core_cli_still_works(work_dir, venv_path)

    # The uninstall half, in its own venv. The absent state above is reached by
    # never installing the extra; this one is reached by installing it, proving
    # the guarded surfaces OPEN, and then removing it again. The two are
    # different claims: the first says a core install refuses, the second says
    # the refusal is a live function of what is installed rather than a
    # permanent property of the build.
    print("creating a second venv, installing WITH the extra, then uninstalling it", flush=True)
    # A sibling work root rather than a second name in the same one: the shared
    # helper roots its venv at a fixed leaf, and reusing that leaf would build
    # the with-extra environment on top of the core one this lane just proved.
    extra_root = work_dir / "with-extra"
    extra_root.mkdir(parents=True, exist_ok=True)
    extra_venv = create_pip_venv(extra_root, args.python)
    _install_core_with_the_extra(work_dir, cohort, extra_venv)
    _assert_guarded_surfaces_do_not_refuse(work_dir, extra_venv, reachable)
    _uninstall_the_extra(work_dir, extra_venv, exclusive)
    _assert_uninstall_restores_the_refusal(work_dir, extra_venv, reachable)

    manifest = write_smoke_manifest(
        work_dir,
        lane="absent-llm-wheel",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "venv": relative_manifest_path(work_dir, venv_path),
            "venv_with_extra": relative_manifest_path(work_dir, extra_venv),
        },
        declared=(
            "wheel metadata dependency surface",
            _CLAIM_EXTRA_IS_REAL,
            _CLAIM_PROBE_IS_EXCLUSIVE,
            _CLAIM_GUARDED_SET_IS_DERIVED,
            "stdlib venv creation",
            "exact local cohort install with pip",
            "pip dependency check",
            _CLAIM_EXTRA_PROBES_ABSENT,
            _CLAIM_SURFACES_REFUSE,
            _CLAIM_CORE_CLI_WORKS,
            _CLAIM_GUARDED_SURFACES_WORK,
            _CLAIM_UNINSTALL_RESTORES_REFUSAL,
        ),
        details={
            "cohort_version": cohort.version,
            "python": args.python,
            "surfaces": [name for name, _call in _INFERENCE_SURFACES],
            "guarded_surfaces": sorted(reachable),
            "guarded_but_unexported": sorted(internal),
            "uninstalled_distributions": sorted(exclusive),
        },
    )

    print(f"absent-llm packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
