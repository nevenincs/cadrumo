"""``ledger evidence pull-all`` accepts the folder link an operator actually has.

Drive writes a folder URL as ``/drive/folders/<id>``, while the shared file-id
grammar looks for ``/d/<id>`` or ``?id=``. So the reference a user copies out of
the browser to sweep a folder — the one form this verb exists to take — was
refused as unrecognisable, and the parser had no test of any kind.

Folder-URL knowledge is kept here rather than widened into
``parse_drive_file_id``: a single-document pull should keep refusing a folder
link at the boundary rather than accepting it and failing later against the
media endpoint, where the operator would read a scope error instead of "that is
a folder".
"""

from __future__ import annotations

import pytest
import typer

from ..ledger_lifecycle_cli import _parse_drive_folder_reference

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz012345"


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param(f"https://drive.google.com/drive/folders/{_ID}", id="folder-url"),
        pytest.param(f"https://drive.google.com/drive/folders/{_ID}?usp=sharing", id="shared-folder-url"),
        pytest.param(f"https://drive.google.com/drive/u/0/folders/{_ID}", id="second-account-folder-url"),
        pytest.param(f"https://drive.google.com/drive/folders/{_ID}/", id="trailing-slash"),
    ],
)
def test_every_shape_of_folder_url_resolves(reference: str) -> None:
    """The account segment and the share suffix are both ordinary in a pasted link."""
    assert _parse_drive_folder_reference(reference) == _ID


def test_a_bare_folder_id_still_resolves() -> None:
    """A folder id has a file id's shape, so the shared grammar still carries it."""
    assert _parse_drive_folder_reference(_ID) == _ID


def test_a_file_url_still_resolves() -> None:
    """Unchanged: the fix adds a form rather than replacing the ones that worked."""
    assert _parse_drive_folder_reference(f"https://drive.google.com/file/d/{_ID}/view") == _ID


@pytest.mark.parametrize(
    "reference",
    [
        pytest.param("not a drive reference", id="prose"),
        pytest.param("", id="empty"),
        pytest.param("https://drive.google.com/drive/folders/short", id="too-short-to-be-an-id"),
    ],
)
def test_an_unrecognisable_reference_is_refused(reference: str) -> None:
    """Refused at the boundary rather than sent to the API as an unparsed string.

    The short case matters on its own: a ``/folders/`` segment is not enough to
    make whatever follows it a Drive id.
    """
    with pytest.raises(typer.BadParameter):
        _parse_drive_folder_reference(reference)
