"""Exercise an assembled interpreter outside the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from cadrumo.core.storage_environment import storage_directory

from ...command_execution import CommandResult, run_command
from ..hashing import digest
from ..verify import _verification_destination

PROBE = r"""
import importlib, json, os, pathlib, subprocess, sys, tempfile
root = pathlib.Path(sys.executable).parent.resolve()
assert sys.flags.isolated and sys.flags.no_site and sys.flags.no_user_site
assert sys.flags.safe_path and sys.dont_write_bytecode
assert all(pathlib.Path(p).resolve().is_relative_to(root) for p in sys.path)
assert 'PYTHONHOME' not in os.environ and 'PYTHONPATH' not in os.environ
assert 'VIRTUAL_ENV' not in os.environ
modules = ['pydantic_core._pydantic_core', 'cryptography.hazmat.bindings._rust',
           'lxml.etree', 'PIL._imaging', 'pikepdf._core', 'pypdfium2',
           'win32api', 'pythoncom', 'win32com.shell.shell', 'rtoml', 'yaml', 'httpx', 'textual']
origins = {name: importlib.import_module(name).__file__ for name in modules}
assert all(pathlib.Path(p).resolve().is_relative_to(root) for p in origins.values())
import pikepdf, pypdfium2, PIL.Image, io
pdf = pikepdf.Pdf.new()
pdf.add_blank_page(page_size=(72,72))
stream = io.BytesIO()
pdf.save(stream)
document = pypdfium2.PdfDocument(stream.getvalue())
assert len(document) == 1
document.close()
assert PIL.Image.new('RGB', (2,2)).size == (2,2)
child = subprocess.check_output([sys.executable, '-c',
    'import json,sys,pikepdf; print(json.dumps([sys.executable,sys.flags.isolated]))'], text=True)
assert json.loads(child) == [sys.executable, 1]
user = pathlib.Path(os.environ['CADRUMO_LOCAL_STORAGE_ROOT']).resolve()
import win32com
cache_root = pathlib.Path(os.environ['XDG_CACHE_HOME']).resolve()
assert pathlib.Path(win32com.__gen_path__).resolve().is_relative_to(cache_root / 'pywin32' / 'gen_py')
assert all(pathlib.Path(p).resolve().is_relative_to(root) for p in win32com.__path__)
temporary_root = pathlib.Path(os.environ['TEMP']).resolve()
assert pathlib.Path(tempfile.gettempdir()).resolve() == temporary_root
writes = []
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str,bytes)):
        mode, flags = args[1:3]
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or flags & (os.O_WRONLY | os.O_RDWR):
            writes.append(os.fsdecode(args[0]))
sys.addaudithook(audit)
with tempfile.NamedTemporaryFile() as temporary:
    temporary.write(b'native interpreter verification')
assert writes and all(pathlib.Path(p).resolve().is_relative_to(temporary_root) for p in writes)
print(json.dumps({'pid': os.getpid(), 'executable': sys.executable, 'version': sys.version, 'origins': origins,
                  'child': json.loads(child), 'python_audit_writes': writes, 'user_root': str(user),
                  'temporary_root': str(temporary_root), 'cache_root': str(cache_root)}))
