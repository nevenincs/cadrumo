"""Unit tests for :class:`LiveSyncRunner` using concrete Protocol doubles.

No mocks or patches. Every dependency is a real Python class that
implements the stubbed Protocol with enough behaviour to drive the
runner.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest

from ...adapters.outbound.aeat.browser import BrowserSession
from . import (
    AdditiveAllowlistStrategy,
    BenignRecordStrategy,
    DivergenceClassifier,
    DivergenceKind,
    EscalateStrategy,
    HealingDispatcher,
    JsonFileDivergenceRepository,
    LiveSyncRunner,
    ModeloIdentifier,
    StrategyAction,
    SyncError,
    WireCasilla,
    WireFilingHistory,
    WireModeloDefinition,
    WirePortalManifest,
    WireValidationError,
    WireValidator,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


class _FakeCert:
    async def preload_into_browser_context(self, session: Any) -> None:
        return None


class _FakeSchema:
    modelo = ModeloIdentifier("100")


class _FakeSchemaLoader:
    def load(self, modelo: ModeloIdentifier) -> Any:
        return _FakeSchema()


class _FakeManualRulesLoader:
    def load(self, modelo: ModeloIdentifier) -> tuple[Any, ...]:
        return ()


class _FakeLLM:
    async def complete(self, request: Any) -> str:
        return ""


class _FakeLocalCatalogue:
    def __init__(
        self,
        *,
        modelo: WireModeloDefinition,
        manifest: WirePortalManifest,
        history: WireFilingHistory,
    ) -> None:
        self._modelo = modelo
        self._manifest = manifest
        self._history = history

    def load_modelo(self, modelo: ModeloIdentifier) -> WireModeloDefinition:
        return self._modelo

    def load_portal_manifest(self) -> WirePortalManifest:
        return self._manifest

    def load_filing_history(self, modelo: ModeloIdentifier) -> WireFilingHistory:
        return self._history


class _StaticFetcher:
    def __init__(
        self,
        *,
        modelo_raw: bytes,
        manifest_raw: bytes,
        history_raw: bytes,
    ) -> None:
        self._m = modelo_raw
        self._p = manifest_raw
        self._h = history_raw

    async def fetch_modelo_raw(self, *, session: Any, modelo: ModeloIdentifier) -> bytes:
        return self._m

    async def fetch_portal_manifest_raw(self, *, session: Any) -> bytes:
        return self._p

    async def fetch_filing_history_raw(self, *, session: Any, modelo: ModeloIdentifier) -> bytes:
        return self._h


class _FlakyFetcher(_StaticFetcher):
    def __init__(self, fail_times: int, **kwargs: bytes) -> None:
        super().__init__(**kwargs)
        self._fail_times = fail_times
        self._calls = 0

    async def fetch_modelo_raw(self, *, session: Any, modelo: ModeloIdentifier) -> bytes:
        self._calls += 1
        if self._calls <= self._fail_times:
            raise RuntimeError("transient flake")
        return await super().fetch_modelo_raw(session=session, modelo=modelo)


def _casilla(id_: str = "C1", default: str | None = "0", formula: str | None = None) -> WireCasilla:
    return WireCasilla.model_validate(
        {
            "id": id_,
            "label": {"es": "Base", "en": "Base", "hu": "Alap"},
            "type": "decimal",
            "default": default,
            "formula": formula,
        }
    )


def _modelo(
    casillas: tuple[WireCasilla, ...] = (_casilla(),),
    vigencia_end: date = date(2024, 12, 31),
) -> WireModeloDefinition:
    return WireModeloDefinition(
        modelo=ModeloIdentifier("100"),
        vigencia_start=date(2024, 1, 1),
        vigencia_end=vigencia_end,
        casillas=casillas,
    )


def _manifest() -> WirePortalManifest:
    from . import PortalIdentifier, WirePortalLink

    link = WirePortalLink.model_validate(
        {
            "url": "https://sede.agenciatributaria.gob.es/a",
            "label": {"es": "A", "en": "A", "hu": "A"},
            "modelo": "100",
        }
    )
    return WirePortalManifest(portal=PortalIdentifier("sede"), links=(link,))


def _history() -> WireFilingHistory:
    return WireFilingHistory(entries=())


def _dispatcher() -> HealingDispatcher:
    allowlist = frozenset(
        {
            DivergenceKind.CASILLA_ADDED_WITH_DEFAULT,
            DivergenceKind.LABEL_TRANSLATION_ADDED,
            DivergenceKind.VIGENCIA_EXTENDED,
        }
    )
    return HealingDispatcher(
        strategies=(
            BenignRecordStrategy(),
            AdditiveAllowlistStrategy(allowlist=allowlist),
            EscalateStrategy(),
        ),
        auto_heal_allowlist=allowlist,
    )


def _build_runner(
    *,
    local: _FakeLocalCatalogue,
    fetcher: Any,
    repository_root: Path,
) -> LiveSyncRunner:
    return LiveSyncRunner(
        browser_session=cast(BrowserSession, object()),
        certificate_backend=_FakeCert(),
        local_loader=local,
        schema_loader=_FakeSchemaLoader(),
        manual_rules_loader=_FakeManualRulesLoader(),
        llm_client=_FakeLLM(),
        fetcher=fetcher,
        validator=WireValidator(),
        classifier=DivergenceClassifier(),
        dispatcher=_dispatcher(),
        repository=JsonFileDivergenceRepository(repository_root),
        strategies=(),
        retry_max=3,
        retry_backoff_s=0.0,
    )


@pytest.mark.asyncio
async def test_runner_happy_path_emits_additive_healing(tmp_path: Path) -> None:
    local_modelo = _modelo()
    live_modelo = _modelo(vigencia_end=date(2025, 6, 30))
    fetcher = _StaticFetcher(
        modelo_raw=live_modelo.model_dump_json(by_alias=True).encode(),
        manifest_raw=_manifest().model_dump_json().encode(),
        history_raw=_history().model_dump_json().encode(),
    )
    local = _FakeLocalCatalogue(modelo=local_modelo, manifest=_manifest(), history=_history())
    runner = _build_runner(local=local, fetcher=fetcher, repository_root=tmp_path)

    result = await runner.run(modelo=ModeloIdentifier("100"), auto_heal=True)

    assert result.modelo == "100"
    assert len(result.plan.auto_heal) == 1
    assert result.plan.auto_heal[0].payload.kind == DivergenceKind.VIGENCIA_EXTENDED
    assert result.outcomes[0].action == StrategyAction.AUTO_HEALED


@pytest.mark.asyncio
async def test_runner_bounded_policy_blocks_breaking_even_with_auto_heal(
    tmp_path: Path,
) -> None:
    local_modelo = _modelo(casillas=(_casilla("C1"), _casilla("C2")))
    live_modelo = _modelo(casillas=(_casilla("C1"),))  # C2 removed → BREAKING
    fetcher = _StaticFetcher(
        modelo_raw=live_modelo.model_dump_json(by_alias=True).encode(),
        manifest_raw=_manifest().model_dump_json().encode(),
        history_raw=_history().model_dump_json().encode(),
    )
    local = _FakeLocalCatalogue(modelo=local_modelo, manifest=_manifest(), history=_history())
    runner = _build_runner(local=local, fetcher=fetcher, repository_root=tmp_path)

    result = await runner.run(modelo=ModeloIdentifier("100"), auto_heal=True)

    assert result.plan.auto_heal == ()
    assert len(result.plan.escalate) == 1
    assert result.plan.escalate[0].payload.kind == DivergenceKind.CASILLA_REMOVED


@pytest.mark.asyncio
async def test_runner_wire_validation_failure_raises(tmp_path: Path) -> None:
    fetcher = _StaticFetcher(
        modelo_raw=b"not-json",
        manifest_raw=_manifest().model_dump_json().encode(),
        history_raw=_history().model_dump_json().encode(),
    )
    local = _FakeLocalCatalogue(modelo=_modelo(), manifest=_manifest(), history=_history())
    runner = _build_runner(local=local, fetcher=fetcher, repository_root=tmp_path)

    with pytest.raises(WireValidationError):
        await runner.run(modelo=ModeloIdentifier("100"), auto_heal=False)


@pytest.mark.asyncio
async def test_runner_retries_transient_fetch_failures(tmp_path: Path) -> None:
    local_modelo = _modelo()
    live = _modelo(vigencia_end=date(2025, 6, 30))
    fetcher = _FlakyFetcher(
        fail_times=2,
        modelo_raw=live.model_dump_json(by_alias=True).encode(),
        manifest_raw=_manifest().model_dump_json().encode(),
        history_raw=_history().model_dump_json().encode(),
    )
    local = _FakeLocalCatalogue(modelo=local_modelo, manifest=_manifest(), history=_history())
    runner = _build_runner(local=local, fetcher=fetcher, repository_root=tmp_path)

    result = await runner.run(modelo=ModeloIdentifier("100"), auto_heal=True)
    assert len(result.plan.auto_heal) == 1


@pytest.mark.asyncio
async def test_runner_gives_up_after_retry_max(tmp_path: Path) -> None:
    fetcher = _FlakyFetcher(
        fail_times=99,
        modelo_raw=_modelo().model_dump_json(by_alias=True).encode(),
        manifest_raw=_manifest().model_dump_json().encode(),
        history_raw=_history().model_dump_json().encode(),
    )
    local = _FakeLocalCatalogue(modelo=_modelo(), manifest=_manifest(), history=_history())
    runner = _build_runner(local=local, fetcher=fetcher, repository_root=tmp_path)

    with pytest.raises(SyncError):
        await runner.run(modelo=ModeloIdentifier("100"), auto_heal=False)
