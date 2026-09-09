"""Real-channel contracts for the mandatory recovery enrollment a create needs.

``config profile create`` publishes no profile until the recovery phrase it
minted has been handed over and returned verbatim. An oracle that drives the
real executable therefore has to play the operator's part for real, and the
tests protecting it have to fail for the same reason a release lane would: if
the possession proof stopped completing, or if the verb stopped demanding one,
a green result here would mean nothing.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import pytest

from ..._paths import UTF_8
from .._recovery_enrollment import (
    WINDOWS_BOOTSTRAP_MODULE,
    RecoveryEnrollmentError,
    enrolled_profile_creation,
    shape_enrollment_invocation,
    windows_bootstrap_interpreter,
)
from ..command_execution import run_command
from ..installed_tax_oracle import (
    PROFILE_LABEL,
    InstalledTaxOracleError,
    create_installed_profile,
    isolated_product_environment,
    profile_create_arguments,
)

pytestmark = [pytest.mark.hex_entrypoint, pytest.mark.serial]

_TIMEOUT_SECONDS = 600.0


def _development_cli() -> Path:
    """Resolve the ``aeat`` executable installed beside the running interpreter."""
    suffix = ".exe" if sys.platform == "win32" else ""
    cli = Path(sys.executable).with_name(f"aeat{suffix}")
    if not cli.is_file():
        raise AssertionError(f"the development environment installs no aeat executable at {cli}")
    return cli


def _creation_payload(passphrase: str) -> str:
    return json.dumps({"passphrase": passphrase, "passphrase_confirmation": passphrase}, separators=(",", ":"))


@pytest.mark.unit
def test_the_shaped_invocation_carries_this_platform_channel() -> None:
    """Which process is spawned, and which token it is told, differ by platform."""
    cli = Path(sys.executable).with_name("aeat.exe" if sys.platform == "win32" else "aeat")

    with enrolled_profile_creation(cli=cli, arguments=("config", "profile", "create")) as invocation:
        handoff, verification = invocation.inherited_descriptors
        if sys.platform == "win32":
            import msvcrt

            assert invocation.argv[:3] == (
                str(windows_bootstrap_interpreter(cli)),
                "-m",
                WINDOWS_BOOTSTRAP_MODULE,
            )
            # The bootstrap injects the descriptor options itself, so the tail
            # it is handed is the ordinary command and nothing else.
            assert invocation.argv[-4:] == ("--", "config", "profile", "create")
            assert str(msvcrt.get_osfhandle(handoff)) in invocation.argv
            assert str(msvcrt.get_osfhandle(verification)) in invocation.argv
        else:
            assert invocation.argv[0] == str(cli)
            assert invocation.argv[-4:] == (
                "--recovery-handoff-fd",
                str(handoff),
                "--recovery-verification-fd",
                str(verification),
            )


@pytest.mark.unit
def test_a_directory_with_no_interpreter_refuses_instead_of_spawning_nothing(tmp_path: Path) -> None:
    """The bootstrap is what runs on Windows, so its absence is the operator's problem."""
    with pytest.raises(RecoveryEnrollmentError, match="recovery bootstrap"):
        windows_bootstrap_interpreter(tmp_path / "empty" / "aeat.exe")


@pytest.mark.integration
def test_the_installed_cli_refuses_a_create_with_no_enrollment_channel(tmp_path: Path) -> None:
    """The teeth: creation is still refused when no channel is supplied.

    Without this, the passing case below would be indistinguishable from a verb
    that quietly stopped asking for a possession proof - which is the shape of
    regression that leaves a release lane green in intent and dead in fact.
    """
    cli = _development_cli()
    environment = isolated_product_environment(tmp_path / "state")

    refusal = run_command(
        (str(cli), "--format", "json", *profile_create_arguments(), "--secrets-stdin"),
        cwd=tmp_path,
        environment=environment,
        timeout_seconds=_TIMEOUT_SECONDS,
        input_text=_creation_payload(secrets.token_urlsafe(32)),
    )

    assert refusal.returncode != 0
    envelope = json.loads(refusal.stderr)
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert "--recovery-handoff-fd" in envelope["error"]["message"]
    assert "--recovery-verification-fd" in envelope["error"]["message"]


