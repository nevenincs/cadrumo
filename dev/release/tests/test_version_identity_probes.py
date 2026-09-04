"""Proof that the probes read the answer they got rather than assuming one.

The decision core is pure and every rule above it is proved against real
observations. The shell that GATHERS those observations had no case in either
direction, and it carries the most security-relevant rule in the module: a 404
is the only answer that means "free". Everything else -- a 500, a refused
connection, a name that does not resolve -- proves nothing about availability,
and reading it as absence is how a guard permits the one collision that cannot
be undone. Inverting the single comparison that expresses this would turn
nothing red.

The index answers here come from a real HTTP origin on loopback, because the
subject is the STATUS CODE and a status has to be held still to be asserted
against. Nothing stands in for `urllib`, the socket, or the response: the
probe builds its own request, opens its own connection, and reaches its own
branch. The live companion module asks the same probe the same questions
against the real index, which is what keeps this file from proving only that
loopback works.

The ledger case at the end is the CLI's, not a probe's: the seal's one
remaining rule reads a file that can be malformed, and an operator meets that
as the whole output of the run.
"""

from __future__ import annotations

import http.server
import shutil
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT, UTF_8
from ..version_identity import PYPI_PROJECTS, VersionIdentityError, pypi_projects_owning

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Comfortably above anything shipped, so nothing but the served status decides.
_CANDIDATE: str = "9.9.9"

#: The discard port: nothing listens, so a connection is refused immediately.
_CLOSED_INDEX: str = "http://127.0.0.1:9/pypi"


@contextmanager
def _index_answering(status: int) -> Iterator[str]:
    """Serve ``status`` from loopback and yield the index base URL for it."""

    class _FixedStatus(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - the stdlib's own hook name.
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - the stdlib's own parameter name.
            """Stay silent: the subject of these cases is the client."""

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FixedStatus)
    serving = threading.Thread(target=server.serve_forever, daemon=True)
    serving.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/pypi"
    finally:
        server.shutdown()
        server.server_close()
        serving.join(timeout=10)


def test_a_404_is_read_as_free() -> None:
    """The permit direction, without which the guard refuses every release."""
    with _index_answering(404) as index_url:
        assert pypi_projects_owning(_CANDIDATE, index_url=index_url) == ()


def test_an_answer_that_is_not_404_is_read_as_carried() -> None:
    """The refusal direction of the same comparison.

    Asserted from the same shell as the case above, so the one branch that
    separates them cannot be inverted with both still passing.
    """
    with _index_answering(200) as index_url:
        assert pypi_projects_owning(_CANDIDATE, index_url=index_url) == PYPI_PROJECTS


@pytest.mark.parametrize("status", [403, 429, 500, 503])
def test_an_index_that_cannot_answer_refuses_rather_than_reading_as_absence(status: int) -> None:
    """An index that failed to answer has not said the version is free.

    This is the whole reason the probe raises instead of returning: a guard
    that treats a failed lookup as a clean one permits the upload it exists to
    refuse, and says nothing while doing it.
    """
    with _index_answering(status) as index_url, pytest.raises(VersionIdentityError, match="index check failed"):
        pypi_projects_owning(_CANDIDATE, projects=["cadrumo"], index_url=index_url)


def test_an_unreachable_index_refuses() -> None:
    """A transport failure is not an answer either, and never means free."""
    with pytest.raises(VersionIdentityError, match="index check failed"):
        pypi_projects_owning(_CANDIDATE, projects=["cadrumo"], index_url=_CLOSED_INDEX)


def test_the_first_project_that_cannot_be_checked_stops_the_whole_cohort() -> None:
    """A cohort answer needs every project, so a partial sweep is not one."""
    with pytest.raises(VersionIdentityError, match="cadrumo"):
        pypi_projects_owning(_CANDIDATE, index_url=_CLOSED_INDEX)


def test_a_malformed_ledger_refuses_with_a_message_rather_than_a_traceback(tmp_path: Path) -> None:
    """The seal's only remaining rule reads a file, and files can be broken.

    The ledger raises its own error type, so a shell catching only the identity
    error meets it as a traceback -- on the one gate whose entire output is
    that line. Run as a real invocation over a real malformed ledger, from a
    copy of the package, so nothing in the shipped tree is disturbed.
    """
    package = tmp_path / "dev" / "release"
    package.mkdir(parents=True)
    for name in ("__init__.py", "_paths.py"):
        shutil.copy2(REPO_ROOT / "dev" / name, tmp_path / "dev" / name)
    for name in ("__init__.py", "version_identity.py", "burned_versions.py"):
        shutil.copy2(REPO_ROOT / "dev" / "release" / name, package / name)
    (package / "burned_versions.json").write_text('{"burned": "not a list"}', encoding=UTF_8)

    completed = subprocess.run(  # noqa: S603 - fixed argv over this interpreter and this repository's own module.
        [sys.executable, "-m", "dev.release.version_identity", "--version", _CANDIDATE, "--scope", "seal"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert completed.stderr.startswith("REFUSED:"), completed.stderr
    assert "burned-version ledger" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_the_same_invocation_passes_over_the_ledger_it_ships(tmp_path: Path) -> None:
    """The other direction: the copy is a working gate until its ledger is not.

    Without this the case above is satisfied by any invocation that fails, for
    any reason -- a bad copy, a missing dependency, a wrong module path.
    """
    package = tmp_path / "dev" / "release"
    package.mkdir(parents=True)
    for name in ("__init__.py", "_paths.py"):
        shutil.copy2(REPO_ROOT / "dev" / name, tmp_path / "dev" / name)
    for name in ("__init__.py", "version_identity.py", "burned_versions.py", "burned_versions.json"):
        shutil.copy2(REPO_ROOT / "dev" / "release" / name, package / name)

    completed = subprocess.run(  # noqa: S603 - fixed argv over this interpreter and this repository's own module.
        [sys.executable, "-m", "dev.release.version_identity", "--version", _CANDIDATE, "--scope", "seal"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "available to seal" in completed.stdout
