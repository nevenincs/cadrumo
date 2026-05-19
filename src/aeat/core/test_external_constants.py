"""Tests for the external-constants registry and tunable-Settings split."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeat.core.config import Settings
from aeat.core.external_constants import ExternalConstants, load_external_constants

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def test_load_external_constants_returns_typed_model() -> None:
    """The loader yields a fully-validated :class:`ExternalConstants`."""

    constants = load_external_constants()

    assert isinstance(constants, ExternalConstants)


def test_load_external_constants_is_cached() -> None:
    """Repeat calls return the identical cached instance."""

    assert load_external_constants() is load_external_constants()


def test_settings_facade_returns_same_registry() -> None:
    """``Settings.external_constants()`` is the canonical accessor."""

    assert Settings.external_constants() is load_external_constants()


def test_aeat_domains_are_absolute_https_urls() -> None:
    """Every AEAT/government domain entry is an absolute HTTPS origin."""

    domains = load_external_constants().aeat.domains

    for value in (domains.sede, domains.www1, domains.www2, domains.www6, domains.clave, domains.boe):
        assert value.startswith("https://")
        assert "://" in value


def test_aeat_sede_paths_are_absolute_paths() -> None:
    """Every sede service path is rooted at ``/``."""

    paths = load_external_constants().aeat.sede_paths

    for value in (
        paths.expedientes_resumen,
        paths.declarations_listing,
        paths.cotejo_query,
        paths.cotejo_document,
        paths.notifications_summary,
        paths.notifications_query,
        paths.certificate_selector,
        paths.notificaciones,
        paths.iva_compensation_wallet,
    ):
        assert value.startswith("/")


def test_clave_movil_surface_constants_are_typed() -> None:
    """Cl@ve Móvil URL fragments and selectors live in the external registry."""

    surface = load_external_constants().aeat.clave_movil

    assert "{target}" in surface.selector_access_url_template
    assert surface.selector_access_path_marker
    assert surface.dialogo_representacion_path_marker
    assert surface.obtener_clave_movil_path_marker
    assert surface.obtener_clave_movil_qr_path_marker
    assert surface.authorize_button_selector.startswith("button")
    assert surface.non_qr_link_selector.startswith("a[")
    assert surface.verification_code_selector.startswith("#")
    assert surface.wait_text_markers
    assert surface.pending_petition_text_markers


def test_renta_web_open_template_has_year_placeholder() -> None:
    """The Renta WEB Open template parameterises the fiscal year."""

    template = load_external_constants().aeat.oracles.renta_web_open_app_template

    assert "{year}" in template
    formatted = template.format(year=2026)
    assert "EJER=2026" in formatted


def test_expediente_detail_template_has_id_placeholder() -> None:
    """The expediente detail path template parameterises the expediente id."""

    template = load_external_constants().aeat.sede_paths.expediente_detail_template

    assert "{expediente_id}" in template


def test_subdomain_enum_aligns_with_aeat_domains() -> None:
    """The :class:`Subdomain` enum hosts mirror the TOML registry hosts."""

    from aeat.domain.portals._categories import Subdomain

    domains = load_external_constants().aeat.domains

    assert Subdomain.SEDE.value == domains.sede.removeprefix("https://")
    assert Subdomain.WWW1.value == domains.www1.removeprefix("https://")
    assert Subdomain.WWW2.value == domains.www2.removeprefix("https://")
    assert Subdomain.CLAVE_GOB.value == domains.clave.removeprefix("https://")


def test_browser_timeouts_belong_to_settings_not_registry() -> None:
    """Browser timeouts are runtime-tunable :class:`Settings` fields, not registry constants."""

    constants = load_external_constants()

    assert not hasattr(constants.aeat, "timeouts_ms")
    settings = Settings()
    assert settings.aeat_browser_navigation_timeout_ms == 30_000
    assert settings.aeat_browser_form_interaction_timeout_ms == 10_000
    assert settings.aeat_browser_ver_click_timeout_ms == 15_000
    assert settings.aeat_browser_buscar_settle_ms == 3_000
    assert settings.aeat_browser_selector_probe_timeout_ms == 2_500


def test_llm_endpoints_belong_to_settings_not_registry() -> None:
    """LLM provider URLs are operator-tunable Settings, not registry constants."""

    constants = load_external_constants()

    assert not hasattr(constants.online_services, "llm_endpoints")
    settings = Settings()
    assert settings.aeat_llm_openai_chat_completions_url.startswith("https://api.openai.com")
    assert "{model}" in settings.aeat_llm_gemini_generate_content_template
    assert settings.aeat_llm_ollama_chat_url.startswith("http://")


def test_browser_context_defaults_are_tunable_settings() -> None:
    """Browser locale, timezone, and viewport flow from Settings."""

    settings = Settings()

    assert settings.aeat_browser_locale == "es-ES"
    assert settings.aeat_browser_timezone == "Europe/Madrid"
    assert settings.aeat_browser_viewport_width == 1366
    assert settings.aeat_browser_viewport_height == 900


def test_file_lock_and_polling_defaults_are_tunable_settings() -> None:
    """File-lock timing and polling intervals are runtime-tunable."""

    settings = Settings()

    assert settings.aeat_file_lock_timeout_s == 30.0
    assert settings.aeat_file_lock_retry_backoff_s == 0.05
    assert settings.aeat_bucket_lock_poll_interval_s == 0.1
    assert settings.aeat_bucket_default_idle_lock_minutes == 15


def test_auth_acquisition_lock_tunables_are_settings() -> None:
    """Auth acquisition lock TTLs are runtime-tunable."""

    settings = Settings()

    assert settings.aeat_auth_clave_movil_lock_buffer_s == 90
    assert settings.aeat_auth_certificate_lock_ttl_s == 180


def test_clave_movil_operator_wait_is_capped_at_two_minutes() -> None:
    """Cl@ve Móvil approval waits fail fast enough for production retry loops."""

    assert Settings().aeat_clave_movil_timeout_ms == 120_000

    with pytest.raises(ValidationError):
        Settings(aeat_clave_movil_timeout_ms=120_001)


def test_logging_levels_are_tunable_settings() -> None:
    """Log handler levels surface as runtime-tunable Settings."""

    settings = Settings()

    assert settings.aeat_log_stderr_level == "ERROR"
    assert settings.aeat_log_file_level == "DEBUG"
    assert settings.aeat_log_root_level == "DEBUG"


def test_google_integration_tunables_are_settings() -> None:
    """Google Drive folder name and OAuth refresh buffer are tunable."""

    settings = Settings()

    assert settings.aeat_google_drive_vault_folder_name == "aeat-vault"
    assert settings.aeat_google_oauth_access_refresh_buffer_s == 300


def test_workbook_parity_tunables_are_settings() -> None:
    """Workbook-parity timeouts are runtime-tunable."""

    settings = Settings()

    assert settings.aeat_workbook_parity_per_file_timeout_s == 15.0
    assert settings.aeat_workbook_parity_recalc_timeout_s == 60
    assert settings.aeat_workbook_parity_libreoffice_timeout_s == 120
    assert settings.aeat_calc_sheets_recalc_delay_s == 2.0


def test_llm_default_completion_knobs_are_settings() -> None:
    """LLM default ``max_tokens`` and ``temperature`` are runtime-tunable."""

    settings = Settings()

    assert settings.aeat_llm_default_max_tokens == 1024
    assert settings.aeat_llm_default_temperature == 0.0


def test_manuals_http_timeout_is_settings() -> None:
    """Manual PDF download timeout is runtime-tunable."""

    settings = Settings()

    assert settings.aeat_manuals_http_timeout_s == 60.0
