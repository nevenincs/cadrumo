"""Wire bytes captured from the supervised-KDF path before its import graph was cut.

Produced by the pre-change encryption primitive, frame codec and KDF worker,
with synthetic key material only. The compatibility tests replay them through
the current implementation, which must read every value unchanged.
"""

from __future__ import annotations

from typing import Final, TypedDict


class AeadSample(TypedDict):
    associated_data_b64: str
    key_b64: str
    plaintext_b64: str
    wire_b64: str


class KdfParameters(TypedDict):
    algorithm: str
    iterations: int
    memory_mib: int
    output_bytes: int
    parallelism: int
    salt_b64: str
    version: int


class WrappedDek(TypedDict):
    ciphertext_b64: str
    nonce_b64: str
    tag_b64: str


class KdfWireBaseline(TypedDict):
    aead: list[AeadSample]
    associated_data_b64: str
    dek_b64: str
    fallback_kdf: KdfParameters
    fallback_wrapped_dek: WrappedDek
    frames: dict[str, str]
    kdf: KdfParameters
    password: str
    recovery_secret: str
    wrapped_dek: dict[str, WrappedDek]


KDF_WIRE_BASELINE: Final[KdfWireBaseline] = {
    "aead": [
        {
            "associated_data_b64": "Y2FkcnVtby13aXJlLWZpeHR1cmUtYWQ=",
            "key_b64": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
            "plaintext_b64": "",
            "wire_b64": "qdDqYndAGoezYnWOWC+juDFRBW8D5jlcV25ixA==",
        },
        {
            "associated_data_b64": "Y2FkcnVtby13aXJlLWZpeHR1cmUtYWQ=",
            "key_b64": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
            "plaintext_b64": "eA==",
            "wire_b64": "duzGkLEv1pZ+Ih74XdWTKOrv0row5I7pmGA4EYA=",
        },
        {
            "associated_data_b64": "Y2FkcnVtby13aXJlLWZpeHR1cmUtYWQ=",
            "key_b64": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8=",
            "plaintext_b64": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8gISIjJCUmJygpKissLS4vMDEyMzQ1Njc4OTo7PD0+P0BBQkNERUZHSElKS0xNTk9QUVJTVFVWV1hZWltcXV5fYGFiYw==",
            "wire_b64": "hFWGgbq255ygv5352nZCnbEm/IDA9Hzv23+1Puca70t8r/diOtS6xGkQatiQTloDEJZeI61sKCPhQ34ujXaIzmWiJLKtgsWhIRMLe35oDG/3CjvA9pnQpF1xgGGXurRkJZsi9UAkVnW76p3EIUl6keuMvmlibmYEkR0oHvSSqwk=",
        },
    ],
    "associated_data_b64": "Y2FkcnVtby13aXJlLWZpeHR1cmUtYWQ=",
    "dek_b64": "ZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXp7fH1+f4CBgoM=",
    # A password wrap at the fixed fallback point, written by the worker that
    # every enrollment fell back to before calibration could confirm a measured
    # point; profiles wrapped this way must keep opening.
    "fallback_kdf": {
        "algorithm": "argon2id",
        "iterations": 3,
        "memory_mib": 64,
        "output_bytes": 32,
        "parallelism": 1,
        "salt_b64": "AAECAwQFBgcICQoLDA0ODw==",
        "version": 19,
    },
    "fallback_wrapped_dek": {
        "ciphertext_b64": "1qHYdfBMuwGH3/TBx2wuTNlbiWkZWWtU6yxCE1bFtGk=",
        "nonce_b64": "FXgwVrK30F5/NJR0",
        "tag_b64": "JnUxLH/qJ/WTweUk1AsYQw==",
    },
    "frames": {
        "KDF_FAILED_FRAME": "Q0tERgEBAAAAAAAdY2FkcnVtby1wcm9maWxlLWtkZi1mYWlsZWQtdjE=",
    },
    "kdf": {
        "algorithm": "argon2id",
        "iterations": 2,
        "memory_mib": 19,
        "output_bytes": 32,
        "parallelism": 1,
        "salt_b64": "AAECAwQFBgcICQoLDA0ODw==",
        "version": 19,
    },
    "password": "correct horse battery staple wire fixture",
    "recovery_secret": "ABCDE-FGHJK-LMNPQ-RSTUV-WXYZ2-34567",
    "wrapped_dek": {
        "password": {
            "ciphertext_b64": "2BN7R2qmBjL9xomOWz9E7MgYhoJiMw6GSVXtz3jhWHg=",
            "nonce_b64": "k6Qj9o15luhCs5o/",
            "tag_b64": "fDW/soFapbOe+IQ5n8GZYg==",
        },
        "recovery": {
            "ciphertext_b64": "+LEgdcwPCS8bPXRoic/hmUdYpHDASx0KOF743PiO19w=",
            "nonce_b64": "2Xap1sYAoth18rJC",
            "tag_b64": "3YZilwNpuEh+iYauQ2yjFg==",
        },
    },
}
