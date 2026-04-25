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
        # 100/{2021,2022,2023}-0A.pdf — IRPF anual
        "eceeb78005b7afa247cc2544f1022fec879164f24c8f1a6048f2fbc826f1e7f1",
        "55db81f29ac0947ff1d9e7442ffbb84c17798313bf83bd8a61801779e260e70d",
        "d300d49a8ce4400f220748d3da317fbb5369557095c2f70cc5da89bcd72105ac",
        # 111/2024-{1T,2T,3T,4T}.pdf — retenciones quarterly 2024
        "ffbb5281e812abf09a7cdbdc2509707a4bb18754064a60a4636dee57a96e5bef",
        "3ea14170b5e49ee206884817896ebddf718f4d024f6cb24f6e6f22ed78202d30",
        "8d428cc8226a750ae58fbf7dfc51284b7a208c3fec74689435e21ef45b5f9d16",
        "4848107bfd105a58b36f69f147180416ac3e666cf2dde95618ab72d175d7089e",
        # 130/2021-{2T,3T,4T}.pdf — IRPF fraccionado quarterly 2021
        "a35c521ed5c1bd041da202dc01c604e562bd9bf6405cad12251d03b3ed80476e",
        "04b708479ddd3de29c4054c13632d89d0918a9782b4bf9b5db1e140b3a2ae669",
        "bd48fdb248a56833943ac67162f4012ddbde743de01654c17ecb12fce06ed6c5",
        # 130/2022-{1T,2T,3T,4T}.pdf — IRPF fraccionado quarterly 2022
        "4fc0bd41f7a533cef016e7fd605ba12d889cb41fb9ade565f0d698375a170b1d",
        "c9519c886cb0ebf4e972b186a2977491f2db969e918d0c6d29c90145d367563a",
        "12dd7517bac208920ef437c1ca2a3cf7b6ee9c2e24e6a85713770a91745d3dfb",
        "0972c53aa0a96ff19d02c0db4144f368c18683c1d009ccd641ed1b79711ff074",
        # 130/2023-{1T,2T,3T,4T}.pdf — IRPF fraccionado quarterly 2023
        "10a5dddaffc4c6a5561e68a82861d8fc87a17276931e2a477119719a845de4e8",
        "20815c99be1ff9527dc135fdb5a2b3c45018675312cd891fc9fd14f8a70adf1a",
        "17de80cbcde61ed363a92e8cf4650443d83409d9535b2ad20aeae64d899df486",
        "0c9c69c90f9665c207104f6a888e15c0741398153cad5f7c514959903284a31c",
        # 130/2024-{1T,2T,3T,4T}.pdf — IRPF fraccionado quarterly 2024
        "7412ae6370585d41df446c0275f4323b112de92466ca2d7280c34292d9933784",
        "09c9ad0793b02c2010e8ea41276edf7550e602254f9b2893913cab92bb3d1b4e",
        "f2fe642e06e75d61c60860f6aaf06ab89b1a5b3fdd3f1e7f5c8c1f2c6fc38e8d",
        "88bcc09b0bf384ce5cfce12d1a8eebe56f8eec716d8f7fa38358573de97c461f",
        # 190/2024-0A.pdf — resumen anual retenciones 2024
        "5bf3d4be88dbb62c4b698ff2e53b56ffb49643a3d7270a1a94b86fb6ca3b6b89",
        # 303/2021-{2T,3T,4T}.pdf — IVA quarterly 2021
        "e3da4439b3b8fff2adb12e8574c06e38e391b2578b9dd90b556a7d1e744c0e42",
        "4fdd9ff5f74be9ac5d6aae8851218769fc1b66829e0223fe4651990312c4a68e",
        "66d1fcd791fe7d7c1d1feceb2fe7e63b82ef1ec79e36bf206d8a1a6cbe75b774",
        # 303/2022-{1T,2T,3T,4T}.pdf — IVA quarterly 2022
        "ade3e98502918bff35d80c3664163f126400be367ca8fb302a3de5fc871cdc1e",
        "0b4bac8036ccea2c39bd36efc072c87a38f9e001f051179589cfa0e4160e133e",
        "f086c1a5a524d731d9daf8ea2fac645808199808adff94a6960113f8f0a6387e",
        "50f09074a6273b934a76f741f6a7fc0a2cdbb11ab7960e1584a63ff32670ccaa",
        # 303/2023-{1T,2T,3T,4T}.pdf — IVA quarterly 2023
        "11b2645064637681791637eb02896d4dfda474ca7755f2d690eb5affbaddec82",
        "25b417fd6925cdca4982884e94a802f393f7e11362cf26ca34f601b213600c96",
        "8283100efa3f70331965cc986f09107445462f0ea9650473c087ecc5f8bc9ca7",
        "7d1a618028d98f78baa804850e5f0963754cf6fdea0ca05255c8bc488934017d",
        # 303/2024-{1T,2T,3T,4T}.pdf — IVA quarterly 2024
        "53e69e77c61cb8aa23bec7c8acb0849fea56cc237c59f1d7ffc5887f53fb7048",
        "a3ff9bf99bb6386a3f565ed39a0e43394c0fa9de617e087a1ee80ea31f3e8906",
        "24d4c76e17ce3a940b895ad536263fc748c472b390dfa583f0c2b7af8b87ccbc",
        "6b7b5d4b2f3f3a33d1a16ea88fb70dfa0c1763f8378c2a7ad819c1fb4e4a81fe",
        # 390/{2021,2022,2023}-0A.pdf — IVA anual
        "08351411dbd84e5c1aad616a591d631235720d7071b7a75a954e718e02aa55e5",
        "90289d14d5292a95b71f98f9c1a8b1794072a3460b7b289527abe287abcf21bc",
        "0ddec4d94235931aca58dcb959cf400f4b3e2595beb6d98ecb43bd9cb8a92ec4",
    },
)
