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
        # 100/2022-0A.pdf — IRPF anual 2022
        "55db81f29ac0947ff1d9e7442ffbb84c17798313bf83bd8a61801779e260e70d",
        # 111/2024-{1T,2T,3T,4T}.pdf — retenciones quarterly 2024
        "ffbb5281e812abf09a7cdbdc2509707a4bb18754064a60a4636dee57a96e5bef",
        "3ea14170b5e49ee206884817896ebddf718f4d024f6cb24f6e6f22ed78202d30",
        "8d428cc8226a750ae58fbf7dfc51284b7a208c3fec74689435e21ef45b5f9d16",
        "4848107bfd105a58b36f69f147180416ac3e666cf2dde95618ab72d175d7089e",
        # 130/2024-{1T,2T,3T,4T}.pdf — IRPF fraccionado quarterly 2024
        "7412ae6370585d41df446c0275f4323b112de92466ca2d7280c34292d9933784",
        "09c9ad0793b02c2010e8ea41276edf7550e602254f9b2893913cab92bb3d1b4e",
        "f2fe642e06e75d61c60860f6aaf06ab89b1a5b3fdd3f1e7f5c8c1f2c6fc38e8d",
        "88bcc09b0bf384ce5cfce12d1a8eebe56f8eec716d8f7fa38358573de97c461f",
        # 190/2024-0A.pdf — resumen anual retenciones 2024
        "5bf3d4be88dbb62c4b698ff2e53b56ffb49643a3d7270a1a94b86fb6ca3b6b89",
        # 303/2024-{1T,2T,3T,4T}.pdf — IVA quarterly 2024
        "53e69e77c61cb8aa23bec7c8acb0849fea56cc237c59f1d7ffc5887f53fb7048",
        "a3ff9bf99bb6386a3f565ed39a0e43394c0fa9de617e087a1ee80ea31f3e8906",
        "24d4c76e17ce3a940b895ad536263fc748c472b390dfa583f0c2b7af8b87ccbc",
        "6b7b5d4b2f3f3a33d1a16ea88fb70dfa0c1763f8378c2a7ad819c1fb4e4a81fe",
        # 390/2023-0A.pdf — IVA anual 2023
        "0ddec4d94235931aca58dcb959cf400f4b3e2595beb6d98ecb43bd9cb8a92ec4",
    },
)
