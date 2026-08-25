"""Browser-automation, live-IVA, and exchange-rate timeout settings.

Split from :mod:`core.config` to keep that module within the line budget.
:class:`~core.config.Settings` inherits these fields, so every timeout
still reads the same ``CADRUMO_*`` environment variable by field name and is
unchanged at runtime.

The browser cleanup and Cl@ve approval budgets are consumed by
:class:`~adapters.outbound.aeat.auth.clave_movil.ClaveMovilAuthProvider`.
The live IVA surface, filed-register, cancellation-drain, and CLI watchdog
budgets are consumed by :mod:`application.live._iva_remote_state`,
:mod:`application.live._filed_data_capture`, and the
:func:`~entrypoints.cli._app_live._run_live_iva_evidence_pull_command`
watchdog. The exchange-rate lookup budget is consumed by
:class:`~adapters.outbound.fx.EcbReferenceRateProvider`.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class CadrumoTimeoutSettings(BaseSettings):
    """Playwright browser-stage and live-IVA surface timeout fields.

    :class:`~core.config.Settings` mixes in this base class so these fields
    remain part of the central environment authority while the timeout catalogue
    stays separated from the rest of the settings facade.
    """

    cadrumo_browser_navigation_timeout_ms: int = Field(
        default=30_000,
        gt=0,
        description="Default Playwright navigation timeout (milliseconds) for AEAT sede pages",
    )
    cadrumo_browser_form_interaction_timeout_ms: int = Field(
        default=10_000,
        gt=0,
        description="Timeout for individual form interactions (fill/click/wait) in milliseconds",
    )
    cadrumo_browser_ver_click_timeout_ms: int = Field(
        default=15_000,
        gt=0,
        description="Timeout (ms) for the AEAT declarations 'Ver' button click and navigation",
    )
    cadrumo_browser_buscar_settle_ms: int = Field(
        default=3_000,
        gt=0,
        description="Settle delay (ms) after the AEAT 'Buscar' button before reading the results table",
    )
    cadrumo_browser_selector_probe_timeout_ms: int = Field(
        default=2_500,
        gt=0,
        description="Selector visibility probe timeout (ms) used by GROI/NIF-IVA check stages",
    )
    cadrumo_browser_close_timeout_ms: int = Field(
        default=5_000,
        gt=0,
        description=(
            "Best-effort timeout (ms) for Playwright browser context/session cleanup during AEAT live "
            "auth and read flows. Cleanup must not leave a command hanging after the primary operation "
            "has already failed or timed out."
        ),
    )
    cadrumo_live_iva_surface_timeout_ms: int = Field(
        default=180_000,
        gt=0,
        description=(
            "Outer timeout (ms) for each live IVA read surface inside a combined remote-state "
            "acquisition. Individual browser stages have their own shorter timeouts; this bounds "
            "the whole filed-history or wallet/cartera surface."
        ),
    )
    cadrumo_live_iva_declaration_capture_timeout_ms: int = Field(
        default=120_000,
        gt=0,
        description=(
            "Timeout (ms) for one Modelo 303 filed-declaration observation inside a combined "
            "live IVA filed-history read. Must be lower than the outer live IVA surface timeout "
            "so partial filed-history failures can return a structured report before the whole "
            "surface is cancelled."
        ),
    )
    cadrumo_live_filed_register_walk_timeout_ms: int = Field(
        default=30_000,
        gt=0,
        description=(
            "Timeout (ms) for one AEAT filed-declaration register query for a single modelo/year. "
            "Bulk filed-history reads use this per-query budget so one slow modelo cannot block "
            "all later modelos from returning typed failures."
        ),
    )
    cadrumo_live_iva_cancellation_drain_ms: int = Field(
        default=250,
        ge=0,
        description=(
            "Drain delay (ms) after a bounded live IVA read surface is cancelled, giving Playwright "
            "browser tasks time to report cancellation-only errors before the loop handler is restored."
        ),
    )
    cadrumo_live_iva_cli_watchdog_timeout_ms: int = Field(
        default=240_000,
        gt=0,
        description=(
            "Top-level CLI watchdog timeout (ms) for the combined read-only IVA remote-state command. "
            "This must exceed the normal auth and surface budgets but remain below operator shell/tool "
            "timeouts so the CLI can cancel and clean up inside its own process."
        ),
    )
    cadrumo_fx_rate_lookup_timeout_s: int = Field(
        default=15,
        gt=0,
        description=(
            "Timeout (seconds) for one ECB Data Portal euro reference-rate lookup. A ledger import "
            "resolves one lookup per distinct currency/date, so this budget bounds a single "
            "observation query rather than the whole import."
        ),
    )

