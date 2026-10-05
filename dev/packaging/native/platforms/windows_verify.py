"""Exercise an assembled interpreter outside the source checkout."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cadrumo.core.storage_environment import storage_directory

from ...command_execution import CommandResult, run_command
from ..hashing import digest
from ..layout import application_images, entrypoint_files, staged_application_images
from ..package_inventory import user_docs_bundled
from ..verification_paths import verification_destination

PROBE = r"""
import importlib, json, os, pathlib, subprocess, sys, tempfile
root = pathlib.Path(sys.executable).parent.resolve()
assert sys.flags.isolated and sys.flags.no_site and sys.flags.no_user_site
assert sys.flags.safe_path and sys.dont_write_bytecode
assert all(pathlib.Path(p).resolve().is_relative_to(root) for p in sys.path)
assert 'PYTHONHOME' not in os.environ and 'PYTHONPATH' not in os.environ
assert 'VIRTUAL_ENV' not in os.environ
windows_version = sys.getwindowsversion()
assert windows_version.major >= 10, 'packaged host does not expose the supported Windows version'
windows_version_observation = {
    'reported': [windows_version.major, windows_version.minor, windows_version.build],
    'platform_version': list(windows_version.platform_version),
    'minimum_supported_major': 10,
}
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
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location
generated_cache = (user / storage_location(StorageCategory.PYWIN32_GENERATED_CACHE).relative_path()).resolve()
assert pathlib.Path(win32com.__gen_path__).resolve() == generated_cache
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
                  'child': json.loads(child), 'windows_version': windows_version_observation,
                  'python_audit_writes': writes, 'user_root': str(user),
                  'temporary_root': str(temporary_root), 'pywin32_generated_cache': str(generated_cache)}))
"""

KDF_READY_PROBE = r"""
import json, time
from pathlib import Path
from cadrumo.adapters.persistence.storage.custody import _kdf_process
from cadrumo.adapters.persistence.storage.custody._kdf_worker_supervision import _SupervisedKdfWorker

# No request (and therefore no password) is sent: enter proves the genuine ready
# frame, neutral cwd, exact environment and assigned Windows Job before cleanup.
with _SupervisedKdfWorker(deadline=time.monotonic() + 30) as worker:
    payload = worker._ready_payload
    neutral = worker._neutral_directory
    assert payload is not None and neutral is not None
    expected = sorted(_kdf_process.worker_environment(neutral_root=Path(neutral.name)))
    assert payload['environment_keys'] == expected
    process = worker._process
    assert process is not None
assert process.poll() is not None
assert not Path(neutral.name).exists()

# This extra option is valid to the real worker parser on Windows, but is not
# part of its parent's fixed invocation. It must keep ordinary host projection
# and fail the unchanged attestation instead of acquiring the exception.
original = _kdf_process.worker_command
original_launch = _kdf_process._launch_worker_process
launched = []
neutral_directories = []
def record_launch(command, options):
    process = original_launch(command, options)
    launched.append(process)
    return process
def extended_command(**kwargs):
    command, options = original(**kwargs)
    neutral_directories.append(Path(options['cwd']))
    return [*command, '--descriptor-bound', '16'], options
_kdf_process.worker_command = extended_command
_kdf_process._launch_worker_process = record_launch
try:
    with _SupervisedKdfWorker(deadline=time.monotonic() + 30):
        raise AssertionError('noncanonical invocation passed KDF readiness')
except ValueError as error:
    assert str(error) == 'profile KDF worker environment is not allowlisted'
else:
    raise AssertionError('noncanonical invocation was not refused')
finally:
    _kdf_process.worker_command = original
    _kdf_process._launch_worker_process = original_launch
assert len(launched) == 1 and launched[0].poll() is not None
assert len(neutral_directories) == 1 and not neutral_directories[0].exists()
print(json.dumps({'ready_environment_keys': expected, 'worker_joined': True,
                  'neutral_directory_removed': True, 'noncanonical_invocation_refused': True,
                  'refused_worker_joined': True,
                  'password_or_request_sent': False}))
"""


RUNTIME_PROBE = r"""
import json, os, sys, time
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError

runtime = Path(sys.argv[1]).resolve(strict=True)
storage_root = Path(os.environ['CADRUMO_LOCAL_STORAGE_ROOT']).resolve(strict=True)
product = version('cadrumo')
with ExitStack() as cleanup:
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    cleanup.callback(endpoint.close)
    scope = WindowsProcessScope()
    cleanup.callback(scope.terminate, timeout=5)
    runtime_installation(storage_root=storage_root, os_owner_id=endpoint.os_owner_id,
                         storage_identity=endpoint.storage_identity)
    # Hostile interpreter variables must not reach the runtime's own isolated host.
    environment = dict(os.environ, PYTHONPATH=os.getcwd(), PYTHONHOME=os.getcwd())
    process = scope.launch(executable=runtime, directory=storage_root, environment=environment, arguments=(
        '--storage-root', str(storage_root), '--storage-identity', endpoint.storage_identity,
        '--expected-version', product))
    expected = RuntimeClientHello(product_version=product, storage_identity=endpoint.storage_identity)
    deadline = time.monotonic() + 60
    while True:
        try:
            channel = endpoint.connect(timeout=0.2, expected_image=runtime)
            connection = VerifiedRuntimeConnection(channel, expected=expected, deadline=deadline)
            break
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.ENDPOINT_NOT_READY or time.monotonic() >= deadline:
                raise
            try:
                code = process.wait(timeout=0)
            except RuntimeRefusalError:
                time.sleep(0.05)
            else:
                raise AssertionError(f'runtime exited before serving its endpoint: {code}') from error
    image = str(channel.image_path)
    connection.close()
