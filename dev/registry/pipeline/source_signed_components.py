"""Exact official M190 sign/magnitude pairs, without a generic signed-field guess."""

from __future__ import annotations

from hashlib import sha256
from typing import Final

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_value_policy import ExportValuePolicy

from .joined_record_design import JoinedRecordDesignField

_SOURCE_PINS: Final[dict[str, tuple[str, str]]] = {
    "2020": ("aeat-dr-190-2020", "4cefd924a7dda3ac5159582f728a72f6f162d3344b8e87f2d17900e6fdcf3b32"),
    "2023": ("aeat-dr-190-2023", "430daf439ed645155ffc6096b65c4da5b26dd2e6c16b8e4781f9be145b3792cb"),
    "2024": ("aeat-dr-190-2024", "20bc8086525ce850063b9ae8644b8514483e5c34f90c8e47cfadc6c52cf7390e"),
    "2025": ("aeat-dr-190-2025", "a7d1092f78620431812354e560a5146a3ae244e0aed69d9d58c353370ba0134d"),
}

# Pair order is dineraria, especie, incapacidad dineraria, incapacidad especie.
# Every digest covers the derived part's full description, content and AEAT type.
# Direct PDF rows in 2024/2025 retain their exact empty content in that digest.
_PAIR_EVIDENCE: Final[dict[str, tuple[tuple[int, int, str, str], ...]]] = {
    "2020": (
        (
            1196,
            1196,
            "89ec584b62fcd036584bb013b19e5a852e491c8ecc8edcea349e9acb6913136f",
            "5ad8fa28eb7351f175c0af8601c64daf27251d04c7ed88ef695dce6cfac6e08d",
        ),
        (
            1261,
            1261,
            "4fbcefca2fe7f02bafd815016bd6abc59abdb0d73cd9bac5d6bf0e470c41a531",
            "61f160a256b3bbb16c58a0e166d232117e8a7911dbd6b052e5354da86bb8b38e",
        ),
        (
            2051,
            2051,
            "3db4d2b2f505c3763d7ee26c04363345a3333cf794a05c2061a3e3f2e283cb0b",
            "80c020e4ae16805c0711bf0341153a7419ab631205ab3015fb8bfddf4bf4407b",
        ),
        (
            2117,
            2117,
            "f34746e10149eac375166a384182409d421cad892696a26577a4ada21b5261a7",
            "30fc3f3984ebcc7f471c8cfb43546a34ba26fde09dbc837afd5dd920312ce3da",
        ),
    ),
    "2023": (
        (
            1410,
            1410,
            "89ec584b62fcd036584bb013b19e5a852e491c8ecc8edcea349e9acb6913136f",
            "5ad8fa28eb7351f175c0af8601c64daf27251d04c7ed88ef695dce6cfac6e08d",
        ),
        (
            1475,
            1475,
            "4fbcefca2fe7f02bafd815016bd6abc59abdb0d73cd9bac5d6bf0e470c41a531",
            "eb84f1657205ccda79b10bcf8ef138f154fb45f2516def5a3397a93f6146ef85",
        ),
        (
            2335,
            2335,
            "3db4d2b2f505c3763d7ee26c04363345a3333cf794a05c2061a3e3f2e283cb0b",
            "078c45e4f0e7d5d8189d367a3c2878e21dec3210e6c44d01fb3bf108f7085a14",
        ),
        (
            2408,
            2408,
            "f81d825247b5adab1a0c20e5d87133d461cba311a2373a4be0de714c5d9de7d1",
            "7a535f5981b9f3fecd03e6706f5dd66f9c5a8e908548ac549a569c82af09d536",
        ),
    ),
    "2024": (
        (
            1426,
            1436,
            "10d5bc9c37dc0f2a5c7b50e17dc1d48cdc13b1265b1ad0f967ea42540af10e0f",
            "478edf0ec3bacd3c7a9e2067c8c9e5268974af281fa25df276df2f9033d2443a",
        ),
        (
            1492,
            1503,
            "e4d33f6985aed9ebfc9f9282e54254d294863ede5814732b07671159c7594b17",
            "9c1642f7328d4ff2e588144e2b673f39080a404e64064ade245e0eb8a37193dc",
        ),
        (
            2371,
            2371,
            "3db4d2b2f505c3763d7ee26c04363345a3333cf794a05c2061a3e3f2e283cb0b",
            "e9215ed7298df6de4438dcd76d4a1461299b2051d88912bc5c8e4bd759093a38",
        ),
        (
            2438,
            2438,
            "1e67c506b4969a9a22896af94f33f31ea83d89d0d1b22edf9f0a609c8dcd1e3f",
            "30fc3f3984ebcc7f471c8cfb43546a34ba26fde09dbc837afd5dd920312ce3da",
        ),
    ),
    "2025": (
        (
            1479,
            1489,
            "10d5bc9c37dc0f2a5c7b50e17dc1d48cdc13b1265b1ad0f967ea42540af10e0f",
            "478edf0ec3bacd3c7a9e2067c8c9e5268974af281fa25df276df2f9033d2443a",
        ),
        (
            1545,
            1556,
            "e4d33f6985aed9ebfc9f9282e54254d294863ede5814732b07671159c7594b17",
            "9c1642f7328d4ff2e588144e2b673f39080a404e64064ade245e0eb8a37193dc",
        ),
        (
            2428,
            2428,
            "3db4d2b2f505c3763d7ee26c04363345a3333cf794a05c2061a3e3f2e283cb0b",
            "c2b27086f3e5af199bea6f4794264f291ea748e4ad95fc570eca26e9624b893d",
        ),
        (
            2495,
            2495,
            "f81d825247b5adab1a0c20e5d87133d461cba311a2373a4be0de714c5d9de7d1",
            "e85b6ac2f12357435733ab39c244d5e8e360f0713241b4a20f2510f74f341566",
        ),
    ),
}

