"""Tolerant reading of the vendor installer's output for progress and failure cause."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ..installer_output import InstallerProgressParser, classify_installer_output

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_MIB = 1024 * 1024
_BAR = "|" + "■" * 16 + " " * 64 + "|  20% of 10 MiB"


def test_progress_without_an_exact_size_uses_the_printed_mebibytes() -> None:
    parser = InstallerProgressParser()

    assert parser.feed("Downloading X 1 (playwright chromium v1248) from https://h/a.zip") is None
    assert parser.feed(_BAR) == 2 * _MIB
    assert parser.feed(_BAR) is None
    assert parser.feed("X 1 (playwright chromium v1248) downloaded to /pw/chromium-1248") == 10 * _MIB


def test_the_installers_own_retry_restarts_the_archive_without_double_counting() -> None:
    parser = InstallerProgressParser()
    parser.feed("Downloading X (playwright chromium v1248) from https://h/a.zip")
    parser.feed("pw:install -- total bytes: 1000 +1ms")
    assert parser.feed("|xxxx|  50% of 0 MiB") == 500
    parser.feed("Downloading X (playwright chromium v1248) from https://h/b.zip")
    parser.feed("pw:install -- total bytes: 1000 +1ms")

    assert parser.feed("|xxxx|  10% of 0 MiB") == 100


@pytest.mark.parametrize("line", ("", "random text", "|| abc% of MiB", "Downloading nothing in particular"))
def test_unrecognised_lines_change_nothing(line: str) -> None:
    assert InstallerProgressParser().feed(line) is None


@pytest.mark.parametrize(
    ("lines", "expected"),
    (
        (["Error: EACCES: permission denied, mkdir '/pw'"], (DependencyFailureCategory.NO_PERMISSION, False)),
        (["server returned code 429 body ''"], (DependencyFailureCategory.HOST_UNREACHABLE, True)),
        (["server returned code 404 body ''"], (DependencyFailureCategory.UNEXPECTED, False)),
        (["Error: read ECONNRESET"], (DependencyFailureCategory.HOST_UNREACHABLE, True)),
        (
            ["Error: self-signed certificate in certificate chain"],
            (DependencyFailureCategory.SECURE_CONNECTION_FAILED, False),
        ),
        (["Failed to download, caused by Download failure, code=1"], (None, False)),
    ),
)
def test_failure_causes_map_to_closed_categories(
    lines: list[str], expected: tuple[DependencyFailureCategory | None, bool]
) -> None:
    assert classify_installer_output(lines) == expected
