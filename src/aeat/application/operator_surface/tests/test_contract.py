"""Tests for the backend-owned operator surface contract."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind
from ....core.aggregation import COUNTERPART_SOURCE_KINDS
from ....core.config import override_settings
from ....core.errors import get_registered_error_code
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
from .._models import LifecycleContract, RootSurface

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _pin_english_locale() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction] - autouse fixture
    """Pin the operator-surface contract tests to the English locale.

    The contract surface (help paragraphs, error messages) is rendered
    through the project locale layer. These tests assert against the
    canonical English strings, so we pin the locale here rather than
    coupling the assertions to whatever the default locale happens to be
    in any given environment.
    """
    with override_settings(aeat_output_language="en"):
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
        root.purpose = "mutated"


def test_operator_surface_application_package_has_no_typer_dependency() -> None:
    module_sources = [
        inspect.getsource(operator_surface),
        inspect.getsource(operator_surface._contract),  # pyright: ignore[reportPrivateUsage] - boundary test
        inspect.getsource(operator_surface._help),  # pyright: ignore[reportPrivateUsage] - boundary test
        inspect.getsource(operator_surface._models),  # pyright: ignore[reportPrivateUsage] - boundary test
    ]
    joined = "\n".join(module_sources)

    assert "typer" not in joined.lower()
    assert "entrypoints.cli" not in joined


def test_log_fields_and_error_codes_are_backend_owned() -> None:
    contract = get_operator_surface_contract()

    assert contract.log_fields.as_extra() == {
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
    assert by_domain[MountedCommandDomain.PROFILE].service_owner == "aeat.application.user_profile"
    assert {"create", "edit", "show", "delete", "status"}.issubset(by_domain[MountedCommandDomain.PROFILE].commands)
    custody_commands = {
        command
        for family in contract.command_families
        if family.domain is MountedCommandDomain.CUSTODY
        for command in family.commands
    }
    assert {"lock", "switch", "rekey", "recover", "show-recovery", "verify-recovery"} == custody_commands
    # The append-only event-history verb merged into the `config profile` group
    # as `config profile history` (D1 family rename); the standalone
    # `config bucket` group was retired, so there is no BUCKET family.
    assert MountedCommandDomain.BUCKET not in by_domain
    assert "history" in by_domain[MountedCommandDomain.PROFILE].commands
    assert by_domain[MountedCommandDomain.OVERVIEW].mutability is OperatorMutability.READ_ONLY
    assert by_domain[MountedCommandDomain.LEDGER].service_owner == "aeat.application.transactions"
    assert by_domain[MountedCommandDomain.REVIEW].service_owner == "aeat.application.review"

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
    assert ("aeat config " + "init") not in root_text
    assert "aeat app ledger import" in root_text
    assert "aeat app live filed list" in root_text
    assert "aeat app live filed pull" in app_text
    assert "aeat config bucket" not in root_text
    assert "aeat config bucket" not in config_text
    assert "aeat config profile history" in config_text
    assert "aeat app invoice" not in app_text
    assert "aeat app declaration" not in app_text


def test_help_command_rows_are_backed_by_mounted_command_families() -> None:
    contract = get_operator_surface_contract()
    mounted = {(family.root.value, family.child) for family in contract.command_families}

    for surface in ("root", "config", "app"):
        document = build_help_document(surface)
        for section in document.sections:
            for entry in section.entries:
                if " -> " in entry.command or "rejected" in entry.command:
                    continue
                tokens = entry.command.split()
                assert tokens[0] == "aeat"
                assert (tokens[1], tokens[2]) in mounted


def test_root_landing_report_reads_profile_state_input_only() -> None:
    missing = build_root_landing_report(None)
    active = build_root_landing_report("operator")

    assert missing.command == "aeat config profile create NAME"
    assert missing.active_profile is None
    assert active.command == "aeat app overview status"
    assert active.active_profile == "operator"


def test_filing_status_filed_is_sole_source_for_filed_token() -> None:
    """FilingStatus.FILED is the single authoritative source for the ``"filed"`` token.

    This test verifies that:
    - The LIVE command-family contract exposes the token through FilingStatus.FILED,
      not a bare string literal.
    - The operator-surface contract source contains no bare ``"filed"`` string
      that would silently diverge from the enum definition.
    - FilingStatus.FILED evaluates to the expected string value.
    """
    # The enum member itself must carry the correct token value.
    assert FilingStatus.FILED == "filed"
    assert str(FilingStatus.FILED) == "filed"

    # The LIVE family must declare exactly the filed sub-command via the enum.
    contract = get_operator_surface_contract()
    live_family = next(f for f in contract.command_families if f.domain is MountedCommandDomain.LIVE)
    assert FilingStatus.FILED in live_family.commands

    # The contract module source must not contain bare "filed" string literals
    # outside of the FilingStatus import/usage lines.  We inspect the source and
    # verify every occurrence of the token '"filed"' is the FilingStatus import or
    # usage, not a stand-alone bare literal in a tuple or keyword argument.
    contract_source = inspect.getsource(operator_surface._contract)  # pyright: ignore[reportPrivateUsage] - boundary test
    # All occurrences of the raw token must be attributable to FilingStatus references.
    bare_literal_count = contract_source.count('"filed"')
    # Each FilingStatus reference in the source accounts for one use of the token
    # (import line and usage site).  No bare literal should exist beyond that.
    assert bare_literal_count == 0, (
        f"Found {bare_literal_count} bare '\"filed\"' literal(s) in _contract.py; "
        "all occurrences must be replaced with FilingStatus.FILED"
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
