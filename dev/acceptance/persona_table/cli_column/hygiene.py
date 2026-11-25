"""Keep the secrets of a CLI-column run out of every line, log and message it writes.

Two secrets reach this process: the synthetic passphrase of the persona's profile, which travels to a child only on
its standard input, and the publisher's Google OAuth client, which enters the build process's environment alone. A
``Redactor`` knows both, replaces them wherever they would be written, and refuses to let a record out that still
holds one after redaction.
"""

from __future__ import annotations

import contextlib
import json
import os
import stat
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import override

OAUTH_CLIENT_ENV = "CADRUMO_GOOGLE_OAUTH_CLIENT_JSON"
"""The build variable that carries the OAuth client; no child other than the build process may see it."""
REDACTED = "[redacted]"
_CLIENT_KEYS = frozenset({"client_id", "client_secret", "project_id"})
_MINIMUM_SECRET = 6
"""A shorter value is not a secret worth redacting: it would mangle ordinary text."""


class SecretLeakError(RuntimeError):
    """A record still held a secret after redaction; the message never repeats the secret."""


def _client_values(document: object) -> Iterable[str]:
    """The identifying leaves of an OAuth client document: the id, the secret and the project."""
    if isinstance(document, Mapping):
        for key, value in document.items():
            if key in _CLIENT_KEYS and isinstance(value, str):
                yield value
            else:
                yield from _client_values(value)
    elif isinstance(document, list):
        for item in document:
            yield from _client_values(item)


def _forms(secret: str) -> Iterable[str]:
    """The ways a secret can be written: as it is and escaped as JSON text."""
    yield secret
    yield json.dumps(secret)[1:-1]


class Redactor:
    """Replace known secret values in text and in JSON-like records."""

    def __init__(self, secrets: Iterable[str]) -> None:
        """Remember ``secrets``, longest first, so a secret that holds another is replaced whole."""
        values = {form for secret in secrets if len(secret) >= _MINIMUM_SECRET for form in _forms(secret)}
        self._secrets = tuple(sorted(values, key=len, reverse=True))

    @override
    def __repr__(self) -> str:
        """Name how many secrets are held and nothing more."""
        return f"Redactor({len(self._secrets)} secrets)"

    @classmethod
    def for_run(cls, passphrase: str, environ: Mapping[str, str] | None = None) -> Redactor:
        """A redactor of ``passphrase`` and, when ``environ`` holds one, the OAuth client and its identifying leaves."""
        found = [passphrase]
        client = (os.environ if environ is None else environ).get(OAUTH_CLIENT_ENV, "")
        if client:
            found.append(client)
            with contextlib.suppress(ValueError):
                found.extend(_client_values(json.loads(client)))
        return cls(found)

    def with_client(self, client: str) -> Redactor:
        """This redactor and an OAuth client read after it was made, with the client's identifying leaves."""
        found = [client]
        with contextlib.suppress(ValueError):
            found.extend(_client_values(json.loads(client)))
        return Redactor([*self._secrets, *found])

    def text(self, text: str) -> str:
        """``text`` with every secret replaced."""
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text

    def value(self, value: object) -> object:
        """``value`` with every secret replaced in its text, its mapping keys and its sequence items."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, Mapping):
            return {self.text(str(key)): self.value(item) for key, item in value.items()}
        if isinstance(value, list | tuple):
            return [self.value(item) for item in value]
        return value

    def holds_secret(self, data: bytes | str) -> bool:
        """Whether ``data`` still holds a secret, as UTF-8 or UTF-16 text."""
        raw = data.encode("utf-8") if isinstance(data, str) else data
        return any(
            form in raw for secret in self._secrets for form in (secret.encode("utf-8"), secret.encode("utf-16-le"))
        )

    def guard(self, text: str, where: str) -> str:
        """``text`` unchanged, or a :class:`SecretLeakError` naming ``where`` when it still holds a secret."""
        if self.holds_secret(text):
            raise SecretLeakError(f"{where} still holds a secret after redaction")
        return text

    def error_text(self, error: BaseException) -> str:
        """The message of ``error`` with every secret replaced."""
        return self.text(f"{type(error).__name__}: {error}")


def is_link(path: Path) -> bool:
    """Whether ``path`` is a symbolic link, a junction or another reparse point, without following it."""
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _plain_files(directory: Path) -> Iterator[Path]:
    """Every file below ``directory`` that is no link, descending into no linked directory."""
    for place, subdirectories, files in os.walk(directory, followlinks=False):
        subdirectories[:] = [name for name in subdirectories if not is_link(Path(place, name))]
        for name in files:
            path = Path(place, name)
            if not is_link(path):
                yield path


def _remove_if_secret(path: Path, redactor: Redactor) -> str | None:
    """Remove ``path`` when it holds a secret and say so; say too when it could not be read."""
    try:
        held = redactor.holds_secret(path.read_bytes())
    except OSError as error:
        return f"{path.name} could not be read for the secret check: {error.strerror or error}"
    if not held:
        return None
    path.unlink()
    return f"a secret appeared in {path.name}, which was removed"


def remove_secret_bearing(directory: Path, redactor: Redactor) -> list[str]:
    """Remove every plain file below ``directory`` that holds a secret, following no link; name each one."""
    if not directory.is_dir() or is_link(directory):
        return []
    notes = (_remove_if_secret(path, redactor) for path in _plain_files(directory))
    return [note for note in notes if note is not None]
