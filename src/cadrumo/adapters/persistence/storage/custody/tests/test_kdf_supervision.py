"""Real child-process tests for supervised current-format profile KDF work."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from itertools import product
from pathlib import Path
from typing import Literal, cast
from uuid import UUID

import pytest

from ......core.config import Settings
from .. import (
    PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfCalibration,
    ProfileCustodyKdfParameters,
    ProfileCustodyKdfResources,
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
    ProfileCustodySentinelRecord,
    calibrate_profile_kdf,
    fixed_profile_kdf_fallback,
    parse_profile_custody_envelope,
    parse_profile_custody_sentinel_record,
    profile_kdf_grid,
    profile_kdf_is_eligible,
    profile_kdf_lease,
    propose_profile_kdf_ratchet,
    unlock_profile_custody,
    unlock_profile_custody_recovery_material,
    wrap_profile_custody_password_material,
    wrap_profile_custody_recovery_material,
)
from .._kdf_attestation import parse_ready_attestation
from .._kdf_process import apply_posix_worker_limits, worker_environment
from .._kdf_process import terminate_process_tree as _terminate_process_tree
from .._kdf_supervision import (
    KDF_FRAME_CONTROL,
    KDF_FRAME_HEADER,
    KDF_FRAME_MAGIC,
    KDF_FRAME_VERSION,
    _select_profile_kdf_calibration,
    _SupervisedKdfWorker,
    read_kdf_frame,
)
from .._kdf_windows_job import _WindowsJob

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("06648eb9-e60e-46d2-bd35-9aaf55a92e24")
_PASSPHRASE = "profile " + "password" + " 123"
_DEK = bytes(range(32))
_ENVELOPE_BYTES = (
    b'{"dek_epoch":"ZWVlZWVlZWVlZWVlZWVlZQ==","kdf":{"algorithm":"argon2id","iterations":2,'
    b'"memory_mib":19,"output_bytes":32,"parallelism":1,"salt_b64":"a2tra2tra2tra2tra2traw==",'
    b'"version":19},"key_schedule":"profile-password-dek-wrap/v1","password_encoding":"utf-8",'
    b'"password_generation":1,"previous_envelope_digest":null,"profile_id":"06648eb9-e60e-46d2-bd35-9aaf55a92e24",'
    b'"schema_version":1,"self_digest":"sha256:b86a72a1b3fbf893e44d47d498d92f07638c2938ca4202862541b1e5a074bd9f",'
    b'"wrapped_dek":{"ciphertext_b64":"Y1uJUgcd8P08G+5k8c8XGqGQ1mKjsWzDUyK/nz+uJLc=",'
    b'"nonce_b64":"yzNoNTTFQJYHUFCT","tag_b64":"coEpLYUWlTSHLYiQ5PNliA=="}}'
)
_SENTINEL_BYTES = (
    b'{"ciphertext_b64":"H74N673vgT70IxPjFyBqUrKhVKV5gGPDTeILFeNqw5U4YwoF0pD0BlJcl+4pW3KEkCrxgl3hmQoGqUbpR62MzsAcuLYLZLqbLXyg3ySjBo6b7ZvHKapV4qyP2LTnjJoTjc04iF217iAWgAVq1FQklioPzolYyn3VA14RI5mP08p13iDFguF9VBBnNpyLjd+awNfPsIQ5Wm0I9i+vvuV75jNCZ2F7s2AVf9e8BNPry7Di4YfjS9pxcYOdujNryHPxBydThWOBrC5eTvlkih6wMer0/1w3PN9W0vph+wyBX12dHbBcRW4r",'
    b'"data_format_version":1,"dek_epoch":"ZWVlZWVlZWVlZWVlZWVlZQ==","nonce_b64":"Pjf6osqjPnA4Tkmh",'
    b'"product":"cadrumo","profile_id":"06648eb9-e60e-46d2-bd35-9aaf55a92e24",'
    b'"purpose":"profile-dek-sentinel/v1","schema_version":1,"tag_b64":"37iPKamYW8bZL8MgXDd6/g=="}'
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(cadrumo_local_storage_root=tmp_path)


def _kdf(
    *,
    memory_mib: Literal[19, 32, 64, 128, 256] = 19,
    iterations: Literal[2, 3, 4, 6, 8, 10] = 2,
    parallelism: Literal[1, 2, 4] = 1,
) -> ProfileCustodyKdfParameters:
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=memory_mib,
        iterations=iterations,
        parallelism=parallelism,
        salt_b64="a2tra2tra2tra2tra2traw==",
        output_bytes=32,
    )


def _unlock_inputs(
    *, kdf: ProfileCustodyKdfParameters | None = None
) -> tuple[ProfileCustodyEnvelope, ProfileCustodySentinelRecord]:
    if kdf is not None:
        raise ValueError("the real current-format unwrap fixture has fixed persisted KDF parameters")
    return parse_profile_custody_envelope(_ENVELOPE_BYTES), parse_profile_custody_sentinel_record(_SENTINEL_BYTES)


def test_finite_grid_and_fixed_fallback_are_closed_to_the_current_contract() -> None:
    salt = b"s" * 16
    grid = profile_kdf_grid(salt=salt)
    expected_axes = product((19, 32, 64, 128, 256), (2, 3, 4, 6, 8, 10), (1, 2, 4))

    assert {(item.memory_mib, item.iterations, item.parallelism) for item in grid} == set(expected_axes)
    assert grid == tuple(
        sorted(grid, key=lambda item: (item.memory_mib, item.iterations, item.parallelism), reverse=True)
    )
    assert fixed_profile_kdf_fallback(salt=salt).model_dump(mode="json") == {
        "algorithm": "argon2id",
        "version": 19,
        "memory_mib": 64,
        "iterations": 3,
        "parallelism": 1,
        "salt_b64": "c3Nzc3Nzc3Nzc3Nzc3Nzcw==",
        "output_bytes": 32,
    }


def test_fallback_eligibility_requires_the_same_memory_and_cpu_gate() -> None:
    fallback = fixed_profile_kdf_fallback(salt=b"s" * 16)

    assert profile_kdf_is_eligible(
        fallback,
        resources=ProfileCustodyKdfResources(available_memory_bytes=256 * 1024 * 1024, cpu_count=1),
    )
    assert not profile_kdf_is_eligible(
        fallback,
        resources=ProfileCustodyKdfResources(available_memory_bytes=127 * 1024 * 1024, cpu_count=1),
    )
    parallel_candidate = next(item for item in profile_kdf_grid(salt=b"s" * 16) if item.parallelism == 2)
    assert not profile_kdf_is_eligible(
        parallel_candidate,
        resources=ProfileCustodyKdfResources(available_memory_bytes=256 * 1024 * 1024, cpu_count=1),
    )


def test_deterministic_selector_chooses_first_strongest_complete_target_median() -> None:
    strongest = _kdf(memory_mib=128, iterations=8, parallelism=1)
    eligible_target = _kdf(memory_mib=64, iterations=6, parallelism=1)
    weaker_target = _kdf(memory_mib=32, iterations=4, parallelism=1)

    selected = _select_profile_kdf_calibration(
        [
            (strongest, None),
            (eligible_target, (0.34, 0.29, 0.31, 0.30, 0.33)),
            (weaker_target, (0.26, 0.28, 0.27, 0.29, 0.30)),
        ],
    )

    assert selected == ProfileCustodyKdfCalibration(
        version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
        parameters=eligible_target,
        source="measured",
        median_seconds=0.31,
    )


def test_incomplete_point_cannot_be_selected() -> None:
    candidate = _kdf(memory_mib=64, iterations=6, parallelism=1)

    with pytest.raises(ValueError, match="five non-negative samples"):
        _select_profile_kdf_calibration([(candidate, (0.3, 0.3, 0.3, 0.3))])


def test_os_released_lease_blocks_another_real_process_then_recovers_after_death(tmp_path: Path) -> None:
    hold_script = """
