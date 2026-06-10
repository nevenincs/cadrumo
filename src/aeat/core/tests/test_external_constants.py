"""Tests for the external-constants registry and tunable-Settings split."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...tests.aeat_literal_fixtures import (
    AEAT_HOST_SUFFIX_EXPECTED,
    AEAT_LITERAL_SCAN_TOKENS,
    CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED,
    PORTAL_LITERAL_SCAN_TOKENS,
    REMOTE_GUARD_LITERAL_SCAN_TOKENS,
)
from ..config import Settings
from ..errors import CoreValidationError
from ..external_constants import (
    AeatSection,
    ExternalConstants,
    load_external_constants,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _registry_toml_payload() -> dict[str, object]:
    """Return the bundled ``external_constants.toml`` parsed to a mapping."""

    toml_path = Path(__file__).parents[1] / "external_constants.toml"
    return tomllib.loads(toml_path.read_text(encoding="utf-8"))


def _aeat_section(payload: dict[str, object]) -> dict[str, object]:
    """Return the mutable ``[aeat]`` table from a parsed registry payload."""

    section = payload["aeat"]
    assert isinstance(section, dict), "registry payload is missing a [aeat] table"
    typed_section: dict[str, object] = {str(key): value for key, value in section.items()}
    payload["aeat"] = typed_section
    return typed_section


def _is_docstring_node(node: ast.Module | ast.ClassDef | ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    return (
        bool(node.body)
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )


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

    assert domains.host_suffix == AEAT_HOST_SUFFIX_EXPECTED
    for value in (
        domains.sede,
        domains.www1,
        domains.www2,
        domains.www3,
        domains.www6,
        domains.www12,
        domains.aeat_gob,
        domains.legacy_www,
        domains.clave,
        domains.boe,
    ):
        assert value.startswith("https://")
        assert "://" in value


def test_aeat_sede_paths_are_absolute_paths() -> None:
    """Every sede service path is rooted at ``/``."""

    paths = load_external_constants().aeat.sede_paths

    for value in (
        paths.auth_gate_4033,
        paths.expedientes_resumen,
        paths.declarations_listing,
        paths.cotejo_query,
        paths.cotejo_document,
        paths.notifications_summary,
        paths.notifications_query,
        paths.certificate_selector,
        paths.censo_g313_launcher,
        paths.irpf_expediente_detail_year_prefix,
        paths.notificaciones,
        paths.iva_compensation_wallet,
    ):
        assert value.startswith("/")
    assert paths.irpf_expediente_detail_year_suffix


def test_clave_movil_surface_constants_are_typed() -> None:
    """Cl@ve Móvil URL fragments and selectors live in the external registry."""

    surface = load_external_constants().aeat.clave_movil

    assert "{target}" in surface.selector_access_url_template
    assert surface.selector_access_path_marker
    assert surface.dialogo_representacion_path_marker
    assert surface.dialogo_representacion_path.startswith("/")
    assert surface.obtener_clave_movil_path_marker
    assert surface.obtener_clave_movil_qr_path_marker
    assert surface.cancelar_clave_movil_path_marker
    assert surface.obtener_clave_movil_qr_path.startswith("/")
    assert surface.obtener_clave_movil_non_qr_path.startswith("/")
    assert surface.autentica_dni_nie_contraste_path.startswith("/")
    assert surface.cancelar_clave_movil_path.startswith("/")
    assert surface.obtener_clave_movil_browser_global == CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED
    assert surface.authorize_button_selector.startswith("button")
    assert surface.non_qr_link_selector.startswith("a[")
    assert surface.verification_code_selector.startswith("#")
    assert surface.wait_text_markers
    assert surface.pending_petition_text_markers


def test_pre303_surface_constants_are_typed() -> None:
    """Pre303 wallet route, documentation, and parser markers live in the external registry."""

    surface = load_external_constants().aeat.pre303

    for path in (
        surface.presentation_service_path,
        surface.access_help_path,
        surface.faq_general_path,
        surface.faq_specific_path,
        surface.functionalities_path,
        surface.procedures_path,
    ):
        assert path.startswith("/")
    assert "forigen=pre303" in surface.presentation_service_path
    assert "erro4033" in load_external_constants().aeat.sede_paths.auth_gate_4033
    assert "ejercicio" in surface.iva_wallet_header_tokens
    assert "disponible" in surface.iva_wallet_header_tokens
    assert "pendientes" in surface.iva_wallet_total_label_tokens
    assert "cartera" in surface.iva_wallet_empty_page_tokens
    assert surface.wallet_form_selector.startswith("form")
    assert surface.wallet_execute_submit_selector.startswith("input")
    assert surface.tipo_actuacion_own_name_link_selector.startswith("a")
    assert surface.wallet_ejercicio_input_selector.startswith("input")
    assert surface.wallet_periodo_input_selector.startswith("input")
    assert surface.representation_own_name_selector
    assert surface.representation_own_name_label_selector
    wallet_actions = load_external_constants().aeat.live_safety.wallet_browser_action_patterns
    assert surface.representation_own_name_action_label in wallet_actions
    assert surface.wallet_discovered_entrypoint_action_label in wallet_actions
    assert surface.wallet_execute_read_action_label in wallet_actions
    assert "clave PIN" in surface.official_access_auth_methods


def test_manual_and_oracle_auxiliary_routes_are_centralized() -> None:
    """Manual corpus paths and cross-oracle auth diagnostics live in TOML."""

    constants = load_external_constants().aeat

    assert constants.help_pages.manual_practicos_root.startswith("/")
    assert constants.help_pages.manual_practicos_root == constants.help_pages.manual_practicos_root.strip()
    assert constants.oracles.groi_auth_unlock_descriptor
    assert constants.oracles.nif_iva_auth_locked_descriptor


def test_live_safety_action_patterns_are_centralized() -> None:
    """Audited live AEAT browser-action labels live in the external registry."""

    safety = load_external_constants().aeat.live_safety
    pre303 = load_external_constants().aeat.pre303

    assert "clave-movil-authorize" in safety.auth_browser_action_patterns
    assert pre303.wallet_discovered_entrypoint_action_label in safety.wallet_browser_action_patterns
    assert pre303.wallet_execute_read_action_label in safety.wallet_browser_action_patterns
    assert "buscar-declaraciones-presentadas" in safety.declarations_browser_action_patterns
    assert "csv-verifier-query" in safety.csv_verify_browser_action_patterns
    assert "check-nif-*" in safety.consult_oracle_browser_action_patterns
    assert "requires-renta-web-open-driver" in safety.renta_web_open_browser_action_patterns
    assert "accept-identification" in safety.renta_web_open_browser_action_patterns


def test_missing_pre303_block_does_not_poison_registry_parsing() -> None:
    """A registry payload with no ``[aeat.pre303]`` block still validates.

    Regression guard: the ``pre303`` section is the most volatile part of
    the registry (AEAT-portal scraping selectors). It must validate
    lazily so a half-landed change that adds pre303 model fields without
    the matching TOML data cannot break registry parsing — and therefore
    cannot break the ``Settings()`` construction that resolves AEAT-URL
    defaults through :func:`load_external_constants`.
    """

    payload = _registry_toml_payload()
    _aeat_section(payload).pop("pre303", None)

    constants = ExternalConstants.model_validate(payload)

    assert isinstance(constants, ExternalConstants)
    assert constants.aeat.domains.sede.startswith("https://")


def test_missing_pre303_block_keeps_settings_construction_alive() -> None:
    """``Settings()`` survives even when the volatile pre303 block is absent.

    Drives the real failure mode reported as a CLI-wide crash: a
    pre303-less registry must not raise a raw ``ValidationError`` out of
    a ``Settings()`` default factory. Selector-free commands such as
    ``config profile status`` and ``modelo list`` never touch pre303.
    """

    payload = _registry_toml_payload()
    aeat_section = _aeat_section(payload)
    aeat_section.pop("pre303", None)
    section = AeatSection.model_validate(aeat_section)

    # The AEAT-URL default factories Settings() depends on only read
    # domains / sede_paths / clave_movil — all present without pre303.
    assert section.domains.sede.startswith("https://")
    assert section.sede_paths.expedientes_resumen.startswith("/")
    assert "{target}" in section.clave_movil.selector_access_url_template

    settings = Settings()
    assert settings.aeat_base_url.startswith("https://")


def test_malformed_pre303_block_surfaces_clean_translated_error() -> None:
    """Accessing a malformed pre303 surface raises a clean ``CoreValidationError``.

    Anti-tautology proof: without lazy validation a malformed pre303
    block raises a raw ``pydantic.ValidationError`` during registry
    parsing. With the lazy boundary in place, registry parsing succeeds
    and the failure is deferred to — and only to — the consumers that
    actually access ``.aeat.pre303``, wrapped in the structured
    :class:`CoreValidationError` contract.
    """

    payload = _registry_toml_payload()
    _aeat_section(payload)["pre303"] = {"presentation_service_path": ""}

    constants = ExternalConstants.model_validate(payload)
    assert isinstance(constants, ExternalConstants)  # parsing must not raise

    with pytest.raises(CoreValidationError) as excinfo:
        _ = constants.aeat.pre303

    assert excinfo.value.context is not None
    assert excinfo.value.context["section"] == "aeat.pre303"


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


def test_sede_parser_route_shapes_are_centralized() -> None:
    """Expediente and cotejo parser route fragments are TOML-backed."""

    paths = load_external_constants().aeat.sede_paths

    raw_paths = _aeat_section(_registry_toml_payload())["sede_paths"]
    assert isinstance(raw_paths, dict)
    registry_paths = {str(key): value for key, value in raw_paths.items()}
    assert paths.irpf_expediente_detail_year_prefix == registry_paths["irpf_expediente_detail_year_prefix"]
    assert paths.irpf_expediente_detail_year_suffix.endswith("Vlt")
    assert paths.cotejo_query == registry_paths["cotejo_query"]
    assert paths.cotejo_document == registry_paths["cotejo_document"]


def test_live_sede_executable_route_literals_stay_centralized() -> None:
    """Live AEAT executable code must read volatile routes from the registry."""

    repo_root = Path(__file__).parents[4]
    checked_paths = (
        repo_root / "src/aeat/core/config.py",
        repo_root / "src/aeat/adapters/outbound/aeat/auth/_clave_movil.py",
        repo_root / "src/aeat/adapters/outbound/aeat/sede/_groi_check.py",
        repo_root / "src/aeat/adapters/outbound/aeat/sede/_nif_iva_check.py",
        repo_root / "src/aeat/adapters/outbound/aeat/sede/_declarations.py",
        repo_root / "src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
        repo_root / "src/aeat/adapters/outbound/aeat/sede/_parse.py",
        repo_root / "src/aeat/adapters/outbound/aeat/verify/__init__.py",
        repo_root / "src/aeat/domain/manuals/_fetch.py",
    )
    volatile_tokens = AEAT_LITERAL_SCAN_TOKENS

    offenders: list[str] = []
    for path in checked_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring_nodes = {
            doc_node
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.AsyncFunctionDef | ast.FunctionDef)
            for doc_node in ([node.body[0]] if _is_docstring_node(node) else [])
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if any(node is getattr(doc_node, "value", None) for doc_node in docstring_nodes):
                continue
            if any(token in node.value for token in volatile_tokens):
                offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}: {node.value!r}")

    assert offenders == []


def test_subdomain_enum_aligns_with_aeat_domains() -> None:
    """Portal host keys resolve to the TOML registry hosts."""

    from ...domain.portals._categories import PortalHost
    from ...domain.portals._hosts import portal_host_name

    domains = load_external_constants().aeat.domains
    configured_hosts = {
        domains.sede.removeprefix("https://"),
        domains.www1.removeprefix("https://"),
        domains.www2.removeprefix("https://"),
        domains.www3.removeprefix("https://"),
        domains.aeat_gob.removeprefix("https://"),
        domains.legacy_www.removeprefix("https://"),
        domains.clave.removeprefix("https://"),
    }

    assert portal_host_name(PortalHost.SEDE) == domains.sede.removeprefix("https://")
    assert portal_host_name(PortalHost.WWW1) == domains.www1.removeprefix("https://")
    assert portal_host_name(PortalHost.WWW2) == domains.www2.removeprefix("https://")
    assert portal_host_name(PortalHost.WWW3) == domains.www3.removeprefix("https://")
    assert portal_host_name(PortalHost.AGENCIATRIBUTARIA_GOB) == domains.aeat_gob.removeprefix("https://")
    assert portal_host_name(PortalHost.AGENCIATRIBUTARIA_ES) == domains.legacy_www.removeprefix("https://")
    assert portal_host_name(PortalHost.CLAVE_GOB) == domains.clave.removeprefix("https://")
    assert {portal_host_name(subdomain) for subdomain in PortalHost} <= configured_hosts


def test_portal_paths_registry_covers_literal_free_portal_entries() -> None:
    """Portal catalogue route paths are owned by external constants."""

    from ...domain.portals._codes import Portal
    from ...domain.portals._entries._common import portal_path

    constants = load_external_constants().aeat
    assert re.compile(constants.portal_paths.filing_censo_path_regex)
    assert constants.portal_paths.filing_censo_path_description
    assert set(constants.portal_paths.paths) == {portal.value for portal in Portal} - {
        Portal.PORTAL_MIS_DATOS_CENSALES.value,
        Portal.PORTAL_PRE303_AYUDA.value,
    }
    for portal_id, path in constants.portal_paths.paths.items():
        assert path.startswith("/")
        assert portal_path(Portal(portal_id)) == path


def test_portal_registry_modules_do_not_reintroduce_route_or_host_literals() -> None:
    """Portal catalogue modules must resolve AEAT hosts and paths through central constants."""

    repo_root = Path(__file__).parents[4]
    portal_root = repo_root / "src/aeat/domain/portals"
    volatile_tokens = PORTAL_LITERAL_SCAN_TOKENS
    allowed_files = {
        portal_root / "_hosts.py",
    }

    offenders: list[str] = []
    for path in sorted(portal_root.rglob("*.py")):
        if path.name.startswith("test_") or path in allowed_files:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring_nodes = {
            doc_node
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.AsyncFunctionDef | ast.FunctionDef)
            for doc_node in ([node.body[0]] if _is_docstring_node(node) else [])
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if any(node is getattr(doc_node, "value", None) for doc_node in docstring_nodes):
                continue
            value = node.value
            is_entry_root_path = path.parent.name == "_entries" and path.name != "_common.py" and value == "/"
            if is_entry_root_path or any(token in value for token in volatile_tokens):
                offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}: {value!r}")

    assert offenders == []


def test_remote_guard_parity_and_oracle_tests_use_declared_aeat_literal_fixtures() -> None:
    """Remote guard/parity/oracle tests must import configured URLs or declared canaries."""

    repo_root = Path(__file__).parents[4]
    checked_paths = (
        repo_root / "src/aeat/domain/calculations/registry/tests/test_remote_state_guard.py",
        repo_root / "src/aeat/domain/calculations/registry/tests/test_live_parity.py",
        repo_root / "src/aeat/domain/calculations/registry/tests/test_groi_oracle.py",
        repo_root / "src/aeat/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py",
    )
    volatile_tokens = REMOTE_GUARD_LITERAL_SCAN_TOKENS
    offenders: list[str] = []
    for path in checked_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring_nodes = {
            doc_node
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.AsyncFunctionDef | ast.FunctionDef)
            for doc_node in ([node.body[0]] if _is_docstring_node(node) else [])
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if any(node is getattr(doc_node, "value", None) for doc_node in docstring_nodes):
                continue
            if any(token in node.value for token in volatile_tokens):
                offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}: {node.value!r}")

    assert offenders == []


def test_test_suite_aeat_route_literals_are_centralized_or_declared() -> None:
    """Test modules must not own executable AEAT/Sede host or route literals."""

    repo_root = Path(__file__).parents[4]
    aeat_root = repo_root / "src/aeat"
    allowed_files = {
        Path(__file__),
        repo_root / "src/aeat/tests/aeat_literal_fixtures.py",
    }
    volatile_tokens = tuple(
        dict.fromkeys(
            (
                *AEAT_LITERAL_SCAN_TOKENS,
                "agenciatributaria.es",
                "clave.gob.es",
            )
        )
    )

    checked_paths = sorted(
        {
            *aeat_root.rglob("test_*.py"),
            *aeat_root.rglob("*_test.py"),
            *aeat_root.rglob("conftest.py"),
        }
    )
    offenders: list[str] = []
    for path in checked_paths:
        if path in allowed_files:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring_nodes = {
            doc_node
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.AsyncFunctionDef | ast.FunctionDef)
            for doc_node in ([node.body[0]] if _is_docstring_node(node) else [])
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if any(node is getattr(doc_node, "value", None) for doc_node in docstring_nodes):
                continue
            if any(token in node.value for token in volatile_tokens):
                offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}: {node.value!r}")

    assert offenders == []


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
    assert settings.aeat_browser_close_timeout_ms == 5_000
    assert settings.aeat_live_iva_declaration_capture_timeout_ms == 120_000
    assert settings.aeat_live_iva_declaration_capture_timeout_ms < settings.aeat_live_iva_surface_timeout_ms
    assert settings.aeat_live_iva_cli_watchdog_timeout_ms == 240_000
    assert settings.aeat_live_iva_cli_watchdog_timeout_ms < 300_000


def test_live_iva_declaration_timeout_must_leave_outer_surface_headroom() -> None:
    """One declaration timeout must fire before the whole filed-history surface timeout."""

    with pytest.raises(ValueError, match="aeat_live_iva_declaration_capture_timeout_ms"):
        Settings(
            aeat_live_iva_declaration_capture_timeout_ms=180_000,
            aeat_live_iva_surface_timeout_ms=180_000,
        )


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
