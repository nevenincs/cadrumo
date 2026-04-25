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
        # Modelo 100 IRPF anual ejercicio 2022.
        "55db81f29ac0947ff1d9e7442ffbb84c17798313bf83bd8a61801779e260e70d",
        # tests/fixtures/justificantes/111/2024-1T.pdf
        # Modelo 111 retenciones quarterly Q1 2024.
        "ffbb5281e812abf09a7cdbdc2509707a4bb18754064a60a4636dee57a96e5bef",
        # tests/fixtures/justificantes/130/2024-1T.pdf
        # Modelo 130 IRPF fraccionado quarterly Q1 2024.
        "7412ae6370585d41df446c0275f4323b112de92466ca2d7280c34292d9933784",
        # tests/fixtures/justificantes/190/2024-0A.pdf
        # Modelo 190 retenciones resumen anual 2024.
        "5bf3d4be88dbb62c4b698ff2e53b56ffb49643a3d7270a1a94b86fb6ca3b6b89",
        # tests/fixtures/justificantes/303/2024-1T.pdf
        # Modelo 303 IVA quarterly Q1 2024.
        "53e69e77c61cb8aa23bec7c8acb0849fea56cc237c59f1d7ffc5887f53fb7048",
        # tests/fixtures/justificantes/390/2023-0A.pdf
        # Modelo 390 IVA anual 2023.
        "0ddec4d94235931aca58dcb959cf400f4b3e2595beb6d98ecb43bd9cb8a92ec4",
    },
)
