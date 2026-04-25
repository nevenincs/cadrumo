"""Known-sanitised fixture SHAs for refuse-if-already-sanitised guard.

When :func:`sanitize_pdf` is called with bytes whose SHA-256 lives
in :data:`SANITIZED_SHAS`, the sanitiser refuses with
:class:`AlreadySanitizedError`. The set is populated with every
fixture committed under ``tests/fixtures/justificantes/`` so an
operator who points the sanitiser at a previously-sanitised fixture
gets a hard error rather than a silent no-op or double-stripped
output.

Callers can opt out per-call with
``sanitize_pdf(..., refuse_if_already_sanitized=False)`` for the
narrow case where intentionally re-sanitising a fixture is the
correct action (e.g. when extending the TokenMap to cover a new
PII surface against an existing capture).
"""

from __future__ import annotations

# Empty until the first fixture lands under
# ``tests/fixtures/justificantes/`` (phase 9 of the plan). Each
# entry is the lowercase hex SHA-256 of a committed sanitised PDF.
SANITIZED_SHAS: frozenset[str] = frozenset()
