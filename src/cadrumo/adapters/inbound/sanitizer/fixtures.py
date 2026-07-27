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
        "b9ee9a65069344a09d456dbd820e335b24cbba771988f3dd84b8d1546f4c83bd",
        # (byte-identical to an entry above: 2025-alta.pdf)
        # 100: 2021-0A.pdf, 2022-0A.pdf, 2023-0A.pdf, 2024-0A.pdf, 2025-0A.pdf
        "a983084723897ec5fa75078d62d10f8bf7ec0a47148d90dae7d1a05eb77ab6ab",
        "ce4a9e39f04237a8a752cd6e6596db1bbec364ba2893c3a2f3e44e8543587066",
        "996fb37e2b98ce0e8d359e4df2f61fc913a337bcb0a620cc6183b81deb32d66f",
        "a40ecc2b700c41353092ffd7f84fa843bc3e9a1e2a4ac2baf3ddecb1259c06f9",
        "837f9fa8a4f6cc9befd594e1006728b53159ebf5ee3f27582ece7dae38fc3e9a",
        # 111: 2024-1T.pdf, 2024-2T.pdf, 2024-3T.pdf, 2024-4T.pdf
        "00a083d5b131ba0964c4c57b069880e884c249d984bb67793253f0b050fbe88f",
        "8289b74ca3bba03db1c9e676f918e4cd29b614db738a81ab94600efc73d78a42",
        "3b8a833c3185933f1b546be4976363baab411fba3c1da7986ea9a1a43ffcc2c1",
        "d9287f5bd606981ae440ffa1fe7a2cdce834d21662d692af42b5bbb0f442754a",
        # 115: 2024-1T.pdf
        "6dd56c9af75422126fa9eebdd838114144230dd7cac877a5cdd14e3304c2b56e",
        # 123: 2023-1T.pdf, 2024-1T.pdf
        "d673ee28a00fb17c5d89812da90fa288014cdd1ae8f1c3613965ad8bc89397b0",
        "0cd78b29226c2bdafa42de43c6befc2150f0099958d72c26a9f503b9f95750c3",
        # 130: 2021-2T.pdf, 2021-3T.pdf, 2021-4T.pdf, 2022-1T.pdf, 2022-2T.pdf, 2022-3T.pdf, 2022-4T.pdf, 2023-1T.pdf,
        # 2023-2T.pdf, 2023-3T.pdf, 2023-4T.pdf, 2024-1T.pdf, 2024-2T.pdf, 2024-3T.pdf, 2024-4T.pdf
        "4e933965cfb9b9da402c893a35394bd05e6fced2d357ec05da84503021b7b6b2",
        "31dc911283752fe1b395177103293a1582236eadac792076d7caddb0528d2b25",
        "b7814f22ec13eff692eb0e977cf163fa75df800e4847a6a04584df48b2da1b58",
        "036f5bebeee35d805240e71c66330434e0490876a2c1636c3aee7b3e70cd000f",
        "3942dbe79e4901caec4825f1d3fec2d79c29834f30d0e8509f5f0b06b8955397",
        "7e5245143d70e4afc4eb31751ff2b95212c45fbb6b51834dce35207edc35af89",
        "9f103cc191ba8ef0b0143d2faaca5eba03bc3aa6581d0574b7b46ca56367059a",
        "75c57f90e7a2f65966aa244deb87e42870abb6167c0ed8fa0359f89e485d844c",
        "600447201728923fd64c1f21ea3c22be04ada4d7a618a941ca6610c1978b61b1",
        "c2792c34690901f1f797167311a7f8c53079465d65573681d0c18a21eaf5a30e",
        "d40a6ac7456d910e2ad130fb6646473cce8afd64e3213dd6d1d561a8f22acada",
        "6017498d590354d710bb07da11f1200c7ad5e44f054067c0e502ffba850df437",
        "9d9e3c79a387f38cb7993439b5e74f2acdfb61525b6dce926bb6e141c0b5d48c",
        "4488ec660b657b09f3a6817f097317b266d4aee526d145833ec43988f4d16891",
        "c207ac193196df125c03b3c3573efdfb07b785b1cad8630032dda0f0ce1f4dc2",
        # 131: 2024-1T.pdf
        "7970d4c257a8329e0eafd946bd4bb4e9e980b8bd99eba493bad5c436af21c866",
        # 180: 2024-0A.pdf
        "13af0b50b94d9d805807860d4ea166667d9d33dbada33f216a5f1c272990f059",
        # 184: 2024-0A.pdf
        "7c67044b4609fc6911002d09f05863179f15bf527c36339da8468ffc637ef8cd",
        # 190: 2024-0A.pdf
        "0c3fe8d99600feeda72962e3bfadecae255d21580416ae623a5ed57817350296",
        # 193: 2024-0A.pdf
        "a3483a59f47a9b70c717dcdd99c7ecce9f6febf8afefb54758f7c11d8f9d60f7",
        # 202: 2025-1P.pdf
        "17f8dc56f54e670ff3cc0d29daa1feebe1d05a6b1c91fac58e15624fb75bf745",
        # 232: 2016-0A.pdf, 2018-0A.pdf
        "70e972741f559c87c254e7fcbd406366adcec72e65d1fd16becf08912f6aa4b0",
        "f751ed778d98fbaf21e2b0c40fdbd24a0543476cb5fa0efdf6bf65a43602f1ad",
        # 303: 2021-2T.pdf, 2021-3T.pdf, 2021-4T.pdf, 2022-1T.pdf, 2022-2T.pdf, 2022-3T.pdf, 2022-4T.pdf, 2023-1T.pdf,
        # 2023-2T.pdf, 2023-3T.pdf, 2023-4T.pdf, 2024-1T.pdf, 2024-2T.pdf, 2024-3T.pdf, 2024-4T.pdf
        "bd2f1d0b0a0f0462fe3ee016d43012c41ef68a93d6905b1326dba0fae81c2574",
        "eb0e4cfffbb6250f91a34ed3465c0090185c0d5265d8167f82b561910f1a4df6",
        "ac47144dc01e5c66d193ebedba88b2ff3122036ccc06a2ae6c421a04a0c4112b",
        "6fa9ae025da54a0560719059df3a4302499a345686f54e219a00f87ea8ff8666",
        "beebfce3ad50128445181d9ad9bc7c7198a5855999985207efbf95577906a49f",
        "1fe0a24a2b3703cdb53b99c05cf8cb6eb8283373238ce8fc8c38a15791c37468",
        "6907c7a3fa93ae4e45a85e94a5685ab11cfef06fd390a45263299f6f282bf172",
        "20f3443d3928456dd4de547e0855520136561e9f3797dc2e4b1c27f324a90f18",
        "e31f975fe40467cb53ff532462dec8c83e6a9c779bd72aebe01de6070ca16eb9",
        "0642a40a5c5b41c84e15be9cd6ef6d6ffdf1f5eae82a68d940d88a007a6bdccf",
        "2704e1071a9af5065d7215629dc22b3c692a71191568b5645a17239fbc6883d4",
        "87f08c73c210d47f76786cb6435194021bd8890b36cf603b81180f71c4e00a3b",
        "9523ebb8611311640d9783a65948e34c9e1c2775dc1015d78d2bac8a713d1b84",
        "3848389ab546f62b47733cdb9a6a95db887968280f2b0d75dc5f6cdc31408c71",
        "adafe65bb8253d0d2a40c7a0cbce22862371feb20d2634cb89d7c5207c728c60",
        # 347: 2024-0A.pdf
        "40088f3b1ef7333acde39cb6a784920aa0f1b535e2fc0df94e549d652d0a537e",
        # 349: 2024-1T.pdf
        "b7809017399b74bfe015baef4c55697081e0ffcfaf02f4181a60fe9ead2f1b3b",
        # 369: 2024-1T.pdf
        "9d71e92c24830c8b83e9b272b19bf29a6d4f91818dcd5b979e36668996e7cec6",
        # 390: 2021-0A.pdf, 2022-0A.pdf, 2023-0A.pdf
        "a070df623c2bcb61f7a1c521b4e5e93de389b09c3283e20eea024c45ad09ad63",
        "794d2c7d99653b010389114fbd017f8907ab594a2c6c45ccfda725ba245dc6a4",
        "8847c831f1ecf2e6096ccfa52aeaa9b95f1814ab0e7e76a491cead4b5c4fa801",
        # 720: 2024-0A.pdf
        "3d4f681c43be5af5c5504bef4b5e5476520aae13ed98e5ae150ea5b709c2f3dc",
        # 840: 2024-0A.pdf
        "4d7c26b58706f6269c01620fe5e875f27fb401a9164fff1dfa986bc76e474349",
        # top-level: modelo_100_2025A.pdf, modelo_130_2026Q1.pdf, modelo_303_2026Q1.pdf
        "2e6621c9706c0dc4ca9c177f327a01a6a7808565531ccf497b39ac86e28bda9c",
        "4d3a3045c77e0e1b446a1c1d95dd530582c8bb78cc60033a238dc024ab494e1e",
        "a128a5074a196d4284b6078eb55af577cad2484e4fdd02ea2974ee063e215f03",
    },
)
