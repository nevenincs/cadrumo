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

    registry_paths = _aeat_section(_registry_toml_payload())["sede_paths"]
    assert isinstance(registry_paths, dict)
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


# ---------------------------------------------------------------------------
# contract — BINARY_MIME_TYPE centralisation tests
# ---------------------------------------------------------------------------


def test_binary_mime_type_value() -> None:
    """``BINARY_MIME_TYPE`` equals the IANA-registered opaque-binary MIME type."""

    from ..external_constants import BINARY_MIME_TYPE

    assert BINARY_MIME_TYPE == "application/octet-stream"


def test_google_drive_reads_binary_mime_from_external_constants() -> None:
    """The Google Drive adapter imports ``BINARY_MIME_TYPE`` rather than a local literal."""

    import importlib
    import importlib.util

    from ..external_constants import BINARY_MIME_TYPE

    spec = importlib.util.find_spec("aeat.adapters.outbound.storage._google_drive")
    assert spec is not None, "_google_drive module not found"
    mod = importlib.import_module("aeat.adapters.outbound.storage._google_drive")

    # The module-level alias resolves to the canonical constant.
    assert mod._BINARY_MIME_TYPE is BINARY_MIME_TYPE


# ---------------------------------------------------------------------------
# contract / contract — DEFAULT_CURRENCY centralisation tests
# ---------------------------------------------------------------------------


def test_default_currency_value() -> None:
    """``DEFAULT_CURRENCY`` equals the ISO 4217 Euro code."""

    from ..external_constants import DEFAULT_CURRENCY

    assert DEFAULT_CURRENCY == "EUR"