"""


def verify(
    package: Path, destination: Path | None = None, *, product: bool = False, build_root: Path | None = None
) -> None:
    """Copy and verify an artifact in a fresh isolated staging directory."""
    package = package.resolve(strict=True)
    layout = json.loads((package / "data/package-manifest.json").read_text(encoding="utf-8"))["layout"]
    build_root = build_root or storage_directory("CADRUMO_NATIVE_BUILD_ROOT", "development/build/native")
    build_root = build_root.resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    destination = _verification_destination(destination, build_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, destination)
    cwd = destination.parent / (destination.name + " unrelated cwd")
    cwd.mkdir()
    (cwd / "python313.dll").write_bytes(b"host DLL must not load")
    (cwd / "pikepdf.py").write_text("raise RuntimeError('ambient import')", encoding="utf-8")
    environment = dict(os.environ)
    for name in tuple(environment):
        if name.upper().startswith("CADRUMO_"):
            environment.pop(name)
    storage_root = cwd / "storage"
    temporary_root = cwd / "temporary"
    cache_root = cwd / "cache"
    environment.update(
        {
            "PYTHONHOME": str(cwd),
            "PYTHONPATH": str(cwd),
            "PYTHONUSERBASE": str(cwd),
            "VIRTUAL_ENV": str(cwd),
            "CONDA_PREFIX": str(cwd),
            "PATH": str(cwd) + os.pathsep + environment.get("PATH", ""),
            "CADRUMO_STORAGE_ROOT": str(cwd / "canonical-storage"),
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "CADRUMO_TEMP_DIR": str(temporary_root),
            "CADRUMO_TOOL_CACHE_DIR": str(cache_root),
        }
    )
    exe = destination / "python.exe"

    def run(arguments: list[str], *, success: bool = True) -> CommandResult:
        result = run_command(
            [str(exe), *arguments],
            cwd=cwd,
            environment=environment,
            timeout_seconds=90,
        )
        if (result.returncode == 0) != success:
            raise AssertionError(f"Unexpected exit {result.returncode}: {result.stdout}\n{result.stderr}")
        return result

    before = {p.relative_to(destination).as_posix(): digest(p) for p in destination.rglob("*") if p.is_file()}
    result = run(["-c", PROBE])
    evidence = json.loads(result.stdout)
    if product:
        installed = run(
            [
                "-c",
                "import importlib.metadata as m, json; "
                "from cadrumo.core.config import configured_authority_root; "
                "from cadrumo.domain.calculations.registry.authority_store import require_authority_store_available; "
                "p=configured_authority_root(); require_authority_store_available(p/'authority.current.json'); "
                "print(json.dumps({n:m.version(n) for n in "
                "['cadrumo','cadrumo-data-manuals','cadrumo-data-official']}))",
            ]
        )
        versions = json.loads(installed.stdout)
        if len(set(versions.values())) != 1:
            raise AssertionError("Product cohort version mismatch")
        evidence["product_versions"] = versions
        cli = run(
            [
                "-c",
                "from cadrumo.entrypoints.cli.bootstrap import main; import sys; sys.argv=['aeat','--version']; main()",
            ]
        )
        evidence["cli_version"] = cli.stdout.strip()
    run(["-m", "json.tool", "--help"])
    script = cwd / "explicit script.py"
    script.write_text("import pikepdf; print('script passed')", encoding="utf-8")
    run([str(script)])
    injected = destination / layout["paths"]["packages"] / "hostile.pth"
    injected.write_text("import sys; raise RuntimeError('executable pth ran')", encoding="utf-8")
    try:
        run(["-c", "import pikepdf"])
    finally:
        injected.unlink()
    refused = []
    runtime_relative = f"{layout['paths']['native']}/{layout['files']['runtime']}"
    for relative in (runtime_relative, layout["paths"]["stdlib"]):
        original = destination / relative
        held = original.with_name(original.name + ".held")
        original.rename(held)
        try:
            failure = run(["-c", "print('must refuse')"], success=False)
            refused.append({"missing": relative, "exit": failure.returncode, "stderr": failure.stderr})
        finally:
            held.rename(original)
    native_map = json.loads((destination / "data/native-modules.json").read_text(encoding="utf-8"))
    extension = destination / native_map["modules"]["pikepdf._core"]
    held = extension.with_name(extension.name + ".held")
    extension.rename(held)
    try:
        failure = run(["-c", "import pikepdf"], success=False)
        refused.append({"missing": str(extension.relative_to(destination)), "stderr": failure.stderr})
    finally:
        held.rename(extension)
    runtime = destination / runtime_relative
    held = runtime.with_name(runtime.name + ".held")
    runtime.rename(held)
    try:
        runtime.write_bytes(b"incompatible PE image")
        failure = run(["-c", "print('must refuse')"], success=False)
        refused.append({"incompatible": "CPython PE image", "exit": failure.returncode, "stderr": failure.stderr})
    finally:
        runtime.unlink()
        held.rename(runtime)
    qpdf = list((destination / layout["paths"]["native"] / "packages/pikepdf.libs").glob("*qpdf*.dll"))
    if not qpdf:
        raise AssertionError("No qpdf transitive dependency found")
    dependency = qpdf[0]
    hostile = cwd / dependency.name
    hostile.write_bytes(b"hostile native dependency")
    run(["-c", "import pikepdf; pikepdf.Pdf.new()"])
    held = dependency.with_name(dependency.name + ".held")
    dependency.rename(held)
    try:
        failure = run(["-c", "import pikepdf"], success=False)
        refused.append({"missing_transitive": dependency.name, "exit": failure.returncode})
    finally:
        held.rename(dependency)
    after = {p.relative_to(destination).as_posix(): digest(p) for p in destination.rglob("*") if p.is_file()}
    if before != after:
        raise AssertionError("Interpreter modified its installed package")
    if not storage_root.is_dir() or not temporary_root.is_dir() or not cache_root.is_dir():
        raise AssertionError("Native bootstrap did not prepare the configured storage overrides")
    evidence.update(
        {
            "refusals": refused,
            "package_unchanged": True,
            "write_trace_scope": "Python audit events; native/OS writes require process tracing",
        }
    )
    output = build_root / "verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Verified {destination}; evidence: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--product", action="store_true")
    arguments = parser.parse_args()
    verify(arguments.package, arguments.destination, product=arguments.product)
