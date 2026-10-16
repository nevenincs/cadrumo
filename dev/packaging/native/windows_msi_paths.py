"""Literal and extended-path projection shared by every WiX source owner."""

from pathlib import PurePath, PureWindowsPath


def literal(value: str) -> str:
    """Keep authored metadata outside WiX's preprocessor expression language."""
    # WiX preprocessing must never interpret metadata or source paths as expressions.
    if "$" in value:
        raise ValueError("MSI authoring cannot admit WiX preprocessor expressions in literal inputs")
    return value


def source_path(path: PurePath) -> str:
    """Use native extended paths at the cabinet reader, without changing MSI destinations."""
    value = str(path).replace("/", "\\")
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    if value.startswith(("\\\\.\\", "\\??\\")):
        raise ValueError("MSI source must identify a filesystem path, not a device namespace")
    native = PureWindowsPath(value)
    if native.is_absolute():
        if ".." in native.parts:
            raise ValueError("MSI source must use an absolute normalized path")
        value = str(native)
        return literal("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)
    # Portable authoring tests can inspect WiX metadata from POSIX fixture roots.
    if path.is_absolute() and not isinstance(path, PureWindowsPath):
        return literal(path.as_posix())
    raise ValueError("MSI source must use an absolute filesystem path")
