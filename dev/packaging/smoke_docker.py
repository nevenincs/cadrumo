"""Run Cadrumo packaging smoke checks inside a fresh Linux Docker image."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import iter_directory

from .._paths import REPO_ROOT, UTF_8
from ._base_image import linux_base_image
from ._proof_ledger import record_proof
from ._smoke_common import relative_manifest_path, require_executable, write_smoke_manifest
from .python_cohort import load_python_cohort

_UTF_8: Final[str] = UTF_8
_DOCKER_COMMAND_TIMEOUT_SECONDS: Final[int] = 30


@dataclass(frozen=True)
class DockerCli:
    """Docker command backend and path translation context."""

    argv_prefix: tuple[str, ...]
    label: str
    wsl_distro: str | None = None


def _repo_root() -> Path:
    """Return the repository root for this module."""
    return REPO_ROOT


def _work_dir(repo_root: Path, requested: str | None, mode: str) -> Path:
    """Resolve a new Docker packaging smoke work directory."""
    if requested is not None:
        path = Path(requested).resolve()
        if path.exists() and any(iter_directory(path)):
            raise SystemExit(f"--work-dir must be empty or absent: {path}")
        path.mkdir(parents=True, exist_ok=True)
        return path
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = repo_root / "var" / "packaging-smoke" / f"docker-{mode}-{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_probe(work_dir: Path, filename: str, source: str) -> Path:
    """Write a container probe script into the mounted work directory."""
    path = work_dir / filename
    path.write_text(textwrap.dedent(source).lstrip(), encoding=_UTF_8, newline="\n")
    return path


def _docker_mount(path: Path) -> str:
    """Return a Docker CLI mount path string for the host platform."""
    resolved = str(path.resolve())
    if os.name == "nt":
        return resolved.replace("\\", "/")
    return resolved


def _wsl_mount(docker: DockerCli, path: Path) -> str:
    """Return a WSL-visible path for a Windows host path."""
    if docker.wsl_distro is None or os.name != "nt":
        return _docker_mount(path)
    wsl = docker.argv_prefix[0]
    windows_path = str(path.resolve()).replace("\\", "/")
    result = subprocess.run(
        [wsl, "-d", docker.wsl_distro, "--", "wslpath", "-a", windows_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    return result.stdout.strip()


def _docker_version_command(docker: DockerCli) -> list[str]:
    """Return the Docker daemon version probe command."""
    return [*docker.argv_prefix, "version", "--format", "{{.Server.Version}}"]


def _command_succeeds(command: list[str], *, timeout: int = _DOCKER_COMMAND_TIMEOUT_SECONDS) -> bool:
    """Return whether a real command exits successfully within ``timeout``."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _wsl_docker_cli_available(wsl: str, distro: str) -> bool:
    """Return whether ``distro`` exposes a Docker CLI, without probing its daemon."""
    return _command_succeeds([wsl, "-d", distro, "--", "docker", "--version"])


def _docker_cli() -> DockerCli:
    """Resolve the Docker CLI backend, preferring native WSL Docker on Windows."""
    if os.name == "nt":
        wsl = shutil.which("wsl")
        distro = os.environ.get("CADRUMO_WSL_DOCKER_DISTRO", "Ubuntu")
        if wsl is not None and _wsl_docker_cli_available(wsl, distro):
            return DockerCli((wsl, "-d", distro, "--", "docker"), f"wsl:{distro}", distro)
        docker = require_executable("docker")
        return DockerCli((docker,), "windows")
    return DockerCli((require_executable("docker"),), "native")


def _preflight_docker(docker: DockerCli) -> None:
    """Fail quickly when Docker is installed but the daemon is not answering."""
    command = _docker_version_command(docker)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=_DOCKER_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        raise SystemExit(
            f"docker daemon did not answer within {_DOCKER_COMMAND_TIMEOUT_SECONDS} seconds via {docker.label}"
        ) from exc
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)
    record_proof("docker daemon preflight")


