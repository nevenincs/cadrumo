"""Assert a real produced path conforms to its declared storage-path grammar.

A ``StoragePathDefinition.grammar`` string is not merely descriptive for the
existing ``blob_manifest`` entry: ``blob_store/_blob_store.py`` parses it at
import time to derive its own shard-directory name and manifest suffix, so
the declaration is already load-bearing there. This module extends that same
idea to test-side verification for a parameterised fan-out shape (a content
hash prefix, a namespace, a per-run id) that cannot be expressed as an
enumerable :class:`~cadrumo.core.StorageCategory` member.

A test comparing the grammar against itself proves nothing. The contract
here is: read the grammar off the one declaration
(:data:`~cadrumo.adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`),
drive a REAL write through the REAL production code path, and assert the
REAL resulting path matches a regex derived from that grammar. A declaration
that drifts from what production actually writes reds the calling test
rather than passing because the test's own expectation drifted the same way.

:func:`literal_directory_runs` serves a second, independent gate: a grammar's
directory portion is a hand-written literal that duplicates a
:class:`~cadrumo.core.StorageCategory` member's ``subpath`` spelling, and
nothing previously compared the two spellings against each other -- a member
rename would leave every grammar that spelled its old name out silently
disagreeing. Extracting the literal runs lets a caller assert each one still
equals a live taxonomy subpath.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from ..adapters.persistence.storage._namespace_taxonomy import StoragePathKind

_PLACEHOLDER_PATTERNS: Final[dict[str, str]] = {
    # Content-hash fan-out (blob store, both root- and bucket-scoped).
    "sha256[:2]": r"[0-9a-f]{2}",
    "sha256": r"[0-9a-f]{64}",
    # Registry-verdict cache filename: a 16-lowercase-hex truncation of a
    # sha256 digest over the resolved registry root
    # (domain/calculations/registry/_verdict_cache.py:_ROOT_HASH_LEN).
    "sha256[:16]": r"[0-9a-f]{16}",
    # Observability per-run trace directory: 16 lowercase hex characters,
    # the shape core.observability.context._mint_run_id mints.
    "run_id": r"[0-9a-f]{16}",
    # ISO calendar date (llm-usage / llm-run-telemetry daily filenames).
    "timestamp": r"\d{4}-\d{2}-\d{2}",
    # Closed set: core.AuthProviderKind's members, spelled precisely rather
    # than bounded only by "not a path separator" like the free-form tokens
    # below. Non-capturing group is load-bearing: "|" has the lowest regex
    # precedence, so an ungrouped alternation would leak across the
    # surrounding literal segments the compiler splices this fragment into.
    "auth_provider_kind": r"(?:certificate|clave_movil|clave_permanente)",
    # A profile UUID, spelled precisely rather than as a free-form token: the
    # custody hold-evidence filenames are ``str(UUID)`` and nothing else, so
    # bounding them only by "not a path separator" would accept a filename the
    # owning authority cannot produce.
    "profile_id": r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    # Closed set: the two custody hold-evidence owners the derived join fans
    # out over. Same non-capturing-group reasoning as the provider kind above.
    "owner": r"(?:legal|filing)",
    # Free-form application-chosen identifiers: a bucket id, an outbound
    # namespace, an HMAC-prefix segment, an operator-mutable label, a
    # config-reset operation id, an LLM provider/model. None of these are
    # hash-shaped, so they are bounded only by "not a path separator".
    "bucket_id": r"[^/]+",
    "namespace": r"[^/]+",
    "hmac_prefix": r"[^/]+",
    "label": r"[^/]+",
    "operation_id": r"[^/]+",
    "provider": r"[^/]+",
    "model": r"[^/]+",
}

_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"<([^<>]+)>")


def _grammar_to_pattern(grammar: str, root: Path) -> re.Pattern[str]:
    """Compile ``grammar`` into a regex, substituting ``<root>`` for ``root``.

    Literal segments between placeholders are individually
    :func:`re.escape`-d; placeholder regex fragments are spliced in raw. This
    ordering matters -- escaping the whole template first would mangle the
    fragments' own regex metacharacters (``[``, ``]``, ``{``, ``}``).
    """
    parts: list[str] = []
    position = 0
    for match in _PLACEHOLDER_RE.finditer(grammar):
        parts.append(re.escape(grammar[position : match.start()]))
        token = match.group(1)
        if token == "root":  # noqa: S105 - grammar placeholder name, not a credential
            parts.append(re.escape(root.as_posix()))
        else:
            try:
                parts.append(_PLACEHOLDER_PATTERNS[token])
            except KeyError:
                raise AssertionError(
                    f"grammar placeholder <{token}> has no declared regex fragment in "
                    "_storage_path_grammar.py -- add one before pinning a test against it",
                ) from None
        position = match.end()
    parts.append(re.escape(grammar[position:]))
    return re.compile("".join(parts) + r"\Z")


def assert_path_matches_grammar(*, key: str, root: Path, produced: Path) -> None:
    """Assert ``produced`` conforms to the declared grammar shape for ``key``.

    Args:
        key: The :class:`~cadrumo.adapters.persistence.storage.StoragePathDefinition`
            registry key whose grammar governs the expected shape.
        root: The path ``<root>`` substitutes for in that grammar. Callers
            pass whatever anchor the specific grammar's ``<root>`` token
            means -- the blob store's own ``root_dir``, or the full storage
            root -- the helper does not assume which.
        produced: The real path a real production write produced.

    Raises:
        AssertionError: When ``produced`` does not match the compiled
            pattern, or when the grammar names a placeholder this module has
            no regex fragment for.
    """
    # Deferred: ``cadrumo.tests`` is imported at the earliest point in pytest
    # collection, before test-harness storage-root isolation is applied
    # (see the repo-root and src/cadrumo conftests). A module-level import
    # here would pull in ``adapters.persistence.storage`` -> the full
    # ``cadrumo.core`` facade -> a real module-level ``get_logger()`` call
    # reachable through it, binding the diagnostic-log FileHandler to
    # whatever storage root is active at THAT premature moment -- the
    # operator's real one, since isolation has not landed yet. This helper is
    # only ever called from inside a test body, well after isolation is in
    # place, so the import costs nothing to defer here.
    from ..adapters.persistence.storage._namespace_registry import STORAGE_NAMESPACE_REGISTRY

    definition = STORAGE_NAMESPACE_REGISTRY.path_by_key(key)
    pattern = _grammar_to_pattern(definition.grammar, root)
    produced_posix = produced.as_posix()
    assert pattern.match(produced_posix), (
        f"{produced_posix!r} does not match the declared grammar {definition.grammar!r} "
        f"for storage-path key {key!r} (compiled pattern: {pattern.pattern!r})"
    )


def literal_directory_runs(*, grammar: str, kind: StoragePathKind) -> tuple[str, ...]:
    """Return ``grammar``'s directory-portion literal runs, as POSIX subpaths.

    A grammar is split on ``/`` into path components. A component is a
    placeholder run (contains a ``<...>`` token) or a pure literal. Pure
    literals are collapsed into maximal consecutive runs and returned joined
    by ``/`` -- exactly the shape a :class:`~cadrumo.core.StorageLocation`
    ``subpath`` is declared in, so a caller can compare them directly.

    The terminal path component is excluded from consideration for
    :attr:`~cadrumo.adapters.persistence.storage.StoragePathKind.FILE` and
    :attr:`~...StoragePathKind.BLOB_OBJECT` grammars, because that component
    names the leaf itself (a filename or a content-addressed object), never a
    directory -- ``manifest.toml`` is not a directory a category could
    declare, and Family 3/4 filename shapes are deliberately governed by the
    grammar alone rather than promoted to a category. For
    :attr:`~...StoragePathKind.DIRECTORY` grammars the terminal component
    *is* a directory name and stays eligible when it is a pure literal (a
    parameterised terminal, e.g. ``<bucket_id>``, is never a literal and is
    excluded regardless).

    Args:
        grammar: A ``<root>``-anchored grammar string. Never call this for a
            :attr:`~...StoragePathKind.LOGICAL_SQL` grammar (a ``db://``
            logical path, not a filesystem path) -- callers must filter that
            kind out themselves.
        kind: The definition's :class:`~...StoragePathKind`.

    Returns:
        The literal directory runs, outermost first. Empty when the grammar
        has no directory portion at all (a bare ``<root>/<literal-file>``).
    """
    if not grammar.startswith("<root>"):
        raise AssertionError(
            f"grammar {grammar!r} is not <root>-anchored -- literal_directory_runs only "
            "applies to filesystem-kind grammars (filter LOGICAL_SQL out before calling)",
        )
    remainder = grammar[len("<root>") :].strip("/")
    if not remainder:
        return ()
    components = remainder.split("/")
    is_literal = ["<" not in component for component in components]
    # Deferred for the same early-collection reason as assert_path_matches_grammar above.
    from ..adapters.persistence.storage._namespace_taxonomy import StoragePathKind

    if kind in (StoragePathKind.FILE, StoragePathKind.BLOB_OBJECT):
        is_literal[-1] = False
    runs: list[str] = []
    current: list[str] = []
    for component, literal in zip(components, is_literal, strict=True):
        if literal:
            current.append(component)
        elif current:
            runs.append("/".join(current))
            current = []
    if current:
        runs.append("/".join(current))
    return tuple(runs)


def assert_grammar_vocabulary_is_declared(grammar: str) -> None:
    """Assert every ``<placeholder>`` token in ``grammar`` has a declared regex fragment.

    Thin wrapper over :func:`_grammar_to_pattern`'s own vocabulary check,
    exposed publicly so a gate can assert compilability without also needing
    a real ``<root>`` to substitute. Never call this for a
    :attr:`~adapters.persistence.storage.StoragePathKind.LOGICAL_SQL`
    grammar (a ``db://`` logical path uses its own tokens, e.g.
    ``<object_key>``, deliberately outside this filesystem-grammar
    compiler) -- callers must filter that kind out themselves.

    Raises:
        AssertionError: When ``grammar`` names a placeholder this module has
            no regex fragment for. The message names the offending token.
    """
    _grammar_to_pattern(grammar, Path("/grammar-vocabulary-probe-root"))
