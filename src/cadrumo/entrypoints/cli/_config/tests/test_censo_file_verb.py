"""``config profile censo file`` refusal contract while extraction is unpinned."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from .....tests.cli_runner import invoke_cached_cli
from .....tests.secure_sql import isolated_cli_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _active_profile(tmp_path: Path) -> Iterator[None]:
    """Provide the active profile the censo verbs are bound to, and isolate storage.

    ``config profile censo file`` declares a ``profile-bound`` write route, so
    with no active profile the CLI root refuses at the boundary
    (``REFUSED_CLI_BOUNDARY``, failed condition ``profile.active``) and the
    artefact is never opened. These cases assert the PARSER's refusal, which
    lives downstream of that guard, so without a profile they would be
    asserting a contract they never reach. A profile is also the honest
    scenario: a cotejo compares a certificate against the active profile's
    censo facts, and there is nothing to compare against without one.

    The bucket is provisioned directly rather than registered through the CLI
    door. Registration derives custody material through the supervised
    Argon2id worker, which spawns a subprocess per call; under the full CLI
    tree at eight xdist workers that spawn storm makes the supervisor refuse
    with ``KDF_SUPERVISION_UNAVAILABLE``, and these cases would then fail for
    a reason unrelated to what they assert. The KDF path is covered where it
    is the subject, not incidentally here.
    """
    with isolated_cli_runtime_profile(tmp_path=tmp_path):
        yield


def _invoke_with_artefact(tmp_path: Path, payload: bytes):
    artefact = tmp_path / "certificado.pdf"
    artefact.write_bytes(payload)
    return invoke_cached_cli(["--format", "json", "config", "profile", "censo", "file", "--file", str(artefact)])


def _stderr_document(result) -> dict[str, object]:
    """Extract the JSON error document from stderr (line-scanned: logging may interleave)."""
    stderr = result.stderr if result.stderr_bytes is not None else ""
    for line in stderr.splitlines():
        candidate = line.strip()
        if candidate.startswith("{"):
            parsed = json.loads(candidate)
            assert isinstance(parsed, dict)
            document: dict[str, object] = {}
            for key, value in parsed.items():
                assert isinstance(key, str), candidate
                document[key] = value
            return document
    raise AssertionError(f"no JSON document on stderr: {stderr[:400]!r}")


def test_non_pdf_artefact_refuses_with_the_registered_parse_code(tmp_path: Path) -> None:
    result = _invoke_with_artefact(tmp_path, b"not a certificate")
    assert result.exit_code != 0
    document = _stderr_document(result)
    error = document.get("error")
    assert isinstance(error, dict)
    assert error.get("code") == "FAIL_CERTIFICADO_CENSAL_PARSE"
    # The refusal must say WHAT was expected. It used to be asserted through a
    # `suggestion` string, which the envelope retired: that name is reserved
    # for the typed action projection now, and the error model refuses it
    # outright, so the old assertion could only ever fail. This refusal carries
    # no typed action yet -- naming a next step here would mean enrolling one
    # in the operator action catalogue rather than reviving the retired field.
    assert "suggestion" not in error
    message = error.get("message")
    assert isinstance(message, str)
    assert "Certificado de Situación Censal" in message


def test_pdf_artefact_refuses_while_extraction_is_unpinned(tmp_path: Path) -> None:
    result = _invoke_with_artefact(tmp_path, b"%PDF-1.7 specimen-free")
    assert result.exit_code != 0
    document = _stderr_document(result)
    error = document.get("error")
    assert isinstance(error, dict)
    assert error.get("code") == "FAIL_CERTIFICADO_CENSAL_PARSE"


def test_missing_artefact_is_refused_at_the_cli_boundary(tmp_path: Path) -> None:
    result = invoke_cached_cli(
        ["--format", "json", "config", "profile", "censo", "file", "--file", str(tmp_path / "absent.pdf")],
    )
    assert result.exit_code != 0


def test_apply_routes_through_the_single_cotejo_apply_authority() -> None:
    """The ``--apply`` door persists through ``apply_cotejo`` (one CENSO_APPLIED), never a bare write.

    The parser refuses every document while the layout extraction is
    unpinned, so the door offers no seam to inject a synthetic certificate;
    the adopt-all emission itself is proven directly against ``apply_cotejo``
    in the user_profile suite. This inspection-level pin guards the door's
    routing: it must call the single apply authority and never re-introduce a
    parallel record-repository fact write that would skip the event.
    """
    import inspect

    from .. import _censo_file

    source = inspect.getsource(_censo_file.censo_file)
    # The persistence call is apply_cotejo(...), never a bare apply_fact_changes(...)
    # write that would skip the CENSO_APPLIED emission (the prose comment naming
    # the bypassed write is not a call, so pin on the call form).
    assert "apply_cotejo(state" in source
    assert "apply_fact_changes(" not in source