def _run_docker(command: list[str], *, timeout: int) -> None:
    """Run Docker and replay captured logs only when the probe fails."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        sys.stderr.write(f"docker packaging smoke timed out after {timeout} seconds\n")
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        raise SystemExit(124) from exc
    if result.returncode != 0:
        sys.stderr.write(f"docker packaging smoke failed with exit code {result.returncode}\n")
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        raise SystemExit(result.returncode or 1)


def _core_probe_source() -> str:
    """Return the Python probe executed inside the core container."""
    return r"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

REPRESENTATIVE_DATA_LEAVES = (
    "registry/aeat/modelos/036/manifest.toml",
    "registry/cadrumo/user_profile/schema.toml",
    "corpus/aeat_official/disenos_registro/modelo_100/manifest.json",
)


def run(argv: list[str], *, expected: tuple[int, ...] = (0,), env: dict[str, str] | None = None):
    result = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)
    if result.returncode not in expected:
        print(f"command failed ({result.returncode}): {' '.join(argv)}", file=sys.stderr)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode or 1)
    return result


def json_payload(output: str) -> dict[str, object]:
    start = output.find("{")
    if start < 0:
        raise SystemExit(f"command did not emit a JSON envelope: {output!r}")
    payload = json.loads(output[start:])
    if not isinstance(payload, dict):
        raise SystemExit(f"command JSON envelope was not an object: {payload!r}")
    return payload


def clean_product_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}


wheel = Path(sys.argv[1])
companions = [Path(value) for value in sys.argv[2:4]]
run([
    sys.executable,
    "-m",
    "pip",
    "install",
    "--disable-pip-version-check",
    "--no-cache-dir",
    str(wheel),
    *(str(companion) for companion in companions),
])
run([sys.executable, "-m", "pip", "check"])

from importlib.metadata import distribution
for name, artifact in zip(
    ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"),
    (wheel, *companions),
    strict=True,
):
    direct_url = json.loads(distribution(name).read_text("direct_url.json") or "null")
    if direct_url.get("url") != artifact.as_uri():
        raise SystemExit(f"{name} installed from unrelated bytes: {direct_url!r}")

version = run(["aeat", "--version"], env=clean_product_env())
if "CADRUMO " not in version.stdout:
    raise SystemExit(f"unexpected aeat --version output: {version.stdout!r}")

root = files("cadrumo").joinpath("_data")
missing = []
for rel in REPRESENTATIVE_DATA_LEAVES:
    if not root.joinpath(*rel.split("/")).is_file():
        missing.append(rel)
if missing:
    raise SystemExit(f"missing installed bundled data leaves: {missing!r}")

default_root = Path("/work/default-check-state")
default_env = {
    **clean_product_env(),
    "CADRUMO_LOCAL_STORAGE_ROOT": str(default_root),
    "CADRUMO_DATABASE_URL": f"sqlite:///{(default_root / 'cadrumo.db').as_posix()}",
}
default_check = run(["aeat", "--format", "json", "config", "check"], expected=(1, 2), env=default_env)
default_payload = json_payload(default_check.stdout)
if default_payload.get("status") != "success" or default_payload.get("result", {}).get("ok") is not False:
    raise SystemExit(f"default config check did not report typed dependency diagnostics: {default_payload!r}")

storage_root = Path("/work/profile-root")
storage_root.mkdir(parents=True, exist_ok=True)
env = {
    **clean_product_env(),
    "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
    "CADRUMO_OUTPUT_LANGUAGE": "en",
    "CADRUMO_SECRET_PASSPHRASE": secrets.token_urlsafe(24),
    # Headless custody: no keyring exists in the container; pin the
    # passphrase-backed file backend like every other smoke lane.
    "CADRUMO_SECRET_STORE_BACKEND": "unsecured",
}
create = run(
    [
        "aeat",
        "--format",
        "json",
        "config",
        "profile",
        "create",
        "packaging-smoke",
        "--entity-type",
        "natural_person",
        "--tax-id",
        "00000000T",
        "--name",
        "Packaging",
        "--surnames",
        "Smoke",
        "--tax-residence-ccaa",
        "madrid",
        "--irpf-income-categories",
        "actividad_economica",
        "--quiet",
        "--accept-defaults",
        "--no-llm-vision",
        "--no-google-export",
    ],
    env=env,
)
create_payload = json_payload(create.stdout)
if create_payload.get("status") != "success":
    raise SystemExit(f"profile create did not succeed: {create_payload!r}")

ready = run(["aeat", "--format", "json", "config", "check"], env=env)
ready_payload = json_payload(ready.stdout)
result = ready_payload.get("result", {})
if ready_payload.get("status") != "success" or result.get("ok") is not True or result.get("issues") != []:
    raise SystemExit(f"opted-out config check did not pass cleanly: {ready_payload!r}")

attachment_probe = r'''
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from cadrumo.adapters.outbound.llm._client import LLMClient
from cadrumo.adapters.outbound.llm.errors import LLMConfigError
from cadrumo.adapters.outbound.llm._models import LLMProvider
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.master_key.active_session import activate_session
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.sql import SecureObjectRepository, dispose_engine, get_engine
from cadrumo.core.config import Settings
from cadrumo.domain.attachments import (
    AttachmentBytesContent,
    AttachmentIngestionRequest,
    AttachmentKind,
    AttachmentSource,
    add_attachment,
    list_attachments,
    load_attachment,
)

root = Path("/work/runtime-surfaces")
root.mkdir(parents=True, exist_ok=True)
settings = Settings(
    cadrumo_database_url=f"sqlite:///{(root / 'attachments.db').as_posix()}",
    cadrumo_local_storage_root=root / "state",
)
session = BucketSession.open(
    bucket_id="packaging-smoke",
    kek=os.urandom(32),
    dek=os.urandom(32),
    idle_minutes=15,
    opened_at=datetime.now(UTC).replace(microsecond=0),
    unsecured_backend=True,
)
payload = b"%PDF-1.4\n%cadrumo-packaging-attachment-smoke\n"
try:
    engine = get_engine(settings)
    with activate_session(session):
        store = AttachmentStore(objects=SecureObjectRepository(engine=engine))
        attachment = add_attachment(
            store,
            content=AttachmentBytesContent(data=payload),
            request=AttachmentIngestionRequest(
                kind=AttachmentKind.INVOICE_PDF,
                source=AttachmentSource.LOCAL_FILE,
                source_reference="packaging-smoke.pdf",
                mime_type="application/pdf",
                captured_at=datetime.now(UTC).replace(microsecond=0),
                bucket_id="packaging-smoke",
                link_transaction_ids=("tx-packaging-smoke",),
            ),
        )
        expected = hashlib.sha256(payload).hexdigest()
        if attachment.attachment_id != expected:
            raise SystemExit(f"attachment digest mismatch: {attachment.attachment_id} != {expected}")
        if store.read_bytes(attachment.attachment_id) != payload:
            raise SystemExit("attachment bytes did not round-trip")
        loaded = load_attachment(store, attachment.attachment_id)
        if loaded.attachment_id != attachment.attachment_id:
            raise SystemExit("attachment manifest did not round-trip")
        listed = tuple(list_attachments(store))
        if [item.attachment_id for item in listed] != [attachment.attachment_id]:
            raise SystemExit(f"unexpected attachment listing: {listed!r}")
finally:
    session.close()
    dispose_engine(settings)

try:
    LLMClient(settings=Settings(cadrumo_local_storage_root=root / "llm-state"))._build_adapter(LLMProvider.ANTHROPIC)
except LLMConfigError as exc:
    if exc.suggestion != "pip install cadrumo[anthropic]":
        raise SystemExit(f"unexpected Anthropic install hint: {exc.suggestion!r}")
else:
    raise SystemExit("Anthropic adapter unexpectedly built in a core wheel install")
'''
run([sys.executable, "-c", attachment_probe], env=env)

print("docker-core-ok")
"""


