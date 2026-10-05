"""Validated requester form extraction, kept separate from screen presentation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from textual.widgets import Checkbox, Input, Select, SelectionList

from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ....application.operations.registry import OperationFrontendProjection
from ....application.user_profile.access_contracts import AccessAction, DisclosureCategory
from ....application.user_profile.automation_enrollment import EnrollmentKind
from ....core.period import Period
from . import automation_requester_contracts as _contracts

if TYPE_CHECKING:
    from .automation_requester import RuntimeAutomationRequesterScreen


class RequesterDraftMixin:
    """Read UI selections and refuse every value outside registered choices."""

    def _bound(self: RuntimeAutomationRequesterScreen, client: RuntimeFrontendClient) -> bool:
        return (
            client.frontend is OperationFrontendProjection.TUI
            and client.profile_id == self._profile_id
            and (self._session_id is None or client.session_id == self._session_id)
        )

    @staticmethod
    def _optional_uuid(value: str) -> UUID | None:
        stripped = value.strip()
        if not stripped:
            return None
        parsed = UUID(stripped)
        if str(parsed) != stripped:
            raise ValueError("noncanonical UUID")
        return parsed

    def _draft(self: RuntimeAutomationRequesterScreen) -> _contracts.ProposalDraft:
        kind = self._selected_kind()
        operations = self._selected_operations()
        actions = self._selected_actions()
        disclosures = self._selected_disclosures()
        periods = self._selected_periods()
        expiry = datetime.fromisoformat(self.query_one("#automation-request-expiry", Input).value.strip())
        key_raw = self.query_one("#automation-request-key-expiry", Input).value.strip()
        key_expiry = datetime.fromisoformat(key_raw) if key_raw else None
        reference = self._optional_uuid(self.query_one("#automation-request-reference", Input).value)
        self._validate_reference(reference)
        return _contracts.ProposalDraft(
            kind=kind,
            operations=operations,
            actions=actions,
            disclosures=disclosures,
            periods=periods,
            period_independent=self.query_one("#automation-request-independent", Checkbox).value,
            delegation=self.query_one("#automation-request-delegation", Checkbox).value,
            expires_at=expiry,
            key_expires_at=key_expiry,
            unattended=self.query_one("#automation-request-unattended", Checkbox).value,
            os_lock=self.query_one("#automation-request-os-lock", Checkbox).value,
            target_grant_id=self._optional_uuid(self.query_one("#automation-request-grant", Input).value),
            target_key_id=self._optional_uuid(self.query_one("#automation-request-key", Input).value),
            credential_reference=reference,
        )

    def _selected_kind(self: RuntimeAutomationRequesterScreen) -> EnrollmentKind:
        kind = cast("Select[EnrollmentKind]", self.query_one("#automation-request-kind", Select)).value
        if not isinstance(kind, EnrollmentKind):
            raise ValueError("no request kind")
        if (self._client is None) != (kind is EnrollmentKind.ENROLL):
            raise ValueError("request kind does not match client admission")
        return kind

    def _selected_operations(self: RuntimeAutomationRequesterScreen) -> frozenset[str]:
        selected = frozenset(
            cast("SelectionList[str]", self.query_one("#automation-request-operations", SelectionList)).selected
        )
        if not selected.issubset(self._operation_choices):
            raise ValueError("undeclared operation")
        return selected

    def _selected_actions(self: RuntimeAutomationRequesterScreen) -> frozenset[AccessAction]:
        action_list = cast("SelectionList[str]", self.query_one("#automation-request-actions", SelectionList))
        return frozenset(AccessAction(value) for value in action_list.selected)

    def _selected_disclosures(
        self: RuntimeAutomationRequesterScreen,
    ) -> frozenset[tuple[str, DisclosureCategory]]:
        raw = frozenset(
            cast("SelectionList[str]", self.query_one("#automation-request-disclosures", SelectionList)).selected
        )
        if not raw.issubset(self._available_disclosure_values()):
            raise ValueError("undeclared disclosure")
        return frozenset(
            (schema, DisclosureCategory(category)) for schema, category in (value.split("|", 1) for value in raw)
        )

    def _available_disclosure_values(self: RuntimeAutomationRequesterScreen) -> set[str]:
        return {f"{schema}|{category.value}" for schema, category in self._disclosure_choices}

    def _selected_periods(self: RuntimeAutomationRequesterScreen) -> frozenset[Period] | None:
        mode = cast("Select[str]", self.query_one("#automation-request-period-mode", Select)).value
        if mode not in {"all", "none", "selected"}:
            raise ValueError("invalid period choice")
        if mode == "all":
            return None
        return frozenset(self._periods if mode == "selected" else ())

    def _validate_reference(self: RuntimeAutomationRequesterScreen, reference: UUID | None) -> None:
        if (self._client is None and reference is not None) or (self._client is not None and reference is None):
            raise ValueError("protected credential reference does not match request kind")
