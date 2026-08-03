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
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from ..adapters.persistence.storage import STORAGE_NAMESPACE_REGISTRY

_PLACEHOLDER_PATTERNS: Final[dict[str, str]] = {
    # Content-hash fan-out (blob store, both root- and bucket-scoped).
    "sha256[:2]": r"[0-9a-f]{2}",
    "sha256": r"[0-9a-f]{64}",
    # Observability per-run trace directory: 16 lowercase hex characters,
    # the shape core.observability._context._mint_run_id mints.
    "run_id": r"[0-9a-f]{16}",
    # Free-form application-chosen identifiers: a bucket id, an outbound
    # namespace, an HMAC-prefix segment, an operator-mutable label, a
    # config-reset operation id. None of these are hash-shaped, so they are
    # bounded only by "not a path separator".
    "bucket_id": r"[^/]+",
    "namespace": r"[^/]+",
    "hmac_prefix": r"[^/]+",
    "label": r"[^/]+",
    "operation_id": r"[^/]+",
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
    definition = STORAGE_NAMESPACE_REGISTRY.path_by_key(key)
    pattern = _grammar_to_pattern(definition.grammar, root)
    produced_posix = produced.as_posix()
    assert pattern.match(produced_posix), (
        f"{produced_posix!r} does not match the declared grammar {definition.grammar!r} "
        f"for storage-path key {key!r} (compiled pattern: {pattern.pattern!r})"
    )
