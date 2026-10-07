"""Registry startup defers concrete effects to their established execution owners."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.llm_classification_ports import LLMClassificationPorts
from ...application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
)
from ...application.ledger.llm_review_execution import LedgerLlmReviewExecutor
from ...application.live.verify import VerifySurface
from ...application.live.verify_capture_operation import VerifyLiveObservation
from ...application.operations.registry import OperationRegistry
from ...application.operations.tests.authority_test_support import unread_authority_operation
from ...core.config import Settings
from ...core.identity.tax_id import tax_id_identity_token
from ...core.identity_check_verdict import IdentityCheckVerdictValue
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...tests.offline_seal import OfflineGuard, offline_guard_fixture
from .. import operation_composition

__all__ = ["offline_guard_fixture"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "60606060-6060-4060-8060-606060606060"
_NIF = "B12345674"
_LEDGER_DEFINITIONS = (LEDGER_CLASSIFY_REVIEW_DEFINITION_ID, LEDGER_SPLIT_REVIEW_DEFINITION_ID)


def test_registry_builds_when_ledger_llm_and_aeat_execution_modules_are_unavailable(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[3]
    base_executable = getattr(sys, "_base_executable", None)
    assert isinstance(base_executable, str)
    interpreter = Path(base_executable).resolve(strict=True)
    package_paths = sorted({sysconfig.get_path("purelib"), sysconfig.get_path("platlib")})
    probe = """
import faulthandler
import importlib.abc
import json
import os
import sys

print(json.dumps({'pid': os.getpid(), 'interpreter': sys.executable}), flush=True)
faulthandler.dump_traceback_later(25)
sys.path[:0] = [sys.argv[1], *json.loads(sys.argv[2])]
blocked = {
    'cadrumo.entrypoints.ledger_llm_composition',
    'cadrumo.adapters.outbound.aeat.sede.nif_iva_check',
    'cadrumo.adapters.outbound.aeat.sede.groi_check',
}

