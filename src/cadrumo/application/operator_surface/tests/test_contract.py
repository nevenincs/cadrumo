"""Tests for the backend-owned operator surface contract.

The suite pins the command roots, mounted command families, lifecycle tokens,
parser-only source-kind aliases, help documents, and registered refusal error
used by entrypoint adapters. It deliberately exercises the application-owned
contract as data so CLI and MCP surfaces cannot redefine operator vocabulary in
their own layers.

See Also:
    :mod:`~application.operator_surface`
        Public facade for the backend-owned command contract under test.
    :func:`~application.operator_surface.get_operator_surface_contract`
        Cached contract builder exercised by the root, lifecycle, command-family,
        and source-kind assertions.
    :func:`~application.operator_surface.build_help_document`
        Backend help document builder checked against the current mounted
        command families.
    :func:`~application.operator_surface.require_accepted_root`
        Refusal gate that raises the registered operator-surface contract error.
    :func:`~application.operator_surface.build_operator_surface_manifest`
        Agent-facing manifest builder that consumes the same backend contract.
    :mod:`~entrypoints.cli._app_contract`
        CLI adapter that emits the manifest without owning the contract.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from dev.locales import LocaleManager
from pydantic import BaseModel, ValidationError

from ....core import BindingSourceKind
from ....core.aggregation import COUNTERPART_SOURCE_KINDS
from ....core.config import override_settings
from ....core.errors import get_registered_error_code
from ....core.external_constants import OutputLanguage
from ... import operator_surface
from .. import (
    FilingStatus,
    ModeloLifecycleStep,
    MountedCommandDomain,
    OperatorMutability,
    OperatorSurfaceContractError,
    RootSurfaceName,
    build_help_document,
    build_root_landing_report,
    get_operator_surface_contract,
    render_help_text,
    require_accepted_root,
    resolve_source_kind_alias,
)
from .. import _help as _help_module
from .._models import HelpDocument, HelpEntry, HelpSection, LifecycleContract, RootLandingReport, RootSurface

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def pin_english_locale() -> Iterator[None]:
    """Pin the operator-surface contract tests to the English locale.

    The contract surface (help paragraphs, error messages) is rendered
    through the project locale layer. These tests assert against the
    canonical English strings, so we pin the locale here rather than
    coupling the assertions to whatever the default locale happens to be
    in any given environment.
    """
    with override_settings(cadrumo_output_language="en"):
        yield


def test_contract_roots_are_exactly_config_and_app() -> None:
    contract = get_operator_surface_contract()

    assert tuple(root.name for root in contract.roots) == (
        RootSurfaceName.CONFIG,
        RootSurfaceName.APP,
    )
    assert contract.roots[0].owns_storage_maintenance is True
    assert contract.roots[1].owns_operational_workflow is True


def test_contract_lifecycle_forbids_live_submission() -> None:
    contract = get_operator_surface_contract()

    assert contract.lifecycle.steps == (
        ModeloLifecycleStep.CALCULATE,
        ModeloLifecycleStep.VERIFY,
        ModeloLifecycleStep.FILE,
    )
    assert contract.lifecycle.internal_filed_term == "internal filed"
    assert contract.lifecycle.live_submission_enabled is False

    with pytest.raises(ValidationError, match=r"steps|VERIFY|lifecycle"):
        LifecycleContract(
            steps=(
                ModeloLifecycleStep.CALCULATE,
                ModeloLifecycleStep.FILE,
            ),
        )
    with pytest.raises(ValidationError, match=r"live_submission_enabled|forbidden|False"):
        LifecycleContract(
            steps=(
                ModeloLifecycleStep.CALCULATE,
                ModeloLifecycleStep.VERIFY,
                ModeloLifecycleStep.FILE,
            ),
            live_submission_enabled=True,
        )


def test_contract_source_kind_aliases_are_parser_only() -> None:
    assert resolve_source_kind_alias("ledger_transaction") is BindingSourceKind.LEDGER_TRANSACTION
    assert resolve_source_kind_alias("lt") is BindingSourceKind.LEDGER_TRANSACTION
    assert resolve_source_kind_alias("pie") is BindingSourceKind.PURCHASE_INVOICE_EVIDENCE
    assert resolve_source_kind_alias("pi") is BindingSourceKind.PAYABLE_INVOICE
    assert resolve_source_kind_alias("ci") is BindingSourceKind.COLLECTIBLE_INVOICE


def test_require_accepted_root_uses_registered_application_error() -> None:
    assert require_accepted_root("config").name is RootSurfaceName.CONFIG

    with pytest.raises(OperatorSurfaceContractError, match=r"operator|surface|contract") as exc_info:
        require_accepted_root("setup")

    error = exc_info.value
    assert error.reason == "The CLI accepts only the config and app roots."
    assert error.suggestion == "aeat --help"
    assert get_registered_error_code(error).code == "REFUSED_OPERATOR_SURFACE_CONTRACT"


def test_contract_models_are_strict_and_immutable() -> None:
    root = get_operator_surface_contract().roots[0]

    with pytest.raises(ValidationError, match=r"required_children|duplicate|unique"):
        RootSurface(
            name=RootSurfaceName.CONFIG,
            purpose="duplicate children",
            owns_storage_maintenance=True,
            owns_operational_workflow=False,
            required_children=("profile", "profile"),
        )
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        extra_kwargs: dict[str, object] = {"unexpected": True}
        RootSurface.model_validate(
            {
                "name": RootSurfaceName.CONFIG,
                "purpose": "extra field",
                "owns_storage_maintenance": True,
                "owns_operational_workflow": False,
                **extra_kwargs,
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        setattr(root, "purpose", "mutated")  # noqa: B010 - frozen-model refusal is the assertion


def test_operator_surface_application_package_has_no_typer_dependency() -> None:
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""\
        import importlib
        import sys

        for module_name in (
            "cadrumo.application.operator_surface",
            "cadrumo.application.operator_surface._contract",
            "cadrumo.application.operator_surface._help",
            "cadrumo.application.operator_surface._models",
        ):
            importlib.import_module(module_name)

        leaked = sorted(
            name
            for name in sys.modules
            if name == "typer" or name.startswith("typer.") or name.startswith("cadrumo.entrypoints.cli")
        )
        assert leaked == [], leaked
    """)
    result = subprocess.run(  # noqa: S603 - fixed interpreter argv with in-test script.
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"operator surface imported a CLI-only dependency.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_log_fields_and_error_codes_are_backend_owned() -> None:
    contract = get_operator_surface_contract()

    assert contract.log_fields.as_extra().for_logging() == {
        "contract_name": "operator_surface",
        "root_count": 2,
        "lifecycle": "calculate -> verify -> file",
        "source_kind_count": 4,
    }
    assert contract.error_codes == ("REFUSED_OPERATOR_SURFACE_CONTRACT",)


def test_mounted_command_families_are_backend_owned_and_service_backed() -> None:
    contract = get_operator_surface_contract()

    by_domain = {family.domain: family for family in contract.command_families}

    assert MountedCommandDomain.FIRST_RUN not in by_domain
    assert by_domain[MountedCommandDomain.PROFILE].root is RootSurfaceName.CONFIG
    assert by_domain[MountedCommandDomain.PROFILE].child == "profile"
    assert by_domain[MountedCommandDomain.PROFILE].service_owner == "cadrumo.application.user_profile"
    assert {"create", "edit", "show", "delete", "status"}.issubset(by_domain[MountedCommandDomain.PROFILE].commands)
    custody_commands = {
        command
        for family in contract.command_families
        if family.domain is MountedCommandDomain.CUSTODY
        for command in family.commands
    }
    assert {"login", "logout", "change", "recover", "status", "create", "rotate", "verify"} == custody_commands
    # The append-only event-history verb merged into the `config profile` group
    # as `config profile history` (D1 family rename); the standalone
    # `config bucket` group was retired, so there is no BUCKET family.
    assert MountedCommandDomain.BUCKET not in by_domain
    assert "history" in by_domain[MountedCommandDomain.PROFILE].commands
    assert by_domain[MountedCommandDomain.OVERVIEW].mutability is OperatorMutability.READ_ONLY
    assert by_domain[MountedCommandDomain.LEDGER].service_owner == "cadrumo.application.transactions"
    assert by_domain[MountedCommandDomain.REVIEW].service_owner == "cadrumo.application.review"

    mounted_pairs = {(family.root.value, family.child) for family in contract.command_families}
    assert ("config", "auth") in mounted_pairs
    assert ("config", "bucket") not in mounted_pairs
    assert ("config", "profile") in mounted_pairs
    assert ("app", "modelo") in mounted_pairs
    assert all("invoice" not in family.child for family in contract.command_families)


def test_required_children_match_mounted_command_families() -> None:
    contract = get_operator_surface_contract()

    for root in contract.roots:
        mounted_children = tuple(family.child for family in contract.command_families if family.root is root.name)
        assert root.required_children == mounted_children


def test_help_documents_are_backend_owned_and_current_surface_only() -> None:
    root = build_help_document("root")
    config = build_help_document("config")
    app = build_help_document("app")

    root_text = render_help_text(root)
    config_text = render_help_text(config)
    app_text = render_help_text(app)

    assert "The CLI has exactly two roots: config and app." in root.paragraphs
    assert "aeat config profile create NAME" in root_text
    assert "CADRUMO_LOCAL_STORAGE_ROOT" in root_text
    assert "CADRUMO_SECRET_STORE_DIR" in root_text
    assert "CADRUMO_SECRET_PASSPHRASE" in config_text
    assert ("aeat config " + "init") not in root_text
    assert "aeat app ledger import" in root_text
    assert "aeat app live filed list" in root_text
    assert "aeat app live filed pull" in app_text
    assert "aeat config bucket" not in root_text
    assert "aeat config bucket" not in config_text
    assert "aeat config profile history" in config_text
    assert "aeat app invoice" not in app_text
    assert "aeat app declaration" not in app_text
    assert "cadrumo app" not in root_text + config_text + app_text
    assert "cadrumo config" not in root_text + config_text + app_text


@pytest.mark.parametrize("locale", list(OutputLanguage))
def test_help_documents_build_in_every_shipped_locale(locale: OutputLanguage) -> None:
    """Building the help documents must succeed in every locale, not only English.

    Every ``HelpEntry.description``, ``HelpSection.title``,
    ``HelpDocument.heading``, and ``HelpDocument.footer`` is a translated
    string feeding an 80- or 120-character pydantic cap. English is
    comfortably short by construction, so a suite pinned to English cannot
    observe a translation that exceeds its cap -- exactly what shipped when
    three Spanish and Hungarian ``config storage`` descriptions blew the
    80-character limit and ``aeat config --help`` exited 2 for every operator
    in those locales, invisible to every English-pinned test in this file.

    Command invocations (``entry.command``) are literal Python strings in
    ``_help.py``, never translated, so the structural assertions below hold
    in every locale exactly as they do in English -- this is not a weaker
    check for non-English locales, it is the same property, proven where a
    translation can actually break it.
    """
    with override_settings(cadrumo_output_language=locale.value):
        root = build_help_document("root")
        config = build_help_document("config")
        app = build_help_document("app")

    root_text = render_help_text(root)
    config_text = render_help_text(config)
    app_text = render_help_text(app)

    assert "aeat config profile create NAME" in root_text
    assert ("aeat config " + "init") not in root_text
    assert "aeat app ledger import" in root_text
    assert "aeat app live filed list" in root_text
    assert "aeat app live filed pull" in app_text
    assert "aeat config bucket" not in root_text
    assert "aeat config bucket" not in config_text
    assert "aeat config profile history" in config_text
    assert "aeat app invoice" not in app_text
    assert "aeat app declaration" not in app_text
    # Product-name hygiene must hold in translated prose too: "cadrumo" must
    # never leak into a command verb in place of "aeat", in any locale.
    assert "cadrumo app" not in root_text + config_text + app_text
    assert "cadrumo config" not in root_text + config_text + app_text


@pytest.mark.parametrize("locale", list(OutputLanguage))
def test_help_command_rows_are_backed_by_mounted_command_families(locale: OutputLanguage) -> None:
    contract = get_operator_surface_contract()
    mounted = {(family.root.value, family.child) for family in contract.command_families}

    with override_settings(cadrumo_output_language=locale.value):
        for surface in ("root", "config", "app"):
            document = build_help_document(surface)
            for section in document.sections:
                for entry in section.entries:
                    if " -> " in entry.command or "rejected" in entry.command:
                        continue
                    tokens = entry.command.split()
                    assert tokens[0] == "aeat"
                    assert (tokens[1], tokens[2]) in mounted


_LENGTH_CAPPED_MODELS: dict[str, type[BaseModel]] = {
    "HelpEntry": HelpEntry,
    "HelpSection": HelpSection,
    "HelpDocument": HelpDocument,
    "RootLandingReport": RootLandingReport,
}
"""Models :mod:`.._help` constructs whose fields carry a pydantic ``max_length``."""


def _field_max_length(model: type[BaseModel], field: str) -> int | None:
    """Return the ``max_length`` constraint ``model.field`` carries, if any.

    Introspects the live pydantic field metadata rather than hand-copying the
    80/120/160 caps from ``_models.py``, so a future constraint change is
    picked up automatically instead of silently drifting from the check.
    """
    info = model.model_fields.get(field)
    if info is None:
        return None
    for constraint in info.metadata:
        candidate = getattr(constraint, "max_length", None)
        if isinstance(candidate, int):
            return candidate
    return None


def _tr_key_from_call(node: ast.expr) -> str | None:
    """Return the literal locale key a ``tr(...)``/``t(...)`` call passes, if any."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    if node.func.id not in {"tr", "t"} or not node.args:
        return None
    first = node.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def _capped_translation_keys() -> tuple[tuple[str, int], ...]:
    """AST-scan ``_help.py`` for every translated string feeding a length-capped field.

    Walks every ``HelpEntry``/``HelpSection``/``HelpDocument``/``RootLandingReport``
    construction call in the module and returns ``(locale_key, max_length)`` for
    each keyword argument whose value is a ``tr(...)`` call and whose target field
    carries a pydantic ``max_length``. ``entry.command`` and ``report.command`` are
    always literal Python strings in ``_help.py`` (never translated), so they never
    match a ``tr(...)`` value and are correctly absent from the returned set.
    """
    tree = ast.parse(inspect.getsource(_help_module))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        model = _LENGTH_CAPPED_MODELS.get(node.func.id)
        if model is None:
            continue
        for kw in node.keywords:
            if kw.arg is None:
                continue
            key = _tr_key_from_call(kw.value)
            if key is None:
                continue
            cap = _field_max_length(model, kw.arg)
            if cap is not None:
                found.append((key, cap))
    return tuple(found)


def _lookup_dotted(catalogue: Mapping[str, object], dotted_key: str) -> str | None:
    """Resolve a dot-notated locale key against a nested locale mapping."""
    node: object = catalogue
    for part in dotted_key.split("."):
        if not isinstance(node, dict):
            return None
        level: dict[str, object] = {str(key): value for key, value in node.items()}
        if part not in level:
            return None
        node = level[part]
    return node if isinstance(node, str) else None


def test_help_and_landing_locale_strings_stay_within_field_caps() -> None:
    """Every translated help/landing string must fit its pydantic length cap, in every locale.

    Sharper companion to :func:`test_help_documents_build_in_every_shipped_locale`:
    that test proves the DOCUMENT still builds per locale, but pydantic raises on
    the FIRST over-length field it hits, so a multi-violation regression is only
    partially visible through it and the failure names a raw string, not the
    offending (locale, key). This test checks every capped ``tr(...)`` call site
    against every locale catalogue directly and reports every violation at once,
    naming the exact locale key, its length, and its cap -- the actionable form of
    the same guarantee. It is independent of :func:`.._help.build_help_document`
    successfully constructing anything, so it also covers a key whose value would
    fail for an unrelated reason (a missing interpolation placeholder, say) before
    ever reaching the model boundary.
    """
    capped_keys = _capped_translation_keys()
    assert capped_keys, "AST scan found no capped tr() call sites in _help.py -- the scanner has regressed"

    cadrumo_root = Path(operator_surface.__file__).parent.parent.parent
    manager = LocaleManager(src_dir=cadrumo_root, locales_dir=cadrumo_root / "locales")

    violations: list[str] = []
    for locale in OutputLanguage:
        catalogue = manager.load_locale(manager.locales_dir / f"{locale.value}.yml")
        for key, cap in capped_keys:
            value = _lookup_dotted(catalogue, key)
            if value is None:
                # Missing-key coverage/parity is owned by the locales audit gate,
                # not this length check.
                continue
            if len(value) > cap:
                violations.append(f"{locale.value}: {key!r} is {len(value)} chars, cap is {cap}: {value!r}")

    assert violations == [], "locale strings exceed their pydantic max_length:\n  " + "\n  ".join(violations)


def test_root_landing_report_reads_profile_state_input_only() -> None:
    missing = build_root_landing_report(None)
    active = build_root_landing_report("operator")

    assert missing.command == "aeat config profile create NAME"
    assert missing.active_profile is None
    assert active.command == "aeat app overview status"
    assert active.active_profile == "operator"


def test_filing_status_filed_is_sole_source_for_filed_token() -> None:
    """FilingStatus.FILED is the token exposed by the LIVE command family."""
    assert FilingStatus.FILED == "filed"
    assert str(FilingStatus.FILED) == "filed"

    contract = get_operator_surface_contract()
    live_family = next(f for f in contract.command_families if f.domain is MountedCommandDomain.LIVE)
    assert FilingStatus.FILED in live_family.commands


def test_filing_status_has_no_token_shim_module() -> None:
    assert not (Path(operator_surface.__path__[0]) / "_filing_status_token.py").exists()


def test_operator_source_kinds_mirror_the_counterpart_subset_of_binding_source_kind() -> None:
    """The operator-surface source kinds are exactly the counterpart subset of the core enum.

    taxonomy unification: the duplicate ``operator_surface.SourceKind``
    enum was deleted and the operator surface now declares its source kinds
    directly as :class:`BindingSourceKind` members. They must equal the canonical
    counterpart subset (:data:`COUNTERPART_SOURCE_KINDS`) — the four
    transaction/invoice settlement kinds — so the operator surface and the core
    taxonomy can never drift.
    """
    contract = get_operator_surface_contract()
    operator_kinds = set(contract.source_kinds)

    assert all(isinstance(kind, BindingSourceKind) for kind in operator_kinds), (
        "operator surface source kinds must be BindingSourceKind members"
    )
    assert operator_kinds == set(COUNTERPART_SOURCE_KINDS), (
        "operator surface source kinds must exactly mirror the counterpart subset of "
        f"BindingSourceKind; unexpected operator-only={sorted(operator_kinds - set(COUNTERPART_SOURCE_KINDS))} "
        f"subset-only={sorted(set(COUNTERPART_SOURCE_KINDS) - operator_kinds)}"
    )
