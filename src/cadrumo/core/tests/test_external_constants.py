"""Tests for the external-constants registry and tunable-Settings split.

See Also:
    :func:`~core.external_constants.load_external_constants`
        Runtime loader for the packaged TOML registry validated by this test
        module.
    :class:`~core.external_constants.ExternalConstants`
        Typed, frozen registry root that keeps remote-mirror constants
        schema-owned.
    :class:`~core.config.Settings`
        Tunable configuration surface that must consume registry defaults
        without becoming a second authority for external constants.
    :mod:`~domain.portals`
        Portal catalogue whose host and route keys resolve through the AEAT
        registry surfaces checked here.
"""

from __future__ import annotations

import ast
import re
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...tests import ast_for_path, discover_test_control_modules, package_ast_items, repo_path, repo_relative
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
    loaded = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    payload: dict[str, object] = {}
    for key, value in loaded.items():
        assert isinstance(key, str), "TOML table keys must be strings"
        payload[key] = value
    return payload


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


def _tree_for_path(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> ast.AST:
    tree = ast_for_path(path, source_tree_ast)
    if tree is None:
        raise AssertionError(f"unable to parse {repo_relative(path)}")
    return tree


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        if not _is_docstring_node(node):
            continue
        first = node.body[0]
        assert isinstance(first, ast.Expr)
        assert isinstance(first.value, ast.Constant)
        ids.add(id(first.value))
    return ids


def _token_literal_offenders(
    *,
    files: Iterable[tuple[Path, ast.AST]],
    volatile_tokens: tuple[str, ...],
) -> list[str]:
    offenders: list[str] = []
    for path, tree in files:
        docstring_ids = _docstring_constant_ids(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstring_ids:
                continue
            if any(token in node.value for token in volatile_tokens):
                offenders.append(f"{repo_relative(path)}:{node.lineno}: {node.value!r}")
    return offenders


def test_load_external_constants_returns_cached_model_used_by_settings_facade() -> None:
    """The loader yields the canonical cached :class:`ExternalConstants`."""

    constants = load_external_constants()

    assert isinstance(constants, ExternalConstants)
    assert constants is load_external_constants()
    assert Settings.external_constants() is constants


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
        paths.irpf_expediente_detail_year_prefix,
        paths.notificaciones,
        paths.iva_compensation_wallet,
        paths.censal_datos,
    ):
        assert value.startswith("/")
    assert paths.irpf_expediente_detail_year_suffix


def test_certificate_protected_resource_authority_is_exact_and_composed() -> None:
    """Certificate authentication has one non-configurable www6 protected resource."""
    from ..config import (
        AEAT_CERTIFICATE_PROTECTED_ORIGIN,
        AEAT_CERTIFICATE_PROTECTED_PATH,
        AEAT_CERTIFICATE_PROTECTED_URL,
    )

    constants = load_external_constants()

    assert AEAT_CERTIFICATE_PROTECTED_ORIGIN == "https://www6.agenciatributaria.gob.es"
    assert constants.aeat.domains.www6 == AEAT_CERTIFICATE_PROTECTED_ORIGIN
    assert AEAT_CERTIFICATE_PROTECTED_PATH == "/wlpl/TEWV-CORE/ResumenVlt"
    assert constants.aeat.sede_paths.expedientes_resumen == AEAT_CERTIFICATE_PROTECTED_PATH
    assert f"{AEAT_CERTIFICATE_PROTECTED_ORIGIN}{AEAT_CERTIFICATE_PROTECTED_PATH}" == AEAT_CERTIFICATE_PROTECTED_URL


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
    assert "check-nif-*" in safety.consult_oracle_browser_action_patterns
    assert "requires-renta-web-open-driver" in safety.renta_web_open_browser_action_patterns
    assert "accept-identification" in safety.renta_web_open_browser_action_patterns


def test_missing_pre303_block_does_not_poison_registry_or_settings() -> None:
    """A registry payload with no ``[aeat.pre303]`` block still validates.

    Regression guard: the ``pre303`` section is the most volatile part of
    the registry (AEAT-portal scraping selectors). It must validate
    lazily so a half-landed change that adds pre303 model fields without
    the matching TOML data cannot break registry parsing — and therefore
    cannot break the ``Settings()`` construction that resolves AEAT-URL
    defaults through :func:`load_external_constants`.
    """

    payload = _registry_toml_payload()
    aeat_section = _aeat_section(payload)
    aeat_section.pop("pre303", None)

    constants = ExternalConstants.model_validate(payload)

    assert isinstance(constants, ExternalConstants)
    assert constants.aeat.domains.sede.startswith("https://")
    section = AeatSection.model_validate(aeat_section)
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


def test_live_sede_executable_route_literals_stay_centralized(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Live AEAT executable code must read volatile routes from the registry."""

    checked_paths = (
        repo_path("src/cadrumo/core/config.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/auth/_clave_movil.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/sede/_groi_check.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/sede/_nif_iva_check.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/sede/_censal_datos.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/sede/_declarations.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/sede/_iva_compensation_wallet.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/sede/_parse.py"),
        repo_path("src/cadrumo/adapters/outbound/aeat/verify/__init__.py"),
        repo_path("src/cadrumo/domain/manuals/_fetch.py"),
    )

    offenders = _token_literal_offenders(
        files=((path, _tree_for_path(path, source_tree_ast)) for path in checked_paths),
        volatile_tokens=AEAT_LITERAL_SCAN_TOKENS,
    )

    assert offenders == []


def test_subdomain_enum_aligns_with_aeat_domains() -> None:
    """Portal host keys resolve to the TOML registry hosts."""

    from ...domain.portals import PortalHost, portal_host_name

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

    from ...domain.portals import Portal, portal_path

    constants = load_external_constants().aeat
    assert re.compile(constants.portal_paths.filing_censo_path_regex)
    assert constants.portal_paths.filing_censo_path_description
    assert set(constants.portal_paths.paths) == {portal.value for portal in Portal} - {
        Portal.PORTAL_PRE303_AYUDA.value,
    }
    for portal_id, path in constants.portal_paths.paths.items():
        assert path.startswith("/")
        assert portal_path(Portal(portal_id)) == path


def test_portal_registry_modules_do_not_reintroduce_route_or_host_literals(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Portal catalogue modules must resolve AEAT hosts and paths through central constants."""

    volatile_tokens = PORTAL_LITERAL_SCAN_TOKENS
    allowed_files = {"src/cadrumo/domain/portals/_hosts.py"}

    offenders: list[str] = []
    for path, tree in package_ast_items(source_tree_ast):
        relative_path = repo_relative(path)
        if not relative_path.startswith("src/cadrumo/domain/portals/"):
            continue
        if "/tests/" in relative_path or relative_path in allowed_files:
            continue
        docstring_ids = _docstring_constant_ids(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in docstring_ids:
                continue
            value = node.value
            is_entry_root_path = path.parent.name == "_entries" and path.name != "_common.py" and value == "/"
            if is_entry_root_path or any(token in value for token in volatile_tokens):
                offenders.append(f"{relative_path}:{node.lineno}: {value!r}")

    assert offenders == []


def test_remote_guard_parity_and_oracle_tests_use_declared_aeat_literal_fixtures(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Remote guard/parity/oracle tests must import configured URLs or declared canaries."""

    checked_paths = (
        repo_path("src/cadrumo/domain/calculations/registry/tests/test_remote_state_guard.py"),
        repo_path("src/cadrumo/domain/calculations/registry/tests/test_oracle_parity.py"),
        repo_path("src/cadrumo/domain/calculations/registry/tests/test_groi_oracle.py"),
        repo_path("src/cadrumo/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py"),
    )
    offenders = _token_literal_offenders(
        files=((path, _tree_for_path(path, source_tree_ast)) for path in checked_paths),
        volatile_tokens=REMOTE_GUARD_LITERAL_SCAN_TOKENS,
    )

    assert offenders == []


def test_test_suite_aeat_route_literals_are_centralized_or_declared(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Test modules must not own executable AEAT/Sede host or route literals."""

    allowed_files = {
        repo_relative(Path(__file__).resolve()),
        "src/cadrumo/adapters/persistence/storage/tests/_runtime_attached_repositories_support.py",
        "src/cadrumo/tests/aeat_literal_fixtures.py",
        # The AEAT locator RECOGNISER: its regex and prefix tuple exist to match
        # external Sede URLs, so the host fragment is the pattern under test
        # rather than a route this module navigates. Sourcing it from a fixture
        # would assert the recogniser against the string it was built from.
        "src/cadrumo/tests/test_spanish_iva_stem_conformance.py",
    }
    volatile_tokens = tuple(
        dict.fromkeys(
            (
                *AEAT_LITERAL_SCAN_TOKENS,
                "agenciatributaria.es",
                "clave.gob.es",
            ),
        ),
    )

    checked_files = (
        (path, _tree_for_path(path, source_tree_ast))
        for path in discover_test_control_modules()
        if repo_relative(path) not in allowed_files
    )
    offenders = _token_literal_offenders(files=checked_files, volatile_tokens=volatile_tokens)

    assert offenders == []


def test_runtime_tunables_are_settings_not_registry_constants() -> None:
    """Runtime knobs live on :class:`Settings`, not the external registry."""

    constants = load_external_constants()

    assert not hasattr(constants.aeat, "timeouts_ms")
    assert not hasattr(constants.online_services, "llm_endpoints")
    settings = Settings()
    expected_defaults: dict[str, object] = {
        "cadrumo_browser_navigation_timeout_ms": 30_000,
        "cadrumo_browser_form_interaction_timeout_ms": 10_000,
        "cadrumo_browser_ver_click_timeout_ms": 15_000,
        "cadrumo_browser_buscar_settle_ms": 3_000,
        "cadrumo_browser_selector_probe_timeout_ms": 2_500,
        "cadrumo_browser_close_timeout_ms": 5_000,
        "cadrumo_live_iva_declaration_capture_timeout_ms": 120_000,
        "cadrumo_live_iva_cli_watchdog_timeout_ms": 240_000,
        "cadrumo_browser_locale": "es-ES",
        "cadrumo_browser_timezone": "Europe/Madrid",
        "cadrumo_browser_viewport_width": 1366,
        "cadrumo_browser_viewport_height": 900,
        "cadrumo_file_lock_timeout_s": 30.0,
        "cadrumo_file_lock_retry_backoff_s": 0.05,
        "cadrumo_bucket_lock_poll_interval_s": 0.1,
        "cadrumo_bucket_default_idle_lock_minutes": 15,
        "cadrumo_bucket_default_session_absolute_minutes": 240,
        "cadrumo_auth_clave_movil_lock_buffer_s": 90,
        "cadrumo_auth_certificate_lock_ttl_s": 180,
        "cadrumo_log_stderr_level": "ERROR",
        "cadrumo_log_file_level": "DEBUG",
        "cadrumo_log_root_level": "DEBUG",
        "cadrumo_google_drive_vault_folder_name": "cadrumo-vault",
        "cadrumo_google_oauth_access_refresh_buffer_s": 300,
        "cadrumo_calc_sheets_recalc_delay_s": 2.0,
        "cadrumo_llm_default_max_tokens": 1024,
        "cadrumo_llm_default_temperature": 0.0,
        "cadrumo_manuals_http_timeout_s": 60.0,
    }

    for field_name, expected_value in expected_defaults.items():
        assert getattr(settings, field_name) == expected_value, field_name

    assert settings.cadrumo_live_iva_declaration_capture_timeout_ms < settings.cadrumo_live_iva_surface_timeout_ms
    assert settings.cadrumo_live_iva_cli_watchdog_timeout_ms < 300_000
    assert settings.cadrumo_llm_openai_chat_completions_url.startswith("https://api.openai.com")
    assert "{model}" in settings.cadrumo_llm_gemini_generate_content_template
    assert settings.cadrumo_llm_ollama_chat_url.startswith("http://")


def test_settings_refuse_the_former_product_google_drive_vault_folder() -> None:
    """The old Drive folder cannot be configured as fresh Cadrumo state."""
    with pytest.raises(ValidationError, match="former product Google Drive vault folder"):
        Settings(cadrumo_google_drive_vault_folder_name=" aeat-vault ")


def test_live_iva_declaration_timeout_must_leave_outer_surface_headroom() -> None:
    """One declaration timeout must fire before the whole filed-history surface timeout.

    The refusal is catalogue-rendered, so the two timeouts it reconciles are
    typed facts on the raised error rather than words in a sentence. Pydantic
    keeps the raising exception under the violation's ``ctx``, which is the only
    channel those facts survive on through a ``model_validator`` -- matching on
    ``str(exc)`` would now only re-assert the message key and would pass just as
    well if the validator compared the wrong pair of fields.
    """
    with pytest.raises(ValidationError) as refusal:
        Settings(
            cadrumo_live_iva_declaration_capture_timeout_ms=180_000,
            cadrumo_live_iva_surface_timeout_ms=180_000,
        )

    (violation,) = refusal.value.errors()
    raised = violation["ctx"]["error"]
    assert isinstance(raised, CoreValidationError)
    context = raised.context or {}
    assert context["capture_timeout_ms"] == 180_000
    assert context["surface_timeout_ms"] == 180_000
    assert context["capture_below_surface"] is False


def test_clave_movil_operator_wait_is_capped_at_two_minutes() -> None:
    """Cl@ve Móvil approval waits fail fast enough for production retry loops."""

    assert Settings().cadrumo_clave_movil_timeout_ms == 120_000

    with pytest.raises(ValidationError):
        Settings(cadrumo_clave_movil_timeout_ms=120_001)
