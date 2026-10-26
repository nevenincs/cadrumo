"""Admit the TUI review server to the local tailnet address."""

from __future__ import annotations

import ipaddress
import shutil
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

TAILSCALE_TIMEOUT_SECONDS: Final[float] = 10.0


class TailnetUnavailableError(RuntimeError):
    """This machine has no tailnet address to bind."""


class _TailscaleSelf(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    tailscale_ips: tuple[str, ...] = Field(default=(), alias="TailscaleIPs")
    dns_name: str = Field(default="", alias="DNSName")


class _TailscaleStatus(BaseModel):
    """The two facts this server needs from ``tailscale status --json``; the rest is ignored."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    backend_state: str = Field(alias="BackendState")
    self_node: _TailscaleSelf | None = Field(default=None, alias="Self")


@dataclass(frozen=True)
class TailnetNode:
    """This machine as Tailscale describes it."""

    address: str
    """The node's tailnet IPv4 address; the only address the server binds by default."""
    name: str | None
    """The node's MagicDNS name, when MagicDNS gives it one."""


def parse_tailnet_status(payload: str) -> TailnetNode:
    """Read this node's address and name out of ``tailscale status --json`` output.

    Anything short of a running client with an IPv4 address is refused: the
    caller would otherwise have nothing safe to bind.
    """
    try:
        status = _TailscaleStatus.model_validate_json(payload)
    except ValidationError:
        raise TailnetUnavailableError("tailscale status printed something this tool cannot read") from None
    if status.backend_state != "Running":
        raise TailnetUnavailableError(f"Tailscale is {status.backend_state}, not Running")
    node = status.self_node
    addresses = () if node is None else tuple(value for value in node.tailscale_ips if _is_ipv4(value))
    if node is None or not addresses:
        raise TailnetUnavailableError("Tailscale reports no IPv4 tailnet address for this machine")
    return TailnetNode(address=addresses[0], name=node.dns_name.rstrip(".") or None)


def tailnet_node() -> TailnetNode:
    """Ask the local Tailscale client for this machine's tailnet address and name.

    Tailscale is the authority on its own addressing, so the answer is read
    from the client rather than inferred from routes or address ranges.
    """
    executable = shutil.which("tailscale")
    if executable is None:
        raise TailnetUnavailableError("the tailscale command is not on PATH")
    try:
        result = run_command(
            [executable, "status", "--json", "--peers=false"],
            cwd=REPO_ROOT,
            errors="replace",
            timeout_seconds=TAILSCALE_TIMEOUT_SECONDS,
        )
    except OSError as failure:
        raise TailnetUnavailableError(f"tailscale status could not run: {failure}") from failure
    if result.returncode != 0:
        reason = _first_line(result.stderr) or _first_line(result.stdout) or "no output"
        raise TailnetUnavailableError(f"tailscale status exited {result.returncode}: {reason}")
    return parse_tailnet_status(result.stdout)


def _is_ipv4(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).version == 4
    except ValueError:
        return False


def is_wildcard_host(host: str) -> bool:
    """Whether binding ``host`` would listen on every interface."""
    if not host.strip():
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_unspecified
    except ValueError:
        return False


def _first_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""