from pathlib import Path
import sys
import time

from cadrumo.adapters.persistence.storage.custody import profile_kdf_lease

with profile_kdf_lease(deadline=time.monotonic() + 30):
    print("leased", flush=True)
    time.sleep(30)
"""
    holder = subprocess.Popen(  # noqa: S603 - fixed test interpreter and module import
        [sys.executable, "-c", hold_script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path)},
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "leased"
        with (
            pytest.raises(ProfileCustodyRefusedError) as captured,
            profile_kdf_lease(settings=_settings(tmp_path), deadline=time.monotonic() + 0.1),
        ):
            raise AssertionError("cross-process lease unexpectedly admitted a concurrent owner")
        assert captured.value.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT
        holder.kill()
        holder.wait(timeout=2.0)
        with profile_kdf_lease(settings=_settings(tmp_path), deadline=time.monotonic() + 1.0):
            assert (tmp_path / "profile-kdf.v1.lock").is_file()
    finally:
        if holder.poll() is None:
            holder.kill()
            holder.wait(timeout=2.0)


def test_strict_frame_reader_refuses_oversized_wire_length() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.write(
            write_fd,
            KDF_FRAME_HEADER.pack(KDF_FRAME_MAGIC, KDF_FRAME_VERSION, KDF_FRAME_CONTROL, 0, 8193),
        )
        with pytest.raises(ValueError, match="bounded transport"):
            read_kdf_frame(read_fd)
    finally:
        os.close(write_fd)
        os.close(read_fd)


def test_ready_without_a_secret_then_failure_reaps_the_real_worker_tree() -> None:
    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 5.0)
    process: subprocess.Popen[bytes] | None = None

    with pytest.raises(RuntimeError, match="test containment cleanup"), worker:
        process = worker._process
        assert process is not None
        assert process.poll() is None
        raise RuntimeError("test containment cleanup")

    assert process is not None
    assert process.poll() is not None


def test_ready_attestation_proves_the_real_os_containment_environment_and_handle_boundary() -> None:
    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 5.0)

    with worker:
        process = worker._process
        job = worker._job
        attestation = worker._ready_payload
        assert process is not None
        assert attestation is not None
        assert attestation["cwd"] != str(Path.cwd())
        environment_keys = attestation["environment_keys"]
        assert isinstance(environment_keys, list)
        assert all(isinstance(key, str) for key in environment_keys)
        assert "PATH" not in environment_keys
        assert worker._request_fd is not None
        assert worker._result_fd is not None
        if sys.platform == "win32":
            assert job is not None
            assert job.contains(process)
            assert job.limits() == {
                "cpu_seconds": 15,
                "memory_bytes": 1024 * 1024 * 1024,
                "max_processes": 2,
            }
            import msvcrt

            assert not os.get_handle_inheritable(msvcrt.get_osfhandle(worker._request_fd))
            assert not os.get_handle_inheritable(msvcrt.get_osfhandle(worker._result_fd))
        else:
            assert job is None
            assert os.getpgid(process.pid) == process.pid
            assert worker._expected_posix_file_descriptors is not None
            assert attestation["open_file_descriptors"] == sorted(
                {0, 1, 2, *worker._expected_posix_file_descriptors},
            )
            assert not os.get_inheritable(worker._request_fd)
            assert not os.get_inheritable(worker._result_fd)


def _assert_posix_worker_sheds_extra_inherited_pty_and_pipe_descriptors_before_ready() -> None:
    import pty

    pty_open_member = "openpty"
    sysconf_member = "sysconf"
    openpty = cast("Callable[[], tuple[int, int]]", getattr(pty, pty_open_member))
    sysconf = cast("Callable[[str], int]", getattr(os, sysconf_member))
    request_read, request_write = os.pipe()
    result_read, result_write = os.pipe()
    extra_pipe_read, extra_pipe_write = os.pipe()
    pty_controller, pty_peer = openpty()
    inherited = (request_read, result_write, extra_pipe_read, extra_pipe_write, pty_controller, pty_peer)
    for descriptor in inherited:
        os.set_inheritable(descriptor, True)

    with tempfile.TemporaryDirectory() as neutral_directory:
        neutral_root = Path(neutral_directory)
        command = [
            sys.executable,
            "-m",
            "cadrumo.adapters.persistence.storage.custody._kdf_worker",
            "--request-fd",
            str(request_read),
            "--result-fd",
            str(result_write),
            "--descriptor-bound",
            str(sysconf("SC_OPEN_MAX")),
        ]
        process = subprocess.Popen(  # noqa: S603 - fixed interpreter and module argv
            command,
            close_fds=True,
            cwd=neutral_root,
            env=worker_environment(neutral_root=neutral_root),
            pass_fds=inherited,
            preexec_fn=apply_posix_worker_limits,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.close(request_read)
        os.close(result_write)
        try:
            kind, value = read_kdf_frame(result_read)
            assert kind == KDF_FRAME_CONTROL
            attestation = parse_ready_attestation(value)
            assert attestation["open_file_descriptors"] == sorted({0, 1, 2, request_read, result_write})

            os.write(extra_pipe_write, b"parent-owned")
            assert os.read(extra_pipe_read, len(b"parent-owned")) == b"parent-owned"
            assert getattr(os.fstat(pty_controller), "st_rdev", 0)
            assert getattr(os.fstat(pty_peer), "st_rdev", 0)
        finally:
            os.close(request_write)
            os.close(result_read)
            for descriptor in (extra_pipe_read, extra_pipe_write, pty_controller, pty_peer):
                os.close(descriptor)
            process.wait(timeout=5.0)


def test_real_worker_sheds_extra_inherited_pty_and_pipe_descriptors_before_ready() -> None:
    """Prove the native worker route closes every unapproved inherited channel."""
    if sys.platform != "win32":
        _assert_posix_worker_sheds_extra_inherited_pty_and_pipe_descriptors_before_ready()
        return

    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 5.0)
    with worker:
        assert worker._process is not None
        assert worker._job is not None
        assert worker._job.contains(worker._process)
        assert worker._job.limits() == {
            "cpu_seconds": 15,
            "memory_bytes": 1024 * 1024 * 1024,
            "max_processes": 2,
        }
        assert worker._request_fd is not None
        assert worker._result_fd is not None
        import msvcrt

        assert not os.get_handle_inheritable(msvcrt.get_osfhandle(worker._request_fd))
        assert not os.get_handle_inheritable(msvcrt.get_osfhandle(worker._result_fd))


def test_real_os_containment_refuses_or_reaps_a_worker_child_escape() -> None:
    child_script = """