class UnavailableExecution(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in blocked:
            raise ModuleNotFoundError('fixture: execution implementation unavailable', name=fullname)

def refuse_effects(event, args):
    if event in {
        'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system',
        'os.exec', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.spawn',
    }:
        raise AssertionError('registry construction attempted an active effect')

sys.addaudithook(refuse_effects)
sys.meta_path.insert(0, UnavailableExecution())
from cadrumo.core.config import Settings
from cadrumo.entrypoints.operation_composition import build_production_operation_registry

registry = build_production_operation_registry(settings=Settings(_env_file=None))
assert registry.public_contract_set.definitions
assert registry.public_contract_set.contract_set_digest
assert not blocked.intersection(sys.modules)
faulthandler.cancel_dump_traceback_later()
"""
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "PATH", "COMSPEC", "USERNAME", "USERDOMAIN"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    environment.update(
        {
            "CADRUMO_AUTHORITY_ROOT": os.environ["CADRUMO_AUTHORITY_ROOT"],
            "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "storage"),
            "CADRUMO_STORAGE_ROOT": str(tmp_path / "storage"),
            "PYDANTIC_DISABLE_PLUGINS": "__all__",
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "APPDATA": str(tmp_path),
            "LOCALAPPDATA": str(tmp_path),
        }
    )
    stdout_path = tmp_path / "registry-probe.stdout"
    stderr_path = tmp_path / "registry-probe.stderr"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(  # noqa: S603 - resolved base interpreter, fixed import-only probe, owned child
            [str(interpreter), "-I", "-S", "-B", "-c", probe, str(source), json.dumps(package_paths)],
            cwd=tmp_path,
            env=environment,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired as error:
            error.add_note(f"Owned child PID: {process.pid}")
            error.add_note(stdout_path.read_text(encoding="utf-8"))
            error.add_note(stderr_path.read_text(encoding="utf-8"))
            raise
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
    assert process.returncode == 0, stderr_path.read_text(encoding="utf-8")
    observation = json.loads(stdout_path.read_text(encoding="utf-8"))
    assert observation["pid"] == process.pid
    assert Path(observation["interpreter"]).resolve(strict=True) == interpreter
    assert not (tmp_path / "storage").exists()


@dataclass
class _LedgerRegistration:
    settings: Settings
    registry: OperationRegistry
    ledger: LedgerActionPorts
    calls: list[tuple[str, PinnedAuthorityOperation]]


@pytest.fixture(scope="module")
def ledger_registration() -> _LedgerRegistration:
    settings = Settings(_env_file=None)
    ledger = cast("LedgerActionPorts", object())
    calls: list[tuple[str, PinnedAuthorityOperation]] = []

    def ledger_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        calls.append((bucket_id, operation))
        return ledger

    registry = operation_composition.build_production_operation_registry(
        settings=settings, ledger_action_ports_factory=ledger_factory
    )
    assert not calls
    return _LedgerRegistration(settings, registry, ledger, calls)


@pytest.mark.parametrize("definition_id", _LEDGER_DEFINITIONS)
@pytest.mark.parametrize("refused", [False, True])
def test_registered_ledger_factory_forwards_exact_owner_settings_and_preserves_refusal(
    ledger_registration: _LedgerRegistration,
    definition_id: str,
    refused: bool,
    monkeypatch: pytest.MonkeyPatch,
    offline_guard: OfflineGuard,
) -> None:
    from .. import ledger_llm_composition

    fixture = ledger_registration
    fixture.calls.clear()
    operation = unread_authority_operation()
    llm = cast("LLMClassificationPorts", object())
    composer_calls: list[tuple[str, Settings]] = []
    primary = ValueError("synthetic ledger composer refusal")

    def compose(*, bucket_id: str, settings: Settings) -> ledger_llm_composition.LedgerLlmComposition:
        composer_calls.append((bucket_id, settings))
        if refused:
            raise primary
        return ledger_llm_composition.LedgerLlmComposition(
            ports=llm,
            bucket_event_repository=cast("BucketEventHistoryRepositoryProtocol", object()),
        )

    monkeypatch.setattr(ledger_llm_composition, "compose_ledger_llm", compose)
    executor = fixture.registry.lookup(definition_id).executor_factory.build()
    assert isinstance(executor, LedgerLlmReviewExecutor)
    if refused:
        with pytest.raises(ValueError) as escaped:
            executor._factory(bucket_id=_BUCKET_ID, operation=operation)
        assert escaped.value is primary
    else:
        ports = executor._factory(bucket_id=_BUCKET_ID, operation=operation)
        assert ports.ledger is fixture.ledger and ports.llm is llm and ports.settings is fixture.settings
    assert fixture.calls == [(_BUCKET_ID, operation)]
    assert composer_calls == [(_BUCKET_ID, fixture.settings)]
    assert not offline_guard.refused


@pytest.mark.parametrize("surface", [VerifySurface.NIF_IVA, VerifySurface.TGVI])
@pytest.mark.parametrize("expected", ["valid", None])
def test_verify_branch_forwards_settings_expectation_and_converts_real_observation(
    surface: VerifySurface,
    expected: IdentityCheckVerdictValue | None,
    monkeypatch: pytest.MonkeyPatch,
    offline_guard: OfflineGuard,
) -> None:
    from ...adapters.outbound.aeat.sede import groi_check, nif_iva_check

    settings = Settings(_env_file=None)
    calls: list[tuple[bytes, dict[str, object], Settings]] = []
    observation = VerifyLiveObservation(nif=_NIF, verdict="valid", raw_evidence_locator="fixture://evidence")
    result = (
        nif_iva_check.NifIvaCheckResult(
            observations=(nif_iva_check.SedeNifIvaCheckObservation.model_validate(observation.model_dump()),)
        )
        if surface is VerifySurface.NIF_IVA
        else groi_check.GroiResult(observations=(groi_check.GroiNifVerdict.model_validate(observation.model_dump()),))
    )

    async def collect(
        payload: bytes, *, expected: dict[str, object], settings: Settings
    ) -> nif_iva_check.NifIvaCheckResult | groi_check.GroiResult:
        calls.append((payload, expected, settings))
        return result

    owner = nif_iva_check if surface is VerifySurface.NIF_IVA else groi_check
    name = "collect_nif_iva_check_observations" if surface is VerifySurface.NIF_IVA else "collect_groi_observations"
    monkeypatch.setattr(owner, name, collect)
    acquired = asyncio.run(
        operation_composition._acquire_registry_verify_observation(
            surface, _NIF, expected, unread_authority_operation(), resolved_settings=settings
        )
    )
    assert type(acquired) is VerifyLiveObservation and acquired == observation
    assert calls == [(b"", {tax_id_identity_token(_NIF): expected or "unknown"}, settings)]
    assert not offline_guard.refused


@pytest.mark.parametrize("surface", [VerifySurface.NIF_IVA, VerifySurface.TGVI])
def test_verify_branch_preserves_the_canonical_collector_refusal(
    surface: VerifySurface, monkeypatch: pytest.MonkeyPatch, offline_guard: OfflineGuard
) -> None:
    from ...adapters.outbound.aeat.sede import groi_check, nif_iva_check

    primary = ValueError("synthetic collector refusal")

    async def collect(*_args: object, **_kwargs: object) -> None:
        raise primary

    owner = nif_iva_check if surface is VerifySurface.NIF_IVA else groi_check
    name = "collect_nif_iva_check_observations" if surface is VerifySurface.NIF_IVA else "collect_groi_observations"
    monkeypatch.setattr(owner, name, collect)
    with pytest.raises(ValueError) as escaped:
        asyncio.run(
            operation_composition._acquire_registry_verify_observation(
                surface, _NIF, None, unread_authority_operation(), resolved_settings=Settings(_env_file=None)
            )
        )
    assert escaped.value is primary
    assert not offline_guard.refused


@pytest.mark.parametrize("surface", [VerifySurface.NIF_IVA, VerifySurface.TGVI])
@pytest.mark.parametrize("count", [0, 2])
def test_verify_branch_still_refuses_non_singleton_observations(
    surface: VerifySurface, count: int, monkeypatch: pytest.MonkeyPatch, offline_guard: OfflineGuard
) -> None:
    from ...adapters.outbound.aeat.sede import groi_check, nif_iva_check

    result = (
        nif_iva_check.NifIvaCheckResult(
            observations=(nif_iva_check.SedeNifIvaCheckObservation(nif=_NIF, verdict="valid"),) * count
        )
        if surface is VerifySurface.NIF_IVA
        else groi_check.GroiResult(observations=(groi_check.GroiNifVerdict(nif=_NIF, verdict="valid"),) * count)
    )

    async def collect(*_args: object, **_kwargs: object) -> nif_iva_check.NifIvaCheckResult | groi_check.GroiResult:
        return result

    owner = nif_iva_check if surface is VerifySurface.NIF_IVA else groi_check
    name = "collect_nif_iva_check_observations" if surface is VerifySurface.NIF_IVA else "collect_groi_observations"
    monkeypatch.setattr(owner, name, collect)
    with pytest.raises(ValueError, match="exactly one observation"):
        asyncio.run(
            operation_composition._acquire_registry_verify_observation(
                surface, _NIF, None, unread_authority_operation(), resolved_settings=Settings(_env_file=None)
            )
        )
    assert not offline_guard.refused
