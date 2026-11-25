"""The read flows a capture may run, and the selectors that name them.

This module imports no product or browser code, so listing a plan and refusing a
run touch nothing. A flow here runs the same adapter reader its registered
operation runs in the profile worker. The worker starts Python isolated and has no
capture hook by design, so the capture runs those readers in its own process
instead of driving the CLI.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

AUTH_POLICY: Final = "aeat-clave-movil-auth-browser-actions"
IDENTITY_POLICY: Final = "aeat-sede-signed-in-identity-read"
CENSAL_POLICY: Final = "aeat-sede-censal-datos-read"
DECLARATIONS_POLICY: Final = "aeat-sede-declarations-read"
WALLET_POLICY: Final = "aeat-sede-iva-compensation-wallet-read"
NOTIFICATIONS_POLICY: Final = "aeat-sede-notifications-read"
GROI_POLICY: Final = "aeat-groi-direct-driver-read"


class UnknownFlowSelectorError(ValueError):
    """A selector names no read flow, which includes every write or unread-opening command."""


@dataclass(frozen=True)
class ReadFlow:
    """One planned capture flow and the evidence that it reads only."""

    flow_id: str
    cli_command: str
    reader: str
    policy_ids: tuple[str, ...]
    needs_session: bool
    lane_tests: tuple[str, ...]
    read_only_because: str


LOGIN: Final = "clave-movil-login"

READ_FLOWS: Final[tuple[ReadFlow, ...]] = (
    ReadFlow(
        flow_id=LOGIN,
        cli_command="cadrumo-runtime config auth login --fresh",
        reader="application.auth.sessions.ensure_authenticated_aeat_session(fresh=True)",
        policy_ids=(AUTH_POLICY, IDENTITY_POLICY),
        needs_session=False,
        lane_tests=(
            "src/cadrumo/adapters/outbound/aeat/auth/tests/test_clave_movil_live.py"
            "::test_clave_movil_provider_full_login_with_central_playwright_when_explicitly_enabled",
        ),
        read_only_because=(
            "Identity choreography only: it reads the login pages and continues in the taxpayer's own name. "
            "It changes no tax, filing, censal or notification state; the session is stored encrypted locally."
        ),
    ),
    ReadFlow(
        flow_id="censo",
        cli_command="aeat config profile censo pull",
        reader="adapters.outbound.aeat.sede.censal_datos.fetch_censal_datos",
        policy_ids=(CENSAL_POLICY,),
        needs_session=True,
        lane_tests=(),
        read_only_because=(
            "The reader refuses a modification landing and clicks only the page's consultation controls. "
            "The result is dropped, so nothing is adopted into a profile, unlike the command's --apply."
        ),
    ),
    ReadFlow(
        flow_id="filed-declarations",
        cli_command="aeat app live filed pull",
        reader="adapters.outbound.aeat.sede.declarations: walk_declarations_register, capture_observation",
        policy_ids=(DECLARATIONS_POLICY,),
        needs_session=True,
        lane_tests=(
            "src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_live.py"
            "::test_walk_modelo_100_returns_at_least_one_declaration",
            "src/cadrumo/adapters/outbound/aeat/sede/tests/test_declarations_live.py"
            "::test_register_session_capture_observation_returns_pdf_bytes",
        ),
        read_only_because=(
            "Fills the search form of the filed-declarations query and fetches one existing justificante. "
            "The fetched bytes are dropped and no filing form is opened."
        ),
    ),
    ReadFlow(
        flow_id="iva-wallet",
        cli_command="aeat app live iva-wallet pull",
        reader="adapters.outbound.aeat.sede.iva_compensation_wallet.fetch_iva_compensation_wallet",
        policy_ids=(WALLET_POLICY,),
        needs_session=True,
        lane_tests=(
            "src/cadrumo/adapters/outbound/aeat/sede/tests/test_iva_compensation_wallet_live.py"
            "::test_fetch_iva_compensation_wallet_live_returns_read_observation",
        ),
        read_only_because=(
            "Runs the wallet's own query form under the reader's HTTP, landing and browser-action guards. "
            "The representation screen is answered in the taxpayer's own name; the reader saves and submits nothing."
        ),
    ),
    ReadFlow(
        flow_id="notifications",
        cli_command="aeat app live notifications pull",
        reader="adapters.outbound.aeat.sede.notifications.fetch_notifications_query",
        policy_ids=(NOTIFICATIONS_POLICY,),
        needs_session=True,
        lane_tests=(
            "src/cadrumo_runtime/host/tests/frontend/cli/test_live_notifications_pull_route.py"
            "::test_live_notifications_pull_persists_a_grounded_snapshot_and_no_remote_write",
        ),
        read_only_because=(
            "Two GET navigations, summary and query, parse the list without clicking a row, so unread rows stay "
            "unread. The document reader is never called, and the listener stops the detail path in every flow."
        ),
    ),
    ReadFlow(
        flow_id="groi",
        cli_command="aeat app live verify tgvi",
        reader="adapters.outbound.aeat.sede.groi_check.collect_groi_observations",
        policy_ids=(GROI_POLICY,),
        needs_session=False,
        lane_tests=(
            "src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check_live.py"
            "::test_groi_collector_returns_valid_verdict_for_registered_telefonica_nif",
        ),
        read_only_because=(
            "A POST to the consult servlet for one public corporate NIF, in a context with no taxpayer session. "
            "The verdict is dropped."
        ),
    ),
)


def _selectors(flow: ReadFlow) -> Iterable[str]:
    yield flow.flow_id
    yield flow.cli_command
    yield flow.cli_command.removeprefix("aeat ")
    yield from flow.lane_tests


def _named_flow_ids(selectors: tuple[str, ...]) -> set[str]:
    wanted: set[str] = set()
    for selector in selectors:
        matches = [flow for flow in READ_FLOWS if selector in _selectors(flow)]
        if not matches:
            raise UnknownFlowSelectorError(f"Not a capture read flow: {selector!r}")
        wanted.update(flow.flow_id for flow in matches)
    return wanted


def select_flows(selectors: Iterable[str] = ()) -> tuple[ReadFlow, ...]:
    """Resolve flow ids, CLI commands or lane test ids, adding the login a selected flow needs.

    No selector means the whole catalogue. The result keeps catalogue order, so
    the login always runs first.
    """
    named = tuple(selectors)
    if not named:
        return READ_FLOWS
    wanted = _named_flow_ids(named)
    if any(flow.needs_session and flow.flow_id in wanted for flow in READ_FLOWS):
        wanted.add(LOGIN)
    return tuple(flow for flow in READ_FLOWS if flow.flow_id in wanted)