def test_default_currency_is_final_str() -> None:
    """``DEFAULT_CURRENCY`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import DEFAULT_CURRENCY

    assert isinstance(DEFAULT_CURRENCY, str)


def test_ledger_transaction_command_reads_currency_from_external_constants() -> None:
    """The manual ledger transaction command default currency comes from ``DEFAULT_CURRENCY``."""

    # Construct with no explicit currency — the field default must resolve to DEFAULT_CURRENCY.
    # We verify by inspecting that the module imports DEFAULT_CURRENCY (not a local literal).
    from ...application.ledger import _models as _models_mod
    from ...application.ledger._models import ManualLedgerTransactionCommand
    from ..external_constants import DEFAULT_CURRENCY

    assert hasattr(_models_mod, "DEFAULT_CURRENCY"), (
        "_models module must import DEFAULT_CURRENCY from external_constants"
    )
    assert _models_mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY

    # Also verify the field default is not a hardcoded literal in the model schema.
    schema = ManualLedgerTransactionCommand.model_json_schema()
    props = schema.get("properties", {})
    currency_prop = props.get("currency", {})
    assert currency_prop.get("default") == DEFAULT_CURRENCY


def test_currency_service_reads_native_eur_from_external_constants() -> None:
    """The currency normalisation service uses ``DEFAULT_CURRENCY`` for native EUR check."""

    from ...domain.currency import _service as _service_mod
    from ..external_constants import DEFAULT_CURRENCY

    assert hasattr(_service_mod, "DEFAULT_CURRENCY"), (
        "_service module must import DEFAULT_CURRENCY from external_constants"
    )
    assert _service_mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY


def test_aggregation_predicates_read_currency_from_external_constants() -> None:
    """The aggregation currency predicate uses ``DEFAULT_CURRENCY``, not a local literal."""

    from ...application.aggregation import _currency_predicates as _pred_mod
    from ..external_constants import DEFAULT_CURRENCY

    assert hasattr(_pred_mod, "DEFAULT_CURRENCY"), (
        "_currency_predicates must import DEFAULT_CURRENCY from external_constants"
    )
    assert _pred_mod.DEFAULT_CURRENCY is DEFAULT_CURRENCY


def test_config_financial_base_currency_default_equals_default_currency() -> None:
    """``Settings.financial_base_currency`` default equals ``DEFAULT_CURRENCY``."""

    from ..config import Settings
    from ..external_constants import DEFAULT_CURRENCY

    settings = Settings()
    assert settings.financial_base_currency == DEFAULT_CURRENCY


def test_blob_store_put_default_content_type_reads_from_external_constants() -> None:
    """``EncryptedBlobStore.put`` default ``content_type`` is bound to ``BINARY_MIME_TYPE``."""

    import inspect

    from ...adapters.persistence.storage.blob_store._blob_store import EncryptedBlobStore
    from ..external_constants import BINARY_MIME_TYPE

    sig = inspect.signature(EncryptedBlobStore.put)
    default = sig.parameters["content_type"].default
    assert default == BINARY_MIME_TYPE


def test_declarations_filed_artefact_uses_binary_mime_constant() -> None:
    """``FiledDeclaracionArtefact`` content_type field no longer carries a raw literal.

    We assert that the module imports ``BINARY_MIME_TYPE`` from
    ``aeat.core.external_constants`` and that the imported value equals the
    expected MIME type, giving a transitive identity guarantee without
    executing the live AEAT browser path.
    """

    import importlib

    from ..external_constants import BINARY_MIME_TYPE

    mod = importlib.import_module("aeat.adapters.outbound.aeat.sede._declarations")

    # The module must expose the constant under the local alias used at the call site.
    assert mod._BINARY_MIME_TYPE is BINARY_MIME_TYPE
    assert mod._BINARY_MIME_TYPE == "application/octet-stream"


# ---------------------------------------------------------------------------
# contract / contract / contract — CLASSIFIED_BY_MANUAL single-source-of-truth tests
# ---------------------------------------------------------------------------


def test_classified_by_manual_value() -> None:
    """``CLASSIFIED_BY_MANUAL`` equals the sentinel stored in persisted records."""

    from ..external_constants import CLASSIFIED_BY_MANUAL

    assert CLASSIFIED_BY_MANUAL == "manual"


def test_classified_by_manual_is_final_str() -> None:
    """``CLASSIFIED_BY_MANUAL`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import CLASSIFIED_BY_MANUAL

    assert isinstance(CLASSIFIED_BY_MANUAL, str)


def test_application_ledger_imports_classified_by_manual_from_core() -> None:
    """The application ledger public surface re-exports ``CLASSIFIED_BY_MANUAL`` from core.

    The application layer must not define a local copy; it must import the
    canonical constant from ``aeat.core.external_constants`` and expose it
    through the package ``__init__``.
    """

    import importlib

    from ..external_constants import CLASSIFIED_BY_MANUAL

    ledger_init = importlib.import_module("aeat.application.ledger")

    # The public surface exposes the constant and it is the same object.
    assert hasattr(ledger_init, "CLASSIFIED_BY_MANUAL"), "aeat.application.ledger must expose CLASSIFIED_BY_MANUAL"
    assert ledger_init.CLASSIFIED_BY_MANUAL is CLASSIFIED_BY_MANUAL


def test_application_ledger_models_does_not_define_classified_by_manual_locally() -> None:
    """``_models.py`` must not carry a local definition of ``CLASSIFIED_BY_MANUAL``.

    It imports the constant from ``aeat.core.external_constants``; the
    imported name must be identical to the core constant (not a shadow).
    """

    import importlib

    from ..external_constants import CLASSIFIED_BY_MANUAL

    models_mod = importlib.import_module("aeat.application.ledger._models")

    # The module still exposes the constant (via import), and it is the same object.
    assert hasattr(models_mod, "CLASSIFIED_BY_MANUAL"), "_models must import CLASSIFIED_BY_MANUAL from core"
    assert models_mod.CLASSIFIED_BY_MANUAL is CLASSIFIED_BY_MANUAL


def test_domain_transactions_service_imports_classified_by_manual_from_core() -> None:
    """The domain service must not shadow ``CLASSIFIED_BY_MANUAL`` with a local string literal.

    The constant must be imported from ``aeat.core.external_constants`` so
    that the domain layer reads a single authoritative value.
    """

    import importlib

    from ..external_constants import CLASSIFIED_BY_MANUAL

    service_mod = importlib.import_module("aeat.domain.transactions._service")

    # The domain service module must import the constant from core (not define its own).
    assert hasattr(service_mod, "CLASSIFIED_BY_MANUAL"), (
        "_service must import CLASSIFIED_BY_MANUAL from aeat.core.external_constants"
    )
    assert service_mod.CLASSIFIED_BY_MANUAL is CLASSIFIED_BY_MANUAL


def test_no_local_classified_by_manual_shadow_in_application_or_domain() -> None:
    """No production file in application/ or domain/ may define a local ``classified_by``
    sentinel by assigning the bare string ``"manual"`` to a module-level variable whose
    name contains ``classified_by`` or ``manual_classified``.

    This is the regression guard against the pattern removed in contract/contract:
    ``_MANUAL_CLASSIFIED_BY = "manual"`` or ``CLASSIFIED_BY_MANUAL = "manual"`` defined
    locally instead of imported from ``aeat.core.external_constants``.
    """

    repo_root = Path(__file__).parents[4]
    search_roots = (
        repo_root / "src/aeat/application",
        repo_root / "src/aeat/domain",
    )

    # Names that signal a classified_by sentinel re-definition.
    _SENTINEL_NAME_FRAGMENTS = ("classified_by", "manual_classified")

    offenders: list[str] = []
    for search_root in search_roots:
        for py_file in search_root.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                # Look for module-level or function-level simple assignments:
                # TARGET = "manual"
                if not isinstance(node, ast.Assign):
                    continue
                value = node.value
                if not isinstance(value, ast.Constant) or value.value != "manual":
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    name_lower = target.id.lower()
                    if any(frag in name_lower for frag in _SENTINEL_NAME_FRAGMENTS):
                        offenders.append(
                            f"{py_file.relative_to(repo_root)}:{node.lineno}: "
                            f"local classified_by sentinel '{target.id} = \"manual\"'; "
                            f"import CLASSIFIED_BY_MANUAL from aeat.core.external_constants"
                        )

    assert offenders == [], (
        "Local classified_by manual sentinels found; "
        "import CLASSIFIED_BY_MANUAL from aeat.core.external_constants instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract / contract / contract — JSON_MIME_TYPE and CSV_MIME_TYPE centralisation tests
# ---------------------------------------------------------------------------


def test_json_mime_type_value() -> None:
    """``JSON_MIME_TYPE`` equals the IANA-registered JSON MIME type."""

    from ..external_constants import JSON_MIME_TYPE

    assert JSON_MIME_TYPE == "application/json"


def test_csv_mime_type_value() -> None:
    """``CSV_MIME_TYPE`` equals the IANA-registered CSV MIME type."""

    from ..external_constants import CSV_MIME_TYPE

    assert CSV_MIME_TYPE == "text/csv"


def test_jsonl_mime_type_value() -> None:
    """``JSONL_MIME_TYPE`` equals the newline-delimited JSON MIME type."""

    from ..external_constants import JSONL_MIME_TYPE

    assert JSONL_MIME_TYPE == "application/x-ndjson"


def test_xlsx_mime_type_value() -> None:
    """``XLSX_MIME_TYPE`` equals the Office Open XML workbook MIME type."""

    from ..external_constants import XLSX_MIME_TYPE

    assert XLSX_MIME_TYPE == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_json_mime_type_is_final_str() -> None:
    """``JSON_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import JSON_MIME_TYPE

    assert isinstance(JSON_MIME_TYPE, str)


def test_csv_mime_type_is_final_str() -> None:
    """``CSV_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import CSV_MIME_TYPE

    assert isinstance(CSV_MIME_TYPE, str)


def test_jsonl_mime_type_is_final_str() -> None:
    """``JSONL_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import JSONL_MIME_TYPE

    assert isinstance(JSONL_MIME_TYPE, str)


def test_xlsx_mime_type_is_final_str() -> None:
    """``XLSX_MIME_TYPE`` is a ``str`` instance (typed ``Final[str]``)."""

    from ..external_constants import XLSX_MIME_TYPE

    assert isinstance(XLSX_MIME_TYPE, str)


def test_declarations_uses_json_mime_constant() -> None:
    """``_declarations.py`` imports ``JSON_MIME_TYPE`` rather than a bare literal.

    The module must expose ``_JSON_MIME_TYPE`` and its value must equal
    ``JSON_MIME_TYPE`` from ``aeat.core.external_constants``, giving an
    identity guarantee without executing the live AEAT browser path.
    """

    import importlib

    from ..external_constants import JSON_MIME_TYPE

    mod = importlib.import_module("aeat.adapters.outbound.aeat.sede._declarations")

    assert hasattr(mod, "_JSON_MIME_TYPE"), (
        "_declarations must import JSON_MIME_TYPE from aeat.core.external_constants under the alias _JSON_MIME_TYPE"
    )
    assert mod._JSON_MIME_TYPE is JSON_MIME_TYPE
    assert mod._JSON_MIME_TYPE == "application/json"


def test_tabular_export_uses_csv_mime_constant() -> None:
    """``_tabular.py`` imports ``CSV_MIME_TYPE`` rather than a bare ``"text/csv"`` literal.

    The module must expose ``_CSV_MIME_TYPE`` and its value must equal
    ``CSV_MIME_TYPE`` from ``aeat.core.external_constants``.
    """

    import importlib

    from ..external_constants import CSV_MIME_TYPE

    mod = importlib.import_module("aeat.application.export._tabular")

    assert hasattr(mod, "_CSV_MIME_TYPE"), (
        "_tabular must import CSV_MIME_TYPE from aeat.core.external_constants under the alias _CSV_MIME_TYPE"
    )
    assert mod._CSV_MIME_TYPE is CSV_MIME_TYPE
    assert mod._CSV_MIME_TYPE == "text/csv"


def test_tabular_export_uses_jsonl_and_xlsx_mime_constants() -> None:
    """``_tabular.py`` imports JSONL/XLSX MIME constants from core."""

    import importlib

    from ..external_constants import JSONL_MIME_TYPE, XLSX_MIME_TYPE

    mod = importlib.import_module("aeat.application.export._tabular")

    assert hasattr(mod, "_JSONL_MIME_TYPE"), (
        "_tabular must import JSONL_MIME_TYPE from aeat.core.external_constants under the alias _JSONL_MIME_TYPE"
    )
    assert hasattr(mod, "_XLSX_MIME_TYPE"), (
        "_tabular must import XLSX_MIME_TYPE from aeat.core.external_constants under the alias _XLSX_MIME_TYPE"
    )
    assert mod._JSONL_MIME_TYPE is JSONL_MIME_TYPE
    assert mod._XLSX_MIME_TYPE is XLSX_MIME_TYPE


def test_no_bare_json_mime_literal_in_declarations() -> None:
    """No bare ``"application/json"`` literal in ``_declarations.py`` argument positions.

    Anti-tautology: parses the real AST so any future re-introduction of
    the literal triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/adapters/outbound/aeat/sede/_declarations.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or node.value != "application/json":
            continue
        offenders.append(f"_declarations.py:{node.lineno}: bare 'application/json' literal")

    assert offenders == [], "Bare 'application/json' literals found; use _JSON_MIME_TYPE instead:\n" + "\n".join(
        offenders
    )


# ---------------------------------------------------------------------------
# contract — M347_THRESHOLD_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_m347_threshold_eur_value() -> None:
    """``M347_THRESHOLD_EUR`` equals €3,005.06 per RD 1065/2007 art. 31.1."""

    from decimal import Decimal

    from ..external_constants import M347_THRESHOLD_EUR

    assert Decimal("3005.06") == M347_THRESHOLD_EUR


def test_m347_threshold_eur_is_final_decimal() -> None:
    """``M347_THRESHOLD_EUR`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import M347_THRESHOLD_EUR

    assert isinstance(M347_THRESHOLD_EUR, Decimal)


