"""Session codec declarations from the pinned SecretStorage 3.5.0 source."""

DH_PRIME_1024: int

class Session:
    object_path: str | None
    aes_key: bytes | None
    encrypted: bool
    my_private_key: int
    my_public_key: int

    def __init__(self) -> None: ...
    def set_server_public_key(self, server_public_key: int) -> None: ...
