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
import json
import sys
from pathlib import Path
from typing import Final

from packaging.requirements import Requirement

from dev.packaging._distribution_names import normalise_distribution_name
from dev.packaging._smoke_common import (
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

_EXTRA: Final[str] = "llm"
_EXPECTED_HINT: Final[str] = "pip install cadrumo[llm]"

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
        "extract_invoice_fields_from_images",
        "extract_invoice_fields_from_images((MultimodalImageInput(base64_data='', media_type='image/png'),))",
    ),
    (
        "extract_invoice_fields_from_text",
        "extract_invoice_fields_from_text('factura')",
    ),
    (
        "LocalVisionLLMClassifier",
        "LocalVisionLLMClassifier(spec=None)",
    ),
    (
        "LocalTextLLMClassifier",
        "LocalTextLLMClassifier(spec=None)",
    ),
)


def _install_core_without_extras(work_dir: Path, cohort: PythonCohort, venv_path: Path) -> None:
    """Install the exact cohort with NO extras, which is this lane's whole premise."""
    install_targets_with_pip(
        work_dir,
        install_targets(cohort, root_artifact=cohort.root_wheel, extras=()),
        venv_path,
    )


def _assert_extra_is_real_in_the_artifact(wheel: Path) -> None:
    """Verify the wheel declares an ``llm`` extra that adds something to core.

    An extra every one of whose requirements is ALSO an unconditional core
    requirement is nominal: installing it changes nothing, so its guard can
    never fire and this lane can never observe a refusal. Read from the built
    wheel's own metadata rather than from ``pyproject.toml``, because the wheel
    is what an operator installs and the two can drift.
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
    record_proof(f"{_EXTRA} extra adds {sorted(exclusive)!r} beyond the core closure")


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
    record_proof(f"{_EXTRA} probe target {import_name!r} is exclusive to the extra")


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
if LLM_EXTRA.install_hint != {_EXPECTED_HINT!r}:
    raise SystemExit(f"unexpected install hint: {{LLM_EXTRA.install_hint!r}}")
print("llm-extra-absent-ok")
"""
    run_checked(
        [str(venv_python_path(venv_path)), "-c", code],
        cwd=work_dir,
        env=_lane_env(work_dir, "probe-state"),
    )
    record_proof("llm extra probes absent in the core install")


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

from cadrumo.core import MissingOptionalExtraError
from cadrumo.llm import (
    LocalTextLLMClassifier,
    LocalVisionLLMClassifier,
    MultimodalImageInput,
    extract_invoice_fields_from_images,
    extract_invoice_fields_from_text,
    rasterise_pdf_pages_to_base64_png,
)

outcomes = []
for surface in json.loads({surfaces!r}):
    try:
        eval(surface["call"])
    except MissingOptionalExtraError as exc:
        outcomes.append({{"name": surface["name"], "outcome": "refused", "hint": exc.install_hint}})
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

    wrong = [entry for entry in outcomes if entry["outcome"] != "refused" or entry["hint"] != _EXPECTED_HINT]
    if wrong:
        raise SystemExit(
            "these inference surfaces did not refuse with the declared install guidance in a core "
            f"install: {wrong!r}. Each must raise MissingOptionalExtraError naming {_EXPECTED_HINT!r}; a "
            "'module-not-found' outcome is the raw failure the guard exists to convert, and a 'succeeded' "
            "outcome is a model-bearing surface running without the model-bearing dependencies.",
        )
    record_proof(f"{len(outcomes)} inference surfaces refuse with the declared install guidance")


def _assert_core_cli_still_works(work_dir: Path, venv_path: Path) -> None:
    """Verify the core CLI is unaffected: the extra is absent, not the product."""
    version = run_checked(
        [str(venv_cadrumo_path(venv_path)), "--version"],
        cwd=work_dir,
        env=_lane_env(work_dir, "cli-state"),
    )
    assert_cadrumo_version_output(version, context="in absent-llm venv")
    record_proof("core CLI runs without the llm extra")


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

    repo_root = Path(__file__).resolve().parents[2]
    require_executable("uv")
    work_dir = resolve_work_dir(repo_root, args.work_dir, prefix="absent-llm")
    print(f"absent-llm packaging smoke work dir: {work_dir}", flush=True)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    assert_wheel_metadata_matches_pyproject(repo_root, wheel)
    _assert_extra_is_real_in_the_artifact(wheel)
    _assert_probe_target_is_exclusive_to_the_extra(repo_root, wheel)

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

    manifest = write_smoke_manifest(
        work_dir,
        lane="absent-llm-wheel",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "venv": relative_manifest_path(work_dir, venv_path),
        },
        declared=(
            "wheel metadata dependency surface",
            f"{_EXTRA} extra adds requirements beyond the core closure",
            f"{_EXTRA} probe target is exclusive to the extra",
            "stdlib venv creation",
            "exact local cohort install with pip and no extras",
            "llm extra probes absent in the core install",
            "inference surfaces refuse with the declared install guidance",
            "core CLI runs without the llm extra",
        ),
        details={
            "cohort_version": cohort.version,
            "python": args.python,
            "surfaces": [name for name, _call in _INFERENCE_SURFACES],
        },
    )

    print(f"absent-llm packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
