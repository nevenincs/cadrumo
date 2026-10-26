"""Require an explicit, storage-controlled Homebrew installation target."""

from pathlib import Path

from cadrumo.core.storage_environment import storage_directory


def require_homebrew_installation_prefix(actual_prefix: str) -> Path:
    """Refuse host-prefix fallback before package installation or cleanup."""
    value = actual_prefix.strip()
    candidate = Path(value)
    if not value or not candidate.is_absolute():
        raise SystemExit("brew --prefix must return one absolute installation directory")
    actual = candidate.resolve(strict=True)
    expected = storage_directory("CADRUMO_HOMEBREW_PREFIX", "development/packages/homebrew")
    if actual != expected:
        raise SystemExit(
            "Homebrew installation prefix differs from controlled storage; "
            "select the intended installation with CADRUMO_HOMEBREW_PREFIX "
            f"and a matching --brew executable (configured={expected}, actual={actual})",
        )
    return actual
