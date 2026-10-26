"""Secret formatting contract from the pinned SecretStorage 3.5.0 source."""

from .dhcrypto import Session

def format_secret(session: Session, secret: bytes, content_type: str) -> tuple[str, bytes, bytes, str]: ...