_PAIRS: Final[tuple[tuple[str, str, str, int], ...]] = (
    (
        "modelo-190-perc-signo-percepcion-dineraria",
        "modelo-190-perc-percepcion-dineraria",
        "modelo-190-perceptor-row-percibido-dinerario",
        81,
    ),
    (
        "modelo-190-perc-signo-percepcion-especie",
        "modelo-190-perc-percepcion-especie",
        "modelo-190-perceptor-row-percibido-especie",
        108,
    ),
    (
        "modelo-190-perc-signo-incapacidad-dineraria",
        "modelo-190-perc-incapacidad-dineraria-percepcion",
        "modelo-190-perceptor-row-incapacidad-dineraria-percepcion",
        255,
    ),
    (
        "modelo-190-perc-signo-incapacidad-especie",
        "modelo-190-perc-incapacidad-especie-valoracion",
        "modelo-190-perceptor-row-incapacidad-especie-valoracion",
        282,
    ),
)


def signed_component_policy_for(
    joined_field: JoinedRecordDesignField, *, modelo: str, source_ref: str, source_sha256: str, epoch: str
) -> ExportValuePolicy | None:
    """Return a wire part only when every source, part and provider fact still matches."""
    field = joined_field.parser_field
    entry = joined_field.semantic_entry
    field_id = str(entry.export_field_id)
    pair_index = _signed_pair_index(field_id)
    if pair_index is None:
        return None
    _require_signed_component_source(modelo, source_ref, source_sha256, epoch)
    sign_id, _, binding, sign_offset = _PAIRS[pair_index]
    sign_row, magnitude_row, sign_digest, magnitude_digest = _PAIR_EVIDENCE[epoch][pair_index]
    is_sign = field_id == sign_id
    expected_row, expected_offset, expected_length, expected_digest = _signed_component_expectations(
        is_sign, sign_row, magnitude_row, sign_offset, sign_digest, magnitude_digest
    )
    material = "\x1f".join((field.normalized_description, field.content or "", field.aeat_type))
    if not _matches_reviewed_signed_component(
        joined_field, binding, expected_row, expected_offset, expected_length, expected_digest, material
    ):
        raise RegistryValidationError("modelo 190 signed component source, geometry or provider no longer matches")
    return ExportValuePolicy.SIGNED_COMPONENT_SIGN if is_sign else ExportValuePolicy.SIGNED_COMPONENT_MAGNITUDE


def _signed_pair_index(field_id: str) -> int | None:
    return next((index for index, pair in enumerate(_PAIRS) if field_id in pair[:2]), None)


def _require_signed_component_source(modelo: str, source_ref: str, source_sha256: str, epoch: str) -> None:
    pin = _SOURCE_PINS.get(epoch)
    if modelo != "190" or pin != (source_ref, source_sha256):
        raise RegistryValidationError("modelo 190 signed component source identity is unreviewed or stale")


def _signed_component_expectations(
    is_sign: bool,
    sign_row: int,
    magnitude_row: int,
    sign_offset: int,
    sign_digest: str,
    magnitude_digest: str,
) -> tuple[int, int, int, str]:
    expected_row = sign_row if is_sign else magnitude_row
    expected_offset = sign_offset if is_sign else sign_offset + 1
    expected_length = 1 if is_sign else 13
    expected_digest = sign_digest if is_sign else magnitude_digest
    return expected_row, expected_offset, expected_length, expected_digest


def _matches_reviewed_signed_component(
    joined_field: JoinedRecordDesignField,
    binding: str,
    expected_row: int,
    expected_offset: int,
    expected_length: int,
    expected_digest: str,
    material: str,
) -> bool:
    field = joined_field.parser_field
    entry = joined_field.semantic_entry
    return (
        field.sheet == "Tipo 2 - Registro De Perceptor"
        and field.record_identity == field.sheet
        and field.source_row == expected_row
        and field.offset == expected_offset
        and field.length == expected_length
        and sha256(material.encode()).hexdigest() == expected_digest
        and entry.kind is CasillaFieldKind.BINDING
        and str(entry.binding) == binding
    )