def _browser_probe_source() -> str:
    """Return the Python probe executed inside the browser-extra container."""
    return r"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


def run(argv: list[str], *, env: dict[str, str] | None = None):
    result = subprocess.run(argv, capture_output=True, text=True, check=False, env=env)
    if result.returncode != 0:
        print(f"command failed ({result.returncode}): {' '.join(argv)}", file=sys.stderr)
        print(result.stdout, end="")
        print(result.stderr, end="", file=sys.stderr)
        raise SystemExit(result.returncode or 1)
    return result


def clean_product_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("CADRUMO_")}


wheel = Path(sys.argv[1])
companions = [Path(value) for value in sys.argv[2:4]]
env = {
    **clean_product_env(),
    "CADRUMO_BROWSER_CHANNEL": "chromium",
    "CADRUMO_BROWSER_HEADLESS": "true",
    "CADRUMO_LOCAL_STORAGE_ROOT": "/work/profile-root",
    "CADRUMO_DATABASE_URL": "sqlite:////work/profile-root/cadrumo.db",
    "CADRUMO_OUTPUT_LANGUAGE": "en",
    "PLAYWRIGHT_BROWSERS_PATH": "/work/playwright-browsers",
}
os.environ.clear()
os.environ.update(env)
Path(env["CADRUMO_LOCAL_STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True)
Path(env["PLAYWRIGHT_BROWSERS_PATH"]).mkdir(parents=True, exist_ok=True)

target = f"cadrumo[browser] @ {wheel.as_uri()}"
run([
    sys.executable,
    "-m",
    "pip",
    "install",
    "--disable-pip-version-check",
    "--no-cache-dir",
    target,
    *(str(companion) for companion in companions),
], env=env)
run([sys.executable, "-m", "pip", "check"], env=env)
from importlib.metadata import distribution
for name, artifact in zip(
    ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"),
    (wheel, *companions),
    strict=True,
):
    direct_url = json.loads(distribution(name).read_text("direct_url.json") or "null")
    if direct_url.get("url") != artifact.as_uri():
        raise SystemExit(f"{name} installed from unrelated bytes: {direct_url!r}")
run([sys.executable, "-c", "import playwright.async_api, playwright_stealth"], env=env)
run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"], env=env)

from cadrumo.adapters.outbound.aeat.browser import default_browser_session_factory
from cadrumo.core.config import load_settings
from ._proof_ledger import record_proof


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><title>AEAT packaging smoke</title><h1>ok</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
thread = Thread(target=server.serve_forever, daemon=True)
thread.start()


async def main():
    settings = load_settings()
    if settings.cadrumo_browser_channel != "chromium" or settings.cadrumo_browser_headless is not True:
        raise SystemExit(
            "docker browser smoke did not resolve canonical Chromium/headless settings: "
            f"channel={settings.cadrumo_browser_channel!r} headless={settings.cadrumo_browser_headless!r}"
        )
    browser_session = await default_browser_session_factory(settings)
    try:
        context = await browser_session.create_context()
        try:
            page = await context.new_page()
            response = await browser_session.navigate(page, f"http://127.0.0.1:{server.server_port}/")
            if not response or not response.ok:
                status = response.status if response else "none"
                raise SystemExit(f"unexpected browser health response: {status}")
            title = await page.title()
            if title != "AEAT packaging smoke":
                raise SystemExit(f"unexpected browser health title: {title!r}")
        finally:
            await context.close()
    finally:
        await browser_session.close()
        server.shutdown()
        server.server_close()


asyncio.run(main())
print("docker-browser-ok")
"""


def _run_probe(
    *,
    docker: DockerCli,
    image: str,
    work_dir: Path,
    cohort_dir: Path,
    wheel: Path,
    companion_wheels: tuple[Path, Path],
    probe: Path,
    timeout: int,
) -> None:
    """Run one probe script in the requested Docker image.

    The probe inputs are COPIED into the container (``docker create`` +
    ``docker cp`` + ``docker start --attach``) rather than bind-mounted. A bind
    mount resolves against the DAEMON host's filesystem, so when this smoke
    itself executes inside a containerized runner (the self-hosted fleet's
    Linux runner is a container speaking to Docker Desktop's daemon) the
    daemon cannot see the runner's paths and silently mounts empty
    directories. Copying works identically for native daemons and
    docker-outside-of-docker runners.
    """
    create_command = [
        *docker.argv_prefix,
        "create",
        "--workdir",
        "/work",
        image,
        "python",
        f"/work/{probe.name}",
        f"/cohort/{wheel.name}",
        *(f"/cohort/{companion.name}" for companion in companion_wheels),
    ]
    created = subprocess.run(create_command, capture_output=True, text=True, check=False, timeout=timeout)
    if created.returncode != 0:
        sys.stderr.write(f"docker packaging smoke failed to create the probe container ({created.returncode})\n")
        sys.stdout.write(created.stdout)
        sys.stderr.write(created.stderr)
        raise SystemExit(created.returncode or 1)
    container_id = created.stdout.strip()
    try:
        # docker cp semantics differ by destination existence: `--workdir`
        # pre-creates /work, so the `SRC/.` contents form targets it (a plain
        # SRC_DIR would nest as /work/<basename>); /cohort does not exist yet,
        # so the plain SRC_DIR form creates it with the source's contents.
        _run_docker(
            [*docker.argv_prefix, "cp", f"{_wsl_mount(docker, work_dir)}/.", f"{container_id}:/work"],
            timeout=timeout,
        )
        _run_docker(
            [*docker.argv_prefix, "cp", _wsl_mount(docker, cohort_dir), f"{container_id}:/cohort"],
            timeout=timeout,
        )
        print("running Docker packaging smoke", flush=True)
        _run_docker([*docker.argv_prefix, "start", "--attach", container_id], timeout=timeout)
    finally:
        subprocess.run(
            [*docker.argv_prefix, "rm", "--force", container_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=_DOCKER_COMMAND_TIMEOUT_SECONDS,
        )
    record_proof("clean Linux container install")
    record_proof("container pip check")


def main(argv: list[str] | None = None) -> int:
    """Build the wheel and verify it from a clean Linux Docker image."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--image",
        default=linux_base_image(),
        help=(
            "Docker image used for the clean Linux proof. Defaults to the "
            "`ARG PYTHON_BASE_IMAGE` declared in the repository-root Dockerfile, "
            "so this proof and the devcontainer image share one base by construction."
        ),
    )
    parser.add_argument("--work-dir", help="Empty directory for wheel and Docker smoke artifacts.")
    parser.add_argument(
        "--cohort-dir",
        required=True,
        type=Path,
        help="Directory containing the prebuilt immutable Python cohort.",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Install cadrumo[browser], provision Chromium with system deps, and run browser health.",
    )
    parser.add_argument("--timeout", type=int, help="Docker probe timeout in seconds.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    docker = _docker_cli()
    mode = "browser" if args.browser else "core"
    timeout = args.timeout if args.timeout is not None else (1800 if args.browser else 900)

    print(f"preflighting Docker daemon ({docker.label})", flush=True)
    _preflight_docker(docker)

    work_dir = _work_dir(repo_root, args.work_dir, mode)
    print(f"Docker packaging smoke work dir: {work_dir}", flush=True)

    cohort = load_python_cohort(args.cohort_dir)
    wheel = cohort.root_wheel
    print("using supplied immutable Python cohort", flush=True)
    probe = _write_probe(
        work_dir,
        f"{mode}_probe.py",
        _browser_probe_source() if args.browser else _core_probe_source(),
    )

    _run_probe(
        docker=docker,
        image=args.image,
        work_dir=work_dir,
        cohort_dir=cohort.directory,
        wheel=wheel,
        companion_wheels=cohort.companion_wheels,
        probe=probe,
        timeout=timeout,
    )

    # The probe above runs the variant's checks INSIDE the container and exits
    # non-zero on any failure, so reaching here is the proof that they passed.
    # Recording per variant keeps the claim tied to the probe that ran it.
    variant_claims = (
        (
            "browser optional imports",
            "Playwright Chromium with system dependencies",
            "container localhost browser health smoke",
        )
        if args.browser
        else (
            "installed CLI config/profile smoke",
            "attachment storage round-trip",
            "core LLM missing-extra boundary",
        )
    )
    for claim in variant_claims:
        record_proof(claim)

    declared = [
        "docker daemon preflight",
        "installed bundled data resources",
        "clean Linux container install",
        "container pip check",
        *variant_claims,
    ]
    manifest = write_smoke_manifest(
        work_dir,
        lane=f"docker-{mode}",
        artifacts={
            "wheel": relative_manifest_path(work_dir, wheel),
            "data_wheel_manuals": relative_manifest_path(work_dir, cohort.manuals_wheel),
            "data_wheel_official": relative_manifest_path(work_dir, cohort.official_wheel),
            "probe": relative_manifest_path(work_dir, probe),
        },
        declared=tuple(declared),
        details={
            "docker_backend": docker.label,
            "cohort_version": cohort.version,
            "image": args.image,
            "mode": mode,
            "timeout_seconds": timeout,
        },
    )

    print(f"Docker {mode} packaging smoke passed: {wheel}", flush=True)
    print(f"packaging smoke manifest: {manifest}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
