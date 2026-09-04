"""Generate a versioned Scoop manifest from one immutable Python wheel cohort."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path

from packaging.requirements import Requirement

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Append (never insert) the repository root so the real PyPI ``packaging``
# distribution keeps priority over the repo's ``packaging/`` source directory,
# while the developer ``dev.packaging`` tooling package still resolves.
if str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

from dev.packaging._distribution_names import normalise_distribution_name  # noqa: E402
from dev.packaging._hashing import sha256_path  # noqa: E402
from dev.packaging.python_cohort import load_python_cohort  # noqa: E402
from dev.packaging.uv_constraints import export_runtime_constraints  # noqa: E402

_DISTRIBUTIONS = (
    ("cadrumo", "cadrumo-*.whl"),
    ("cadrumo-data-manuals", "cadrumo_data_manuals-*.whl"),
    ("cadrumo-data-official", "cadrumo_data_official-*.whl"),
)


@dataclass(frozen=True)
class WheelArtifact:
    """One verified wheel used by the generated Scoop manifest."""

    distribution: str
    version: str
    path: Path
    sha256: str
    requirements: tuple[str, ...]


def _wheel_artifact(cohort_dir: Path, distribution: str, wheel_glob: str) -> WheelArtifact:
    matches = tuple(sorted(cohort_dir.glob(wheel_glob)))
    if len(matches) != 1:
        raise SystemExit(
            f"expected one {distribution} wheel matching {wheel_glob!r}; got {[path.name for path in matches]!r}",
        )
    wheel = matches[0].resolve(strict=True)
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = tuple(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        if len(metadata_names) != 1:
            raise SystemExit(f"expected one METADATA member in {wheel}: {metadata_names!r}")
        metadata = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
    observed_name = metadata.get("Name")
    version = metadata.get("Version")
    if not observed_name or not version:
        raise SystemExit(f"wheel metadata lacks Name or Version: {wheel}")
    if normalise_distribution_name(observed_name) != distribution:
        raise SystemExit(
            f"wheel {wheel.name!r} declares {normalise_distribution_name(observed_name)!r}, expected {distribution!r}",
        )
    return WheelArtifact(
        distribution=distribution,
        version=version,
        path=wheel,
        sha256=sha256_path(wheel),
        requirements=tuple(metadata.get_all("Requires-Dist", [])),
    )


def _validate_companion_pins(
    root: WheelArtifact,
    manuals: WheelArtifact,
    official: WheelArtifact,
) -> None:
    requirements = [Requirement(value) for value in root.requirements]
    for companion in (manuals, official):
        matches = [
            requirement
            for requirement in requirements
            if normalise_distribution_name(requirement.name) == companion.distribution
        ]
        if len(matches) != 1:
            raise SystemExit(
                f"root wheel must declare exactly one dependency on {companion.distribution}",
            )
        requirement = matches[0]
        if (
            requirement.extras
            or requirement.marker is not None
            or str(requirement.specifier) != f"=={companion.version}"
        ):
            raise SystemExit(
                f"root wheel must require {companion.distribution}=={companion.version} "
                "unconditionally and without extras; found "
                f"{requirement}",
            )


def _wrapper_script(executable: str) -> str:
    return (
        "$state = Join-Path $persist_dir 'state'; "
        '$wrapper = "@echo off`r`n'
        "if not defined CADRUMO_LOCAL_STORAGE_ROOT "
        'set `"CADRUMO_LOCAL_STORAGE_ROOT=$state`"`r`n'
        f'`"%~dp0venv\\Scripts\\{executable}.exe`" %*`r`n"; '
        f"Set-Content -LiteralPath (Join-Path $dir '{executable}.cmd') "
        "-Value $wrapper -NoNewline -Encoding ascii"
    )


def generate_manifest(
    *,
    cohort_dir: Path,
    version: str,
) -> dict[str, object]:
    """Return one Scoop manifest bound to exact cohort filenames and hashes."""
    load_python_cohort(cohort_dir)
    artifacts = tuple(
        _wheel_artifact(cohort_dir, distribution, wheel_glob) for distribution, wheel_glob in _DISTRIBUTIONS
    )
    observed_versions = {artifact.version for artifact in artifacts}
    if observed_versions != {version}:
        raise SystemExit(
            f"cohort wheel versions must all equal {version!r}: {sorted(observed_versions)!r}",
        )
    root, manuals, official = artifacts
    _validate_companion_pins(root, manuals, official)
    constraints_body = "\n".join(export_runtime_constraints(repo_root=_REPO_ROOT))
    python_path = "(Join-Path $dir 'venv\\Scripts\\python.exe')"
    pre_install = [
        "New-Item -ItemType Directory -Force -Path (Join-Path $dir 'state') | Out-Null",
        "$python = (Get-Command python.exe -ErrorAction Stop).Source; "
        "& uv venv (Join-Path $dir 'venv') --python $python; "
        "if ($LASTEXITCODE -ne 0) { throw 'uv venv failed' }",
        # Pin the transitive dependency closure to the tested uv.lock. A verbatim
        # here-string keeps every requirement marker (single quotes included)
        # literal, so the constraints file is written byte-for-byte as exported.
        "Set-Content -LiteralPath (Join-Path $dir 'constraints.txt') -Value @'\n"
        f"{constraints_body}\n"
        "'@ -Encoding ascii",
        # Installed from the index by name and exact version. The wheels are
        # not downloaded by the manifest: only a source distribution has a
        # stable address on the index ahead of an upload, and addressing a
        # release asset instead would point this manifest at a surface no
        # workflow populates. The constraints file still pins the whole
        # transitive closure to the tested lock.
        f"& uv pip install --python {python_path} --no-cache "
        "--constraint (Join-Path $dir 'constraints.txt') "
        f"'cadrumo=={version}'; "
        "if ($LASTEXITCODE -ne 0) { throw 'uv pip install failed' }",
        f"& uv pip check --python {python_path}; if ($LASTEXITCODE -ne 0) {{ throw 'uv pip check failed' }}",
        _wrapper_script("aeat"),
    ]
    return {
        "version": version,
        "description": (
            "Cadrumo is a deterministic Spanish tax calculation CLI "
            "that turns local financial records into checked, exportable modelo filing "
            "artifacts. Independent software; not affiliated with AEAT."
        ),
        "homepage": "https://github.com/nevenincs/cadrumo",
        "license": "Apache-2.0",
        "depends": ["python", "uv"],
        "pre_install": pre_install,
        "bin": [
            ["aeat.cmd", "aeat"],
        ],
        "persist": ["state"],
        "notes": [
            "Cadrumo state persists across Scoop updates.",
            "Verify with: aeat --version",
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-dir", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    """Generate and write one deterministic Scoop manifest."""
    args = _parser().parse_args()
    manifest = generate_manifest(
        cohort_dir=args.cohort_dir.resolve(strict=True),
        version=args.version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sys.stdout.write(f"{args.output.resolve()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
