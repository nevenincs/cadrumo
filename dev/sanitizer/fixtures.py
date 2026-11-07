"""Known-sanitised fixture SHAs for refuse-if-already-sanitised guard.

When :func:`sanitize_pdf` is called with bytes whose SHA-256 lives
in :data:`SANITIZED_SHAS`, the sanitiser refuses with
:class:`AlreadySanitizedError`. The set is populated with every
fixture committed under ``src/cadrumo/tests/fixtures/justificantes/`` so an
operator who points the sanitiser at a previously-sanitised fixture
gets a hard error rather than a silent no-op or double-stripped
output.

The set contains only SHA-256 digests of already-sanitised fixture bytes. It
does not store cleartext source hashes or token-map contents.

Callers can opt out per-call with
``sanitize_pdf(..., refuse_if_already_sanitized=False)`` for the
narrow case where intentionally re-sanitising a fixture is the
correct action (e.g. when extending the TokenMap to cover a new
PII surface against an existing capture).
"""

from __future__ import annotations

# Lowercase hex SHA-256 of every committed PDF under
# ``src/cadrumo/tests/fixtures/justificantes/``.
#
# DO NOT hand-edit. Regenerated from the committed tree and pinned by
# ``tests/test_sanitized_sha_catalogue.py``, which fails on drift. Hand
# maintenance is what broke it: 32 of 41 entries matched no committed fixture
# and 53 of 62 fixtures were absent, so the refuse-if-already-sanitised guard
# covered nine fixtures while reading as though it covered all of them. A
# regenerated fixture changes its SHA and nothing made the list follow.
SANITIZED_SHAS: frozenset[str] = frozenset(
    {
        # 036: 2025-0A.pdf, 2025-alta.pdf
        "70078c8b9a3fa23c0624141aa0f3630edc556a50e25a5a1452540d1b77c2c274",
        # 100: 2021-0A.pdf, 2022-0A.pdf, 2023-0A.pdf, 2024-0A.pdf, 2025-0A.pdf
        "920a0493fc11dd432450876cb42ab5db920365d6f387887dc5de4db193e97c25",
        "9f804cb1b34487a84a76287e3c3a365d53edcc282f629c280c866df07cfc5b7a",
        "370483f75e0f006b9d441db2b3ddc56c7548445c5b1dabe568b182d1f0903a58",
        "e91f39a18e243bbda34e7633eaadf01b728da2ed147cddb80ed485d910e19acb",
        "6ddf90251a02f40728e6bd46fe109459a7aa4f2810abc1dad8e3d1086901e517",
        # 111: 2024-1T.pdf, 2024-2T.pdf, 2024-3T.pdf, 2024-4T.pdf
        "d174fcf5e4b1821cf1ad6fc035178a0d6e353413b5ab9946d0f96269a6fb2890",
        "0f200c09f77fccd588b9e84fe34958ce7eeb2c199337a17a3b15993461ee8d68",
        "316b726aa5d327887dcda041bb61f6132aad29e5a9a529541e8764b11cf409d8",
        "189871cbe1249786414b36877df2fc74eac9f27fa5703dfedf07a898018c613f",
        # 115: 2024-1T.pdf
        "ec18e0dca849e44f1eba9f7b1591ed576db341768328484c33add01cec7a6d10",
        # 123: 2023-1T.pdf, 2024-1T.pdf
        "c98a4b4df51f8ec44c4d575e11bc2fbe73ca34423a1bedd3d9a69763b49d3e70",
        "59b005865e74822da5859af68a9a81b11ad069bfdc637101c435af2bb051937c",
        # 130: 2021-2T.pdf, 2021-3T.pdf, 2021-4T.pdf, 2022-1T.pdf, 2022-2T.pdf, 2022-3T.pdf, 2022-4T.pdf, 2023-1T.pdf,
        # 2023-2T.pdf, 2023-3T.pdf, 2023-4T.pdf, 2024-1T.pdf, 2024-2T.pdf, 2024-3T.pdf, 2024-4T.pdf
        "77bb527dfb8b20c558880e36dd0bf25e97007c61c88dc8eabb1214c6d486f549",
        "f2ad289a7c1baf3951650402143b7bf2b05f07903fdf3f837f638117fe36f245",
        "bde596932e4bd2eedd5bc22938dc0024fd44d1e963c321710b6f0b467a31df89",
        "048c0a1f78623fe482ff48d44fa0a0404f77963253d39345cf463ceb5f9e0d37",
        "bd7d7d72200ec295b41748ad65deb3ca4c9766338130140c98fda8003c4c1654",
        "292c15892bfdc2f39226d46ad5434a778eeec1f057c6e9397c464e0ab480123c",
        "a942a6435e1d2f51257e7ff5733d6e7c0b290f4595177d1f2f8ea9dc688214a7",
        "212f2e2b89f099208b910fd275e5ccec1941c5503ea5617b93ec32f1fa6f16ee",
        "32167e3bd2ce3f0852759ba9ef856e1ad39d203b23f96d370f99e1c40f29bdef",
        "597eb0666e962cf08bd5dc772b612343bc854fa3a20b7388be67eb3023e203c6",
        "de371a66375639ecac077cc926e8d6a1bde1e4f2e55a0b33fb539666a8ff26b4",
        "f8f23e148f8d0a8d4e535abc4918e95679e9cc86ad314c0ad5d6cf06692df3c0",
        "40c76c0dc913cd01c6db2be12418862e89bfda910e58eecccd82f2bb1fdef00d",
        "065a5e1f1c9b722e3b8b96475eddd15765c991122a7c3e2922931b0554c2e975",
        "3bc063c6ebd488b8a2e90632cb9f57ca7cf13754a445e49870e3851ae264bbb9",
        # 131: 2024-1T.pdf
        "7f50c55ec4641a425b81d8196dcc8eec7c9003f396168b0696834af896751555",
        # 180: 2024-0A.pdf
        "73d0352a066bd931f5cea3ccacbd1f68108d127fa0e26f92e690b965118d4782",
        # 184: 2024-0A.pdf
        "31def2b6b4d9272eb06e39b271eb73fdecc8f4c55ba1722623746630547cf3d2",
        # 190: 2024-0A.pdf
        "0d345e9d06e976907c3c9795fa6955dbf24bf50cf354dc7481c91b0248cd9d56",
        # 193: 2024-0A.pdf
        "2d72fa1228ea31c368e85bdc3fd2daab3365a64f29f3b43ba0eec9ddd9f6b48a",
        # 202: 2025-1P.pdf
        "96d5ff30804cc970a8dde1a6fdc262c447381a107205e85928dc488ce3eba93a",
        # 232: 2016-0A.pdf, 2018-0A.pdf
        "971bfe8e60652b806b77ebb4ee1e295b54674fcdb2e6328f6287fd5a6aa2ee9f",
        "b3c47e2e3d28a2afc66151287332ae8982314b77a66bdf7998734cf747f3df44",
        # 303: 2021-2T.pdf, 2021-3T.pdf, 2021-4T.pdf, 2022-1T.pdf, 2022-2T.pdf, 2022-3T.pdf, 2022-4T.pdf, 2023-1T.pdf,
        # 2023-2T.pdf, 2023-3T.pdf, 2023-4T.pdf, 2024-1T.pdf, 2024-2T.pdf, 2024-3T.pdf, 2024-4T.pdf
        "0726d193f2aa2062978bd9c83f8ccead025557b0fa582f1383436ae134471b3b",
        "2426d3159e8b28a9783da7d2e37e9bc426d09e21eae8e7a4a99865aea378c4e5",
        "9d779e39579638613528574947723f0bff70c3ecbe470a25a726c938de4abce7",
        "1c0a9ce44b19e7a5877c75e6e56a7fde3cf5d066632685b612243e4774d8b6d2",
        "e1f79c9c6f1bed32da3f06fbeee3afb435635bfc49442589207afa4b3204cdd3",
        "6c51af3a06be2234f8411abad335d72b5c4103b1e353efa3fd40584582dbb15e",
        "421aa1748c5110c57e397099e4a2daa23900ce4c878a21e8cb6f39bcace3796f",
        "97a4890d0f1ba0ce4ce299d93a46efdc4fc09426ad9afd5bd335e6620afae77b",
        "fbf3a299447709b346d7f9d8facc3213dfca913f57860201c134d1a17873bb74",
        "5e72830917fdb22ba73d3f46a1fc3077ac68366be7487949a270c0b2a37e41bf",
        "cdccb837c8264e6836f125dfd1526ae6ebfede5d4500eab172d9eba2e1a68015",
        "a5102b5a89e77dc3f45056312e6466e80439761e41433d8f4f41593d09121943",
        "9237f14175f3ac62e9cd2e61d06d92cb5fc12788ba462fe3e95192d060d31e6a",
        "abda67af29fbe75d827133f97abf42a5bbda90d16fff742eb0cd7d55e34c27d8",
        "f417e6498f7e0b8459c0575b0ebd07476d012c3ad925348dc9f0d4f500c70622",
        # 347: 2024-0A.pdf
        "d16f0dfaed25ca04791dd0a1606475deeef486b7781d9c8f0a21fe8232d70796",
        # 349: 2024-1T.pdf
        "26964c015b25ed0b33ae85b98d780861ef5f9e79fb4234d8bd1399c54577e3e3",
        # 369: 2024-1T.pdf
        "eb9cb7f50f8ed910bbb6405831735f0b7ef35bc3478e2640be955c5bc593276d",
        # 390: 2021-0A.pdf, 2022-0A.pdf, 2023-0A.pdf
        "2870b55b725e5d18feb33da21b38d57bbdb68de77f2510fab780ed4fb0bdd6f6",
        "b73ac3b71c3697847247c5ab840f3ff9d1ccad2cd7e4ea8531de6a2c43df03af",
        "5e6b70d907c0c2fe738c7fcdc4b6c3027360d9b9f848f325c03c485c49947523",
        # 720: 2024-0A.pdf
        "abb908698efabfd1c7d036db318f1f60ef78b34f3a329aad1142fae9af6727d8",
        # 840: 2024-0A.pdf
        "36f8bf8b5d772e9c3b4534599a1230cd5294a868d3759a67ab20a481244591a2",
        # top-level: modelo_100_2025A.pdf, modelo_111_2026Q1.pdf, modelo_130_2026Q1.pdf,
        # modelo_303_2026Q1.pdf
        "b08fdfc5f4413fe0154534709ef3ebfe9ce2da6347e7b151a9909b2d2c924635",
        "2e6621c9706c0dc4ca9c177f327a01a6a7808565531ccf497b39ac86e28bda9c",
        "4d3a3045c77e0e1b446a1c1d95dd530582c8bb78cc60033a238dc024ab494e1e",
        "a128a5074a196d4284b6078eb55af577cad2484e4fdd02ea2974ee063e215f03",
    },
)