@pytest.mark.integration
def test_creation_completes_the_possession_proof_end_to_end(tmp_path: Path) -> None:
    """The whole point: a real profile, published only after a verified handover."""
    cli = _development_cli()
    environment = isolated_product_environment(tmp_path / "state")

    execution = create_installed_profile(
        cli,
        cwd=tmp_path,
        environment=environment,
        passphrase=secrets.token_urlsafe(32),
        timeout_seconds=_TIMEOUT_SECONDS,
    )

    envelope = json.loads(execution.stdout)
    assert envelope["status"] == "success"
    assert envelope["result"]["profile_name"] == PROFILE_LABEL
    # The verb emits this only once the returned proof matched the phrase it
    # minted, so its presence is the enrollment evidence rather than a label.
    assert [notice["code"] for notice in envelope["notices"]] == ["PROFILE_RECOVERY_ENROLLED"]


@pytest.mark.integration
def test_a_refused_creation_is_raised_rather_than_carried_forward(tmp_path: Path) -> None:
    """Everything the oracle asserts afterwards depends on this profile existing."""
    cli = _development_cli()
    environment = isolated_product_environment(tmp_path / "state")
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding=UTF_8)
    environment["CADRUMO_LOCAL_STORAGE_ROOT"] = str(blocker / "state")

    with pytest.raises(InstalledTaxOracleError, match="installed command failed"):
        create_installed_profile(
            cli,
            cwd=tmp_path,
            environment=environment,
            passphrase=secrets.token_urlsafe(32),
            timeout_seconds=_TIMEOUT_SECONDS,
        )


@contextmanager
def _fabricated_possession_proof() -> Iterator[tuple[int, int]]:
    """Yield a channel whose operator returns a phrase it was never handed.

    The defect fixture for the exchange itself. It takes delivery exactly as
    the honest relay does and then answers with a well-formed document
    carrying the wrong phrase, which is the shape a caller would produce if it
    invented a proof instead of proving possession.
    """
    handoff_read, handoff_write = os.pipe()
    verification_read, verification_write = os.pipe()

    def answer_with_the_wrong_phrase() -> None:
        delivered = bytearray()
        while not delivered.endswith(b"\n"):
            chunk = os.read(handoff_read, 4096)
            if not chunk:
                break
            delivered.extend(chunk)
        fabricated = json.dumps({"recovery_mnemonic": " ".join(["fabricated"] * 24)}).encode()
        with suppress(OSError):
            os.write(verification_write, fabricated + b"\n")
        with suppress(OSError):
            os.close(verification_write)

    operator = threading.Thread(target=answer_with_the_wrong_phrase, daemon=True)
    operator.start()
    try:
        yield handoff_write, verification_read
    finally:
        for descriptor in (handoff_write, verification_read):
            with suppress(OSError):
                os.close(descriptor)
        operator.join(timeout=5.0)
        for descriptor in (handoff_read, verification_write):
            with suppress(OSError):
                os.close(descriptor)


@pytest.mark.integration
def test_a_fabricated_possession_proof_is_refused(tmp_path: Path) -> None:
    """The teeth on the exchange: only the exact minted phrase publishes a profile.

    Returning a well-formed document with the wrong phrase is the difference
    between proving possession and asserting it. If this ever passed, the
    green end-to-end case above would prove only that two pipes were wired,
    not that the phrase reached the caller.
    """
    cli = _development_cli()
    environment = isolated_product_environment(tmp_path / "state")

    with _fabricated_possession_proof() as (handoff, verification):
        invocation = shape_enrollment_invocation(
            cli=cli,
            arguments=("--format", "json", *profile_create_arguments(), "--secrets-stdin"),
            handoff=handoff,
            verification=verification,
        )
        refusal = run_command(
            invocation.argv,
            cwd=tmp_path,
            environment=environment,
            timeout_seconds=_TIMEOUT_SECONDS,
            input_text=_creation_payload(secrets.token_urlsafe(32)),
            inherited_descriptors=invocation.inherited_descriptors,
        )

    assert refusal.returncode != 0
    envelope = json.loads(refusal.stderr)
    assert envelope["status"] == "error"
    assert envelope["error"]["code"] == "REFUSED_CLI_BOUNDARY"
    assert "no profile was created" in envelope["error"]["message"]
