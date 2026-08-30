"""Tests for the backend-owned operator surface contract.

The suite pins the command roots, mounted command families, lifecycle tokens,
parser-only source-kind aliases, help documents, and registered refusal error
used by entrypoint adapters. It deliberately exercises the application-owned
contract as data so entrypoint adapters cannot redefine operator vocabulary in
their own layers.

The live reconciliation against the materialised Click tree lives in the
sibling ``test_contract_live.py``: it is integration-scope, and the marker
taxonomy allows one execution-scope marker per module.

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
    :mod:`~entrypoints.cli`
        Entrypoint layer consuming the contract without owning it.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.application.operator_surface.tests._contract_locale_fixture import pin_english_locale

from .. import LocaleManager
from ..manager import locale_catalogue_source

__all__ = ["pin_english_locale"]

from cadrumo.application import operator_surface
from cadrumo.application.operator_surface.contract import (
    get_operator_surface_contract,
    require_accepted_root,
    resolve_source_kind_alias,
)
from cadrumo.application.operator_surface.errors import OperatorSurfaceContractError
from cadrumo.application.operator_surface.help import (
    build_help_document,
    build_root_landing_report,
    render_help_text,
)
from cadrumo.application.operator_surface.help_models import (
    HelpDocument,
    HelpEntry,
    HelpSection,
    RootLandingReport,
)
from cadrumo.application.operator_surface.models import (
    FamilyMountState,
    FilingStatus,
    LifecycleContract,
    ModeloLifecycleStep,
    MountedCommandDomain,
    MountedCommandFamily,
    OperatorMutability,
    RootSurface,
    RootSurfaceName,
)
from cadrumo.application.operator_surface import help as _help_module
from cadrumo.core import BindingSourceKind
from cadrumo.core.aggregation import COUNTERPART_SOURCE_KINDS
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.core.external_constants import OutputLanguage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
    # Which verbs a family contains is not asserted here, and cannot be: the
    # contract declares no command inventory, so the live tree is the only
    # answer and this unit module does not resolve it. Membership is proven
    # against the materialised tree in `test_contract_live`.
    custody_children = {
        family.child for family in contract.command_families if family.domain is MountedCommandDomain.CUSTODY
    }
    assert custody_children == {"login", "logout", "passphrase"}
    # The append-only event-history verb merged into the `config profile` group
    # as `config profile history` (D1 family rename); the standalone
    # `config bucket` group was retired, so there is no BUCKET family.
    assert MountedCommandDomain.BUCKET not in by_domain
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

    # The two-root contract is asserted from the contract, not from a sentence
    # about it. This line used to pin a full English paragraph, which made a
    # locale catalogue the test's real authority: rewording the help in the
    # catalogue reddened this gate without changing any behaviour it guards.
    assert frozenset(surface.name for surface in get_operator_surface_contract().roots) == {
        RootSurfaceName.CONFIG,
        RootSurfaceName.APP,
    }
    assert root.paragraphs, "the root help document rendered no prose at all"
    assert "aeat config profile create NAME" in root_text
    # Asserted on BOTH documents, and the root half is the load-bearing one.
    # These are live, settings-bound, operator-settable variables, so an
    # operator who never reaches `config --help` must still be able to find
    # them: discoverability of a settable knob is part of the surface, not
    # decoration on it. This assertion was briefly moved to config-only after
    # the root landing was shortened, which made this test pass over a real
    # regression -- following content to where it went, without asking whether
    # it was entitled to go there.
    assert "CADRUMO_LOCAL_STORAGE_ROOT" in root_text
    assert "CADRUMO_SECRET_STORE_DIR" in root_text
    assert "CADRUMO_LOCAL_STORAGE_ROOT" in config_text
    assert "CADRUMO_SECRET_PASSPHRASE" not in config_text
    for option in (
        "--profile-secrets-stdin",
        "--profile-secrets-fd",
        "--secrets-stdin",
        "--secrets-fd",
    ):
        assert option in config_text
    assert ("aeat config " + "init") not in root_text
    assert "aeat app ledger import" in root_text
    assert "aeat app modelo verification-report list" in root_text
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
    assert "aeat app modelo verification-report list" in root_text
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
                    if all(token.startswith("-") for token in tokens[1:]):
                        continue
                    if len(tokens) == 2:
                        assert tokens[1] in {root for root, _child in mounted}
                        continue
                    adjacent_pairs = set(pairwise(tokens[1:]))
                    assert adjacent_pairs & mounted


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
        # A catalogue ships as a shard directory or a flat file; resolving the
        # shape here rather than hardcoding one keeps this cap check from
        # raising -- and a gate that raises is a gate that stopped checking.
        source = locale_catalogue_source(manager.locales_dir, locale.value)
        assert source is not None, f"no committed catalogue for {locale.value!r}; the cap check would be vacuous"
        catalogue = manager.load_locale(source)
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
    unavailable = build_root_landing_report(None, profile_selected=True)
    registered = build_root_landing_report(None, registered_profile_count=1)

    assert missing.command == "aeat config profile create NAME"
    assert missing.profile_selected is False
    assert missing.active_profile is None
    assert active.command == "aeat app overview status"
    assert active.profile_selected is True
    assert active.active_profile == "operator"
    assert unavailable.command == "aeat config repair profile"
    assert unavailable.profile_selected is True
    assert unavailable.active_profile is None
    assert registered.command == "aeat config login NAME"
    assert registered.profile_selected is False
    assert registered.active_profile is None


def test_filing_status_filed_is_sole_source_for_filed_token() -> None:
    """FilingStatus.FILED is the token the LIVE command family mounts.

    The membership half of this claim moved to ``test_contract_live``: the
    contract no longer restates a family's verbs, so whether ``app live``
    mounts a ``filed`` subgroup is a question only the materialised tree can
    answer. What stays here is the token identity itself.
    """
    assert FilingStatus.FILED == "filed"
    assert str(FilingStatus.FILED) == "filed"

    contract = get_operator_surface_contract()
    live_family = next(f for f in contract.command_families if f.domain is MountedCommandDomain.LIVE)
    assert live_family.child == "live"


def test_no_family_is_left_declared_unimplemented() -> None:
    """Custody passphrase rotation shipped; nothing else claims an owed gap.

    The global recovery facade left no declaration behind either, so the two
    dispositions (retired vs. owed-but-unbuilt) do not quietly converge.
    """
    contract = get_operator_surface_contract()
    by_child = {family.child: family for family in contract.command_families}

    unmounted = {
        family.child
        for family in contract.command_families
        if family.mount_state is FamilyMountState.DECLARED_UNIMPLEMENTED
    }
    assert unmounted == set()

    assert "recover" not in by_child
    assert "recovery" not in by_child


def test_a_mounted_family_may_not_carry_an_unimplemented_reason() -> None:
    """A shipped capability must lose its gap note, not keep it as decoration."""
    with pytest.raises(ValidationError, match="only a declared-unimplemented family"):
        MountedCommandFamily(
            domain=MountedCommandDomain.CUSTODY,
            root=RootSurfaceName.CONFIG,
            child="login",
            operator_question="authenticate a taxpayer profile",
            service_owner="cadrumo.application.user_profile",
            mutability=OperatorMutability.LOCAL_STATE_MUTATING,
            unimplemented_reason="stale note left behind after the capability shipped",
        )


def test_an_unimplemented_family_must_name_the_capability_it_waits_on() -> None:
    """Without a stated reason the marker is an unattributable silencer."""
    with pytest.raises(ValidationError, match="must state the capability"):
        MountedCommandFamily(
            domain=MountedCommandDomain.CUSTODY,
            root=RootSurfaceName.CONFIG,
            child="passphrase",
            operator_question="rotate the profile custody passphrase",
            service_owner="cadrumo.application.user_profile",
            mutability=OperatorMutability.LOCAL_STATE_MUTATING,
            mount_state=FamilyMountState.DECLARED_UNIMPLEMENTED,
        )


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
