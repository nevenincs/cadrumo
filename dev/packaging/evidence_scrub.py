r"""Scrub runner metadata out of distribution-evidence rows at mint time.

Every :class:`~dev.packaging.evidence.DistributionEvidence` row a packaging
lane mints is eventually published: it rides an evidence draft, is aggregated
by the promotion gates, and is attached to the final public release as a
self-evidencing asset. The raw oracle captures carry machine identifiers of
the runner that produced them — the operator's hostname, the account username
inside home-directory paths (``C:\\Users\\<name>``, ``/home/<name>``,
``/Users/<name>``), and workspace paths. None of that is evidence; all of it
is operator-machine metadata that must not ship (operator ruling 2026-07-20).

The scrub runs at emit time, before the row is first written, so exactly one
tamper-evident identity exists: the row's ``evidence_id`` is recomputed over
the scrubbed content through the same canonical-identifier path every consumer
validates. The transport below the readiness gate is unchanged — a scrubbed
row is an ordinary, fully valid ``DistributionEvidence``.

Fail-closed posture: normalization rewrites the three sanctioned leak shapes
(home-directory user segments, the runner's CI workspace root, and the
explicitly named machine tokens) across every string leaf; a *detection* sweep
then re-walks the whole document and raises :class:`EvidenceScrubError` on any
residual leak signature — including shapes the scrubber refuses to rewrite
because their meaning is unknown (UNC ``\\\\host\\share`` paths), and leaks
inside the cohort binding, which must stay byte-identical to the sealed cohort
and therefore can never be rewritten, only refused.

The workspace root is the absolute checkout/work-tree directory the lane ran in
(``GITHUB_WORKSPACE`` / ``RUNNER_WORKSPACE`` on a GitHub-hosted runner, e.g.
``D:\\a\\cadrumo\\cadrumo`` on Windows where no home segment or hostname token
appears). It leaks into every captured absolute path — a command ``cwd``, an
installed executable ``path``, an observation ``resolved_executable`` or
``storage_root`` — so its prefix is redacted to a placeholder token, leaving the
path tail (the venv/artefact structure that IS evidence) intact.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import re
from typing import TYPE_CHECKING, Final

from dev.packaging.evidence import (
    DistributionEvidence,
    EvidenceIdentityPayload,
    evidence_identifier,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

SCRUBBED_USER: Final[str] = "scrubbed-user"
SCRUBBED_MACHINE_ID: Final[str] = "scrubbed"
SCRUBBED_WORKSPACE: Final[str] = "scrubbed-workspace"

# The environment variables a CI runner exports for the absolute directory the
# lane checked out and worked in. Longer (more specific) roots are scrubbed
# before shorter ones so a nested root does not strand a parent prefix.
_WORKSPACE_ROOT_ENV_VARS: Final[tuple[str, ...]] = ("GITHUB_WORKSPACE", "RUNNER_WORKSPACE")

# A home-directory user segment on any platform, tolerant of doubled (JSON-
# escaped) separators embedded inside observation strings.
_HOME_USER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<prefix>(?:[A-Za-z]:)?[\\/]{1,2}(?:Users|home)[\\/]{1,2})(?P<user>[^\\/\"'\s]+)",
    re.IGNORECASE,
)

# A LEADING UNC host reference (``\\host\share``). Its share semantics are
# unknown, so the scrubber refuses rather than rewrites: detection-only. The
# lookbehind keeps escaped separators inside ordinary drive paths
# (``C:\\Users\\...`` embedded in serialized text) from false-positiving.
_UNC_HOST_RE: Final[re.Pattern[str]] = re.compile(r"(?<![\w:\\])[\\]{2,4}[A-Za-z0-9][A-Za-z0-9._-]*[\\/]")

# The cohort binding is a byte-exact copy of the sealed release authority
# (readiness re-derives and compares it), so it is never rewritten. A leak
# inside it is a build defect surfaced loudly, not silently normalized.
_UNSCRUBBABLE_TOP_LEVEL: Final[frozenset[str]] = frozenset({"cohort"})


class EvidenceScrubError(ValueError):
    """A machine-identifier leak survived scrubbing (or cannot be rewritten)."""


def default_runner_tokens() -> tuple[str, ...]:
    """Return this machine's own identifying tokens (hostname, username).

    The scrub runs on the machine that minted the row, so its own identity is
    exactly the runner metadata that must not ship.
    """
    return tuple(token for token in (platform.node(), getpass.getuser()) if token and len(token) >= 2)


def default_workspace_roots() -> tuple[str, ...]:
    """Return the runner's CI workspace-root paths, most specific first.

    The scrub runs on the machine that minted the row, so the checkout/work-tree
    directory it exports is exactly the workspace metadata that must not ship.
    Roots are ordered longest-first so a nested root (``GITHUB_WORKSPACE``) is
    redacted before its parent (``RUNNER_WORKSPACE``).
    """
    roots = {
        value
        for var in _WORKSPACE_ROOT_ENV_VARS
        if (value := os.environ.get(var, "").strip()) and len(value) >= 3
    }
    return tuple(sorted(roots, key=len, reverse=True))


def _token_pattern(token: str) -> re.Pattern[str]:
    """Match the token case-insensitively when not embedded in a larger word."""
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", re.IGNORECASE)


def _workspace_pattern(root: str) -> re.Pattern[str]:
    r"""Match an absolute workspace root, tolerant of separator style and doubling.

    The root is decomposed into path segments and rejoined with a separator class
    so ``D:\\a\\cadrumo\\cadrumo`` matches both raw and JSON-escaped
    (``D:\\\\a\\\\cadrumo``) serializations, and a POSIX
    ``/home/runner/work/repo/repo`` matches with its leading separator. Only the
    root prefix is matched; the path tail is preserved.
    """
    segments = [segment for segment in re.split(r"[\\/]+", root) if segment]
    if not segments:
        return re.compile(r"(?!)")  # matches nothing
    body = r"[\\/]{1,2}".join(re.escape(segment) for segment in segments)
    return re.compile(rf"[\\/]{{0,2}}{body}", re.IGNORECASE)


def _scrub_text(
    value: str,
    token_patterns: Iterable[re.Pattern[str]],
    workspace_patterns: Iterable[re.Pattern[str]] = (),
) -> str:
    scrubbed = value
    for pattern in workspace_patterns:
        scrubbed = pattern.sub(SCRUBBED_WORKSPACE, scrubbed)
    scrubbed = _HOME_USER_RE.sub(rf"\g<prefix>{SCRUBBED_USER}", scrubbed)
    for pattern in token_patterns:
        scrubbed = pattern.sub(SCRUBBED_MACHINE_ID, scrubbed)
    return scrubbed


def _walk_strings(node: object, pointer: str) -> Iterator[tuple[str, str]]:
    """Yield every string leaf with its JSON-pointer-style location."""
    if isinstance(node, str):
        yield pointer, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _walk_strings(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_strings(value, f"{pointer}/{index}")


def _rewrite_strings(
    node: object,
    token_patterns: tuple[re.Pattern[str], ...],
    workspace_patterns: tuple[re.Pattern[str], ...] = (),
) -> object:
    if isinstance(node, str):
        return _scrub_text(node, token_patterns, workspace_patterns)
    if isinstance(node, dict):
        return {key: _rewrite_strings(value, token_patterns, workspace_patterns) for key, value in node.items()}
    if isinstance(node, list):
        return [_rewrite_strings(value, token_patterns, workspace_patterns) for value in node]
    return node


def find_residual_leaks(
    document: dict[str, object],
    tokens: Iterable[str],
    workspace_roots: Iterable[str] = (),
) -> list[str]:
    """Return a description of every leak signature anywhere in the document.

    This is the fail-closed sweep: it is field-agnostic (a leak in a novel
    observation key is found exactly like one in a known path field) and runs
    over the *whole* row including the unscrubbable cohort binding.
    """
    token_patterns = [_token_pattern(token) for token in tokens]
    workspace_roots = tuple(workspace_roots)
    workspace_patterns = [_workspace_pattern(root) for root in workspace_roots]
    leaks: list[str] = []
    for pointer, value in _walk_strings(document, ""):
        for match in _HOME_USER_RE.finditer(value):
            if match.group("user") != SCRUBBED_USER:
                leaks.append(f"{pointer}: home-directory user segment {match.group('user')!r}")
        if _UNC_HOST_RE.search(value):
            leaks.append(f"{pointer}: UNC host path (refused, not rewritable)")
        for root, pattern in zip(workspace_roots, workspace_patterns, strict=True):
            if pattern.search(value):
                leaks.append(f"{pointer}: workspace root {root!r}")
        for pattern in token_patterns:
            if pattern.search(value):
                leaks.append(f"{pointer}: machine token {pattern.pattern!r}")
    return leaks


def scrub_distribution_evidence(
    evidence: DistributionEvidence,
    *,
    tokens: tuple[str, ...] | None = None,
    workspace_roots: tuple[str, ...] | None = None,
) -> DistributionEvidence:
    """Return the row with runner metadata scrubbed and its identity recomputed.

    Every string leaf outside the cohort binding is normalized (home-directory
    user segments, the runner's CI workspace root, and the machine's own
    hostname/username tokens); the whole row is then swept for residual leak
    signatures and refused on any hit. The result revalidates through the strict
    schema with a fresh, matching ``evidence_id``, so downstream consumers (the
    readiness gate above all) see an ordinary tamper-evident row.

    Args:
        evidence: The freshly minted row to scrub.
        tokens: The machine identifier tokens to redact; defaults to this
            machine's own hostname and username.
        workspace_roots: The absolute CI workspace roots to redact; defaults to
            the ``GITHUB_WORKSPACE`` / ``RUNNER_WORKSPACE`` paths this runner
            exports.

    Raises:
        EvidenceScrubError: A leak signature survived normalization — a UNC
            path, a leak inside the unscrubbable cohort binding, or a token
            reintroduced by the rewrite itself. Publication must not proceed.
    """
    machine_tokens = default_runner_tokens() if tokens is None else tokens
    roots = default_workspace_roots() if workspace_roots is None else workspace_roots
    token_patterns = tuple(_token_pattern(token) for token in machine_tokens)
    workspace_patterns = tuple(_workspace_pattern(root) for root in roots)
    document = evidence.model_dump(mode="json", exclude={"evidence_id"})
    scrubbed: dict[str, object] = {
        key: (value if key in _UNSCRUBBABLE_TOP_LEVEL else _rewrite_strings(value, token_patterns, workspace_patterns))
        for key, value in document.items()
    }
    residual = find_residual_leaks(scrubbed, machine_tokens, roots)
    if residual:
        raise EvidenceScrubError(
            "runner metadata survived scrubbing; refusing to mint the row:\n"
            + "\n".join(f"  - {leak}" for leak in residual),
        )
    payload = EvidenceIdentityPayload.model_validate_json(json.dumps(scrubbed))
    return DistributionEvidence(**payload.model_dump(), evidence_id=evidence_identifier(payload))


__all__ = [
    "SCRUBBED_MACHINE_ID",
    "SCRUBBED_USER",
    "SCRUBBED_WORKSPACE",
    "EvidenceScrubError",
    "default_runner_tokens",
    "default_workspace_roots",
    "find_residual_leaks",
    "scrub_distribution_evidence",
]