print(json.dumps({'runtime_image': image, 'handshake': 'verified', 'product_version': product}))
"""


def verify_entrypoints(
    destination: Path,
    layout: dict[str, Any],
    cwd: Path,
    environment: dict[str, str],
    run: Callable[[list[str]], CommandResult],
) -> dict[str, Any]:
    """Prove each console entrypoint equals its console script run by the interpreter, then serve the runtime."""
    observed: dict[str, Any] = {}
    interpreter = destination / layout["paths"]["executable"]
    files = entrypoint_files(layout)
    for name, relative in files.items():
        executable = destination / relative
        script = ["-c", f"import _cadrumo_bootstrap; _cadrumo_bootstrap.run_entrypoint({name!r})"]
        exits = {}
        for label, arguments in (("help", ["--help"]), ("unrecognized_option", ["--unrecognized-option"])):
            native = run_command([str(executable), *arguments], cwd=cwd, environment=environment, timeout_seconds=90)
            reference = run_command(
                [str(interpreter), *script, *arguments], cwd=cwd, environment=environment, timeout_seconds=90
            )
            if (native.returncode, native.stdout) != (reference.returncode, reference.stdout):
                raise AssertionError(f"Entrypoint {name} differs from its console script for {label}: {native.stderr}")
            exits[label] = native.returncode
        if exits["help"] != 0 or exits["unrecognized_option"] == 0:
            raise AssertionError(f"Entrypoint {name} did not forward its arguments: {exits}")
        # A declared entrypoint outside the native directory cannot locate its package root.
        displaced = destination / executable.name
        shutil.copy2(executable, displaced)
        try:
            outside = run_command([str(displaced), "--help"], cwd=cwd, environment=environment, timeout_seconds=90)
        finally:
            displaced.unlink()
        if outside.returncode == 0 or "must reside in the package" not in outside.stderr:
            raise AssertionError(f"Displaced entrypoint {name} was not refused: exit {outside.returncode}")
        observed[name] = {
            "location": relative,
            "matches_console_script": True,
            "help_exit": exits["help"],
            "argument_refusal_exit": exits["unrecognized_option"],
            "displaced_refusal_exit": outside.returncode,
        }
    runtime = (destination / files["cadrumo-runtime"]).resolve(strict=True)
    served = json.loads(run(["-c", RUNTIME_PROBE, str(runtime)]).stdout)
    if Path(served["runtime_image"]) != runtime:
        raise AssertionError(f"Runtime endpoint was served by another image: {served['runtime_image']}")
    observed["cadrumo-runtime"]["served"] = served
    return observed


def verify_application_images(
    destination: Path, manifest: dict[str, Any], execute: Callable[[list[str]], CommandResult]
) -> dict[str, Any]:
    """Prove each staged application image is hashed, opts into startup as declared and reports the version."""
    layout, files = manifest["layout"], manifest["files"]
    staged = staged_application_images(layout, user_docs=user_docs_bundled(manifest))
    version = str(manifest["build"]["version"])
    observed: dict[str, Any] = {}
    for image in application_images(layout):
        path = destination / image.package_path
        if image not in staged:
            if path.exists() or image.package_path in files:
                raise AssertionError(f"Application image {image.file} ships in a package that may not stage it")
            observed[image.file] = {"staged": False}
            continue
        if not path.is_file() or files.get(image.package_path) != digest(path):
            raise AssertionError(f"Application image {image.file} is missing or absent from the package manifest")
        if (image.package_path in manifest["startup_files"]) != image.startup:
            raise AssertionError(f"Application image {image.file} startup membership differs from its declaration")
        result = execute([str(path), *image.version_arguments])
        if result.returncode or not re.search(rf"(?<![\w.]){re.escape(version)}(?![\w.])", result.stdout):
            raise AssertionError(
                f"Application image {image.file} did not report version {version}: exit {result.returncode}, "
                f"{result.stdout!r} {result.stderr!r}"
            )
        observed[image.file] = {
            "staged": True,
            "location": image.package_path,
            "sha256": files[image.package_path],
            "startup_file": image.startup,
            "version_arguments": list(image.version_arguments),
            "version_output": result.stdout.strip(),
        }
    return observed


def verify(
    package: Path, destination: Path | None = None, *, product: bool = False, build_root: Path | None = None
) -> None:
    """Copy and verify an artifact in a fresh isolated staging directory."""
    package = package.resolve(strict=True)
    manifest = json.loads((package / "data/package-manifest.json").read_text(encoding="utf-8"))
    layout = manifest["layout"]
    build_root = build_root or storage_directory("CADRUMO_NATIVE_BUILD_ROOT", "development/build/native")
    build_root = build_root.resolve()
    build_root.mkdir(parents=True, exist_ok=True)
    destination = verification_destination(destination, build_root)
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
            # Neither the former tool-cache override nor an ambient XDG cache may place packaged state.
            "CADRUMO_TOOL_CACHE_DIR": str(cwd / "hostile-tool-cache"),
            "XDG_CACHE_HOME": str(cwd / "hostile-xdg-cache"),
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
        kdf_ready = run(["-c", KDF_READY_PROBE])
        evidence["kdf_pre_secret_readiness"] = json.loads(kdf_ready.stdout)
        evidence["entrypoints"] = verify_entrypoints(destination, layout, cwd, environment, run)
        evidence["application_images"] = verify_application_images(
            destination,
            manifest,
            lambda argv: run_command(argv, cwd=cwd, environment=environment, timeout_seconds=90),
        )
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
    if not storage_root.is_dir() or not temporary_root.is_dir():
        raise AssertionError("Native bootstrap did not prepare the configured storage overrides")
    if (cwd / "hostile-tool-cache").exists() or (cwd / "hostile-xdg-cache").exists():
        raise AssertionError("Packaged processes wrote to a development or ambient cache location")
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