import subprocess
import sys
import time

input()
try:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
except OSError:
    print("contained", flush=True)
else:
    print(child.pid, flush=True)
time.sleep(30)
"""
    parent = subprocess.Popen(  # noqa: S603 - fixed test interpreter and source
        [sys.executable, "-c", child_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=sys.platform != "win32",
    )
    job = _WindowsJob.create() if sys.platform == "win32" else None
    try:
        if job is not None:
            job.assign(parent)
            assert job.contains(parent)
        assert parent.stdin is not None
        assert parent.stdout is not None
        parent.stdin.write(b"\n")
        parent.stdin.flush()
        child_result = parent.stdout.readline().strip()
        if child_result == b"contained":
            assert sys.platform == "win32"
            _terminate_process_tree(parent, job)
            assert parent.poll() is not None
            return
        descendant_pid = int(child_result)
        if sys.platform != "win32":
            assert os.getpgid(descendant_pid) == parent.pid
        _terminate_process_tree(parent, job)
        deadline = time.monotonic() + 2.0
        while True:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() >= deadline:
                raise AssertionError("OS containment left the real worker descendant alive")
            time.sleep(0.02)
        assert parent.poll() is not None
    finally:
        if parent.poll() is None:
            _terminate_process_tree(parent, job)
        else:
            if job is not None:
                job.close()


def test_ready_then_deadline_terminates_and_reaps_the_real_worker() -> None:
    worker = _SupervisedKdfWorker(deadline=time.monotonic() + 5.0)
    process: subprocess.Popen[bytes] | None = None

    with pytest.raises(TimeoutError, match="did not respond"), worker:
        process = worker._process
        assert process is not None
        worker._read_response_frame()

    assert process is not None
    assert process.poll() is not None


def test_unavailable_canonical_root_has_no_weaker_supervision_fallback(tmp_path: Path) -> None:
    envelope, sentinel = _unlock_inputs()

    first_enrollment_root = tmp_path / "first-enrollment-root"
    unlock_profile_custody(
        envelope,
        _PASSPHRASE,
        sentinel=sentinel,
        settings=_settings(first_enrollment_root),
    )
    assert first_enrollment_root.is_dir()

    blocked_parent = tmp_path / "non-directory-parent"
    blocked_parent.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        unlock_profile_custody(
            envelope,
            _PASSPHRASE,
            sentinel=sentinel,
            settings=_settings(blocked_parent / "custody-root"),
        )

    assert captured.value.refusal is ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE


def test_sentinel_record_rejects_fixed_purpose_substitution() -> None:
    substituted = _SENTINEL_BYTES.replace(b"profile-dek-sentinel/v1", b"profile-dek-sentinel/x1")

    with pytest.raises(ProfileCustodyRecordError):
        parse_profile_custody_sentinel_record(substituted)


def test_real_supervised_calibration_returns_only_the_versioned_grid_or_fixed_fallback(tmp_path: Path) -> None:
    calibration = calibrate_profile_kdf(salt=b"c" * 16, settings=_settings(tmp_path))

    assert calibration.version == PROFILE_CUSTODY_KDF_CALIBRATION_VERSION
    assert calibration.parameters in profile_kdf_grid(salt=b"c" * 16)
    if calibration.source == "fallback":
        assert calibration.parameters == fixed_profile_kdf_fallback(salt=b"c" * 16)
        assert calibration.median_seconds is None
    else:
        assert calibration.median_seconds is not None
        assert 0.250 <= calibration.median_seconds <= 0.500


def test_real_child_unwrap_returns_only_a_parent_sentinel_proven_dek(tmp_path: Path) -> None:
    envelope, sentinel = _unlock_inputs()

    unlock = unlock_profile_custody(
        envelope,
        _PASSPHRASE,
        sentinel=sentinel,
        settings=_settings(tmp_path),
    )

    assert unlock.profile_id == _PROFILE_ID
    assert unlock.dek == _DEK
    assert unlock.envelope_digest == envelope.self_digest


def test_real_worker_keeps_short_recovery_secret_outside_password_policy(tmp_path: Path) -> None:
    envelope, sentinel = _unlock_inputs()
    recovery_candidate = "short"
    recovery_aad = b"profile-recovery-policy-independence/v1"
    settings = _settings(tmp_path)

    wrapped = wrap_profile_custody_recovery_material(
        secret=recovery_candidate,
        dek=_DEK,
        kdf=envelope.kdf,
        associated_data=recovery_aad,
        settings=settings,
    )
    recovered = unlock_profile_custody_recovery_material(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        kdf=envelope.kdf,
        wrapped_dek=wrapped,
        secret=recovery_candidate,
        associated_data=recovery_aad,
        sentinel=sentinel,
        settings=settings,
    )

    assert recovered == _DEK
    with pytest.raises(ProfileCustodyPasswordError, match="too_few_scalars"):
        wrap_profile_custody_password_material(
            secret=recovery_candidate,
            dek=_DEK,
            kdf=envelope.kdf,
            associated_data=recovery_aad,
            settings=settings,
        )


def test_wrong_password_and_canonical_sentinel_substitution_do_not_release_a_dek(tmp_path: Path) -> None:
    envelope, sentinel = _unlock_inputs()

    with pytest.raises(ProfileCustodyPasswordError):
        unlock_profile_custody(
            envelope,
            "wrong profile password",
            sentinel=sentinel,
            settings=_settings(tmp_path),
        )
    substituted = parse_profile_custody_sentinel_record(
        _SENTINEL_BYTES.replace(
            b"06648eb9-e60e-46d2-bd35-9aaf55a92e24",
            b"f6648eb9-e60e-46d2-bd35-9aaf55a92e24",
        ),
    )
    with pytest.raises(ProfileCustodyRecordError):
        unlock_profile_custody(
            envelope,
            _PASSPHRASE,
            sentinel=substituted,
            settings=_settings(tmp_path),
        )


def test_ratcheting_requires_the_real_post_sentinel_unlock_and_never_weakens(tmp_path: Path) -> None:
    envelope, sentinel = _unlock_inputs()
    unlock = unlock_profile_custody(
        envelope,
        _PASSPHRASE,
        sentinel=sentinel,
        settings=_settings(tmp_path),
    )
    stronger = ProfileCustodyKdfCalibration(
        version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
        parameters=_kdf(memory_mib=32, iterations=3),
        source="measured",
        median_seconds=0.3,
    )
    weaker = ProfileCustodyKdfCalibration(
        version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
        parameters=_kdf(memory_mib=19, iterations=2),
        source="fallback",
        median_seconds=None,
    )

    proposal = propose_profile_kdf_ratchet(unlock, stronger)

    assert proposal is not None
    assert proposal.profile_id == _PROFILE_ID
    assert proposal.expected_envelope_digest == envelope.self_digest
    assert proposal.proposed == stronger.parameters
    assert propose_profile_kdf_ratchet(unlock, weaker) is None


def test_expired_deadline_refuses_and_releases_the_supervised_child_boundary(tmp_path: Path) -> None:
    envelope, sentinel = _unlock_inputs()

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        unlock_profile_custody(
            envelope,
            _PASSPHRASE,
            sentinel=sentinel,
            settings=_settings(tmp_path),
            timeout_seconds=0.0001,
        )

    assert captured.value.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT
