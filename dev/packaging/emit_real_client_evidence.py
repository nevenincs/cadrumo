"""Mint a sanctioned real-client claude-* row record from an operator capture.

The four required ``claude-*`` distribution rows are REAL-Claude-client claims:
they are satisfied only when the operator performs the tax-work call inside a real
Claude client (authenticated Claude Code, Claude Desktop, Claude Cowork). This is
the emission hook the operator runs the moment they complete that in-app capture.

It reconstructs the MCP protocol proof the operator's capture already produced
(the ``protocol_oracle`` document), captures a genuinely-owned bounded launch of
the same installed server (the real Claude client owns its own launch subprocess,
which we cannot capture, so the owned launch here proves the exact installed
server starts), and emits the flat client-row record - client-bound to the real
Claude client, with the operator's real client session retained as the real-client
dimension in ``result.observations``. The honesty guard permits the required row
because the client identity is a real Claude client, not the MCP SDK.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

from dev._paths import UTF_8

from ._acquire_common import capture_owned_server_launch
from .cohort_manifest import load_release_cohort
from .desktop_capture import collect_seed_secrets
from .distribution_evidence_emit import _mcp_evidence_from_mapping, emit_client_evidence
from .evidence import AcquisitionIdentity, ClientIdentity, DestinationIdentity
from .installed_mcp_oracle import isolated_mcp_environment

_DEFAULT_DISTRIBUTION_EVIDENCE_DIR: Final[Path] = Path("var/distribution-install-readiness")
_UTF_8: Final[str] = UTF_8

# A real-client session summary is a handful of short status fields
# (connected, status, tool_called, model, ...). Anything token-shaped or an
# email address is operator-supplied content that must not ship verbatim into a
# published claude-*.json row. The length floor mirrors
# ``desktop_capture.collect_seed_secrets``.
_SECRET_MIN_LENGTH: Final[int] = 32
_EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class RealClientSessionError(RuntimeError):
    """Raised when the operator-supplied session JSON carries secret-shaped content."""


def _iter_strings(value: Any) -> Iterator[str]:
    """Yield every string leaf in an arbitrarily nested JSON structure.

    Dict KEYS are yielded alongside values: a session JSON key is operator-typed
    text that can itself be secret-shaped or carry an email, so it must face the
    same refusals as a value.
    """
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_strings(item)


def assert_session_carries_no_secret(session_path: Path, session: object) -> None:
    """Refuse a session summary that carries a token-shaped string or an email.

    The session JSON ships verbatim into a published ``claude-*.json`` row, so it
    is scanned before minting. It reuses the ``collect_seed_secrets`` long-string
    heuristic (any value >= 32 chars is treated as a secret) and additionally
    walks every nested string — dict KEYS as well as values — refusing a
    token-length string or an email address wherever it appears.

    Raises:
        RealClientSessionError: On the first secret-shaped value found.
    """
    long_values = collect_seed_secrets(session_path)
    nested_long = tuple(text for text in _iter_strings(session) if len(text) >= _SECRET_MIN_LENGTH)
    emails = tuple(text for text in _iter_strings(session) if _EMAIL_PATTERN.search(text))
    if long_values or nested_long or emails:
        raise RealClientSessionError(
            "the real-client session JSON carries secret-shaped content (a token-length string or an email "
            "address) and cannot ship verbatim into a published claude-* evidence row. Keep the session summary "
            "to short, non-sensitive status fields (e.g. connected, status, tool_called, model), and redact any "
            "token or personal identifier before emitting evidence.",
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-id", required=True, help="The required claude-* row this capture proves.")
    parser.add_argument("--release-cohort-dir", required=True, type=Path, help="Full release-cohort directory.")
    parser.add_argument("--protocol-oracle", required=True, type=Path, help="The captured MCP protocol_oracle JSON.")
    parser.add_argument("--real-client-session", required=True, type=Path, help="The real Claude client session JSON.")
    parser.add_argument("--server", required=True, type=Path, help="The installed MCP server executable to launch.")
    parser.add_argument("--server-arg", action="append", default=[], help="An argument passed to the server (repeat).")
    parser.add_argument("--client-name", required=True, help="The real Claude client name (e.g. claude-desktop).")
    parser.add_argument("--client-version", required=True, help="The real Claude client version.")
    parser.add_argument("--client-executable", required=True, help="The real Claude client executable path.")
    parser.add_argument("--acquisition-source", required=True, help="Where the client acquired the artifact.")
    parser.add_argument("--destination-kind", required=True, help="The install/serve destination kind.")
    parser.add_argument("--destination-locator", required=True, help="The install/serve destination locator.")
    parser.add_argument("--launch-work-dir", required=True, type=Path, help="A fresh work dir for the owned launch.")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--distribution-evidence-dir", type=Path, default=None, help="Where the flat record lands.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Emit one sanctioned real-client claude-* row record from a capture."""
    args = _parser().parse_args(argv)
    cohort = load_release_cohort(args.release_cohort_dir)
    mcp_evidence = _mcp_evidence_from_mapping(json.loads(args.protocol_oracle.read_text(encoding=_UTF_8)))
    real_client_session = json.loads(args.real_client_session.read_text(encoding=_UTF_8))
    assert_session_carries_no_secret(args.real_client_session, real_client_session)

    work = args.launch_work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    launch_transcript = capture_owned_server_launch(
        server=args.server,
        server_args=tuple(args.server_arg),
        env=isolated_mcp_environment(work / "launch-storage"),
        cwd=work,
        timeout_seconds=args.timeout_seconds,
    )

    path = emit_client_evidence(
        directory=(args.distribution_evidence_dir or _DEFAULT_DISTRIBUTION_EVIDENCE_DIR),
        row_id=args.row_id,
        cohort=cohort,
        mcp_evidence=mcp_evidence,
        launch_transcript=launch_transcript,
        client=ClientIdentity(
            name=args.client_name,
            version=args.client_version,
            executable=args.client_executable,
        ),
        acquisition=AcquisitionIdentity(mechanism="real-claude-client", source=args.acquisition_source),
        destination=DestinationIdentity(
            kind=args.destination_kind,
            locator=args.destination_locator,
            version=cohort.manifest.version,
        ),
        real_client_session=real_client_session,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
