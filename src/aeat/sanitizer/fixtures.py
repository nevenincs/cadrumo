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

# Lowercase hex SHA-256 of every committed sanitised PDF under
# ``tests/fixtures/justificantes/``. Updated whenever a new
# fixture lands.
SANITIZED_SHAS: frozenset[str] = frozenset(
    {
        # tests/fixtures/justificantes/100/2022-0A.pdf
        # Modelo 100 IRPF anual, ejercicio 2022, derived from a
        # live capture sanitised via aeat.sanitizer with 35
        # mapping entries (NIF, name, CSV, NRC, 28 importes,
        # 3 arbitrary). 149 replacement edits applied; verify-
        # clean, round-trips through parse_justificante.
        "55db81f29ac0947ff1d9e7442ffbb84c17798313bf83bd8a61801779e260e70d",
    },
)