def test_counterpart_aggregator_reads_threshold_from_external_constants() -> None:
    """``_counterpart.py`` must import ``M347_THRESHOLD_EUR`` from core, not define it locally."""

    import importlib

    from ..external_constants import M347_THRESHOLD_EUR

    mod = importlib.import_module("aeat.application.aggregation._counterpart")

    assert hasattr(mod, "M347_THRESHOLD_EUR"), (
        "_counterpart must import M347_THRESHOLD_EUR from aeat.core.external_constants"
    )
    assert mod.M347_THRESHOLD_EUR is M347_THRESHOLD_EUR


def test_no_bare_threshold_347_literal_in_counterpart() -> None:
    """No bare ``Decimal("3005.06")`` threshold literal in ``_counterpart.py``.

    Anti-tautology: parses the real AST so any future re-introduction of the
    local constant triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_counterpart.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        # Flag any Decimal("3005.06") call-expression literal in the file.
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "3005.06":
            offenders.append(f"_counterpart.py:{node.lineno}: bare Decimal('3005.06'); use M347_THRESHOLD_EUR")

    assert offenders == [], (
        "Local M347 threshold literals found; import M347_THRESHOLD_EUR from core instead:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# contract — MODELO_720_REPORTING_THRESHOLD_EUR centralisation tests
# ---------------------------------------------------------------------------


def test_modelo_720_reporting_threshold_eur_value() -> None:
    """``MODELO_720_REPORTING_THRESHOLD_EUR`` equals €50,000.00 per AEAT instrucciones."""

    from decimal import Decimal

    from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

    assert Decimal("50000.00") == MODELO_720_REPORTING_THRESHOLD_EUR


def test_modelo_720_reporting_threshold_eur_is_final_decimal() -> None:
    """``MODELO_720_REPORTING_THRESHOLD_EUR`` is a ``Decimal`` instance."""

    from decimal import Decimal

    from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

    assert isinstance(MODELO_720_REPORTING_THRESHOLD_EUR, Decimal)


def test_foreign_assets_aggregator_reads_threshold_from_external_constants() -> None:
    """``_foreign_assets.py`` must import ``MODELO_720_REPORTING_THRESHOLD_EUR`` from core."""

    import importlib

    from ..external_constants import MODELO_720_REPORTING_THRESHOLD_EUR

    mod = importlib.import_module("aeat.application.aggregation._foreign_assets")

    assert hasattr(mod, "MODELO_720_REPORTING_THRESHOLD_EUR"), (
        "_foreign_assets must import MODELO_720_REPORTING_THRESHOLD_EUR from aeat.core.external_constants"
    )
    assert mod.MODELO_720_REPORTING_THRESHOLD_EUR is MODELO_720_REPORTING_THRESHOLD_EUR


def test_no_bare_threshold_720_literal_in_foreign_assets() -> None:
    """No bare ``Decimal("50000.00")`` threshold literal in ``_foreign_assets.py``.

    Anti-tautology: parses the real AST so any future re-introduction of the
    local constant triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/aggregation/_foreign_assets.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "50000.00":
            offenders.append(
                f"_foreign_assets.py:{node.lineno}: bare Decimal('50000.00'); use MODELO_720_REPORTING_THRESHOLD_EUR"
            )

    assert offenders == [], (
        "Local Modelo 720 threshold literals found; import MODELO_720_REPORTING_THRESHOLD_EUR from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_csv_mime_literal_in_tabular() -> None:
    """No bare ``"text/csv"`` literal in ``_tabular.py`` argument positions.

    Anti-tautology: parses the real AST so any future re-introduction of
    the literal triggers immediate failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/export/_tabular.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or node.value != "text/csv":
            continue
        offenders.append(f"_tabular.py:{node.lineno}: bare 'text/csv' literal")

    assert offenders == [], "Bare 'text/csv' literals found; use _CSV_MIME_TYPE instead:\n" + "\n".join(offenders)


# ---------------------------------------------------------------------------
# contract — DEFAULT_IVA_GENERAL_RATE_PCT centralisation tests
# ---------------------------------------------------------------------------


def test_default_iva_general_rate_pct_value() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` equals 21.00 per LIVA art. 90 Uno."""

    from decimal import Decimal

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    assert Decimal("21.00") == DEFAULT_IVA_GENERAL_RATE_PCT


def test_default_iva_general_rate_pct_is_final_decimal() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` is a ``Decimal`` instance (typed ``Final[Decimal]``)."""

    from decimal import Decimal

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    assert isinstance(DEFAULT_IVA_GENERAL_RATE_PCT, Decimal)


def test_default_iva_general_rate_pct_matches_registry() -> None:
    """``DEFAULT_IVA_GENERAL_RATE_PCT`` equals the IVA-registry general rate for Spain on 2026-01-01.

    Binds the default to the dated :func:`aeat.domain.iva.lookup_rate` registry so
    it cannot silently drift when AEAT publishes a rate change.
    """

    from datetime import date
    from decimal import Decimal

    from ...domain.iva import EUMemberState, IvaRateKind, lookup_rate

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    registry_rate = lookup_rate(EUMemberState.ES, IvaRateKind.GENERAL, date(2026, 1, 1))
    assert DEFAULT_IVA_GENERAL_RATE_PCT == registry_rate.pct


def test_inventory_service_imports_default_iva_general_rate_pct_from_core() -> None:
    """``application/inventory/_service.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.application.inventory._service")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "_service must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_ledger_inventory_cli_imports_default_iva_general_rate_pct_from_core() -> None:
    """``entrypoints/cli/_ledger_inventory_cli.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.entrypoints.cli._ledger_inventory_cli")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "_ledger_inventory_cli must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_contribuyente_assets_imports_default_iva_general_rate_pct_from_core() -> None:
    """``domain/contribuyente/assets/__init__.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.domain.contribuyente.assets")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "aeat.domain.contribuyente.assets must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_contribuyente_inventory_imports_default_iva_general_rate_pct_from_core() -> None:
    """``domain/contribuyente/inventory/__init__.py`` imports ``DEFAULT_IVA_GENERAL_RATE_PCT`` from core."""

    import importlib

    from ..external_constants import DEFAULT_IVA_GENERAL_RATE_PCT

    mod = importlib.import_module("aeat.domain.contribuyente.inventory")

    assert hasattr(mod, "DEFAULT_IVA_GENERAL_RATE_PCT"), (
        "aeat.domain.contribuyente.inventory must import DEFAULT_IVA_GENERAL_RATE_PCT from aeat.core.external_constants"
    )
    assert mod.DEFAULT_IVA_GENERAL_RATE_PCT is DEFAULT_IVA_GENERAL_RATE_PCT


def test_no_bare_iva_rate_decimal_literal_in_inventory_service() -> None:
    """No bare ``Decimal("21.00")`` literal in ``application/inventory/_service.py``.

    Anti-tautology: parses the real AST so any future re-introduction triggers failure.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/inventory/_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "21.00":
            offenders.append(f"_service.py:{node.lineno}: bare Decimal('21.00'); use DEFAULT_IVA_GENERAL_RATE_PCT")

    assert offenders == [], (
        "Local IVA 21.00 literals found; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_decimal_literal_in_contribuyente_assets() -> None:
    """No bare ``Decimal("21.00")`` literal in ``domain/contribuyente/assets/__init__.py``."""

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/assets/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "21.00":
            offenders.append(
                f"assets/__init__.py:{node.lineno}: bare Decimal('21.00'); use DEFAULT_IVA_GENERAL_RATE_PCT"
            )

    assert offenders == [], (
        "Local IVA 21.00 literals found in assets; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_decimal_literal_in_contribuyente_inventory() -> None:
    """No bare ``Decimal("21.00")`` literal in ``domain/contribuyente/inventory/__init__.py``."""

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/domain/contribuyente/inventory/__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if func_name != "Decimal":
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "21.00":
            offenders.append(
                f"inventory/__init__.py:{node.lineno}: bare Decimal('21.00'); use DEFAULT_IVA_GENERAL_RATE_PCT"
            )

    assert offenders == [], (
        "Local IVA 21.00 literals found in inventory; import DEFAULT_IVA_GENERAL_RATE_PCT from core instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_iva_rate_string_literal_in_ledger_inventory_cli() -> None:
    """No bare ``"21.00"`` string literal as a typer Option default in ``_ledger_inventory_cli.py``.

    Anti-tautology: parses the AST and fails if the literal is re-introduced as a
    bare Option default instead of ``str(DEFAULT_IVA_GENERAL_RATE_PCT)``.
    """

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/entrypoints/cli/_ledger_inventory_cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders: list[str] = []
    for node in ast.walk(tree):
        # Look for string constants with value "21.00" that are NOT inside str(...) calls.
        if not isinstance(node, ast.Constant) or node.value != "21.00":
            continue
        offenders.append(
            f"_ledger_inventory_cli.py:{node.lineno}: bare '21.00' string literal; "
            f"use str(DEFAULT_IVA_GENERAL_RATE_PCT)"
        )

    assert offenders == [], (
        "Bare '21.00' string literals found; use str(DEFAULT_IVA_GENERAL_RATE_PCT) instead:\n"
        + "\n".join(offenders)
    )


def test_no_bare_jsonl_or_xlsx_mime_literal_in_tabular() -> None:
    """No bare JSONL/XLSX MIME literals in ``_tabular.py`` argument positions."""

    repo_root = Path(__file__).parents[4]
    source = (repo_root / "src/aeat/application/export/_tabular.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    guarded_literals = {
        "application/x-ndjson": "_JSONL_MIME_TYPE",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "_XLSX_MIME_TYPE",
    }
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        expected = guarded_literals.get(node.value)
        if expected is None:
            continue
        offenders.append(f"_tabular.py:{node.lineno}: bare {node.value!r} literal; use {expected}")

    assert offenders == [], "Bare JSONL/XLSX MIME literals found:\n" + "\n".join(offenders)
