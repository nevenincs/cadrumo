"""The review server, driven over a real loopback socket.

Every check goes through the HTTP surface the phone uses, against a real
catalogue and a real notes database in a temporary directory; the only thing
that differs from `serve` is the bind address.
"""

from __future__ import annotations

import io
import ipaddress
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from hashlib import sha256
from http.client import HTTPConnection, HTTPResponse
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from .._review_catalogue import ReviewCatalogue
from .._review_elements import element_digest
from .._review_network import TailnetNode, TailnetUnavailableError, is_wildcard_host, parse_tailnet_status
from .._review_server import ReviewHTTPServer, serve
from .._review_server_contracts import PAGE_PATH
from .._review_state import ReviewState
from .._review_store import ReviewStore
from .._review_thumbnails import THUMBNAIL_WIDTH

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DARK = "home--ready__small__dark"
_LIGHT = "home--ready__small__light"
_ELEMENT = "fixture:home"


@dataclass
class _Review:
    port: int
    runs: Path
    store_path: Path
    state: ReviewState
    digests: dict[str, str]

    def request(
        self,
        method: str,
        path: str,
        body: object = None,
        *,
        content_type: str = "application/json",
    ) -> tuple[int, dict[str, str], bytes]:
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            headers = {}
            payload = None
            if body is not None:
                payload = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
                headers["Content-Type"] = content_type
            connection.request(method, path, body=payload, headers=headers)
            response = connection.getresponse()
            return response.status, {key.lower(): value for key, value in response.getheaders()}, response.read()
        finally:
            connection.close()

    def json(self, method: str, path: str, body: object = None) -> tuple[int, object]:
        status, _, payload = self.request(method, path, body)
        return status, json.loads(payload)

    def state_now(self) -> dict[str, Any]:
        status, state = self.json("GET", "/api/state")
        assert status == 200
        assert isinstance(state, dict)
        return state

    def element_digest(self) -> str:
        """The digest the page is handed for the element, as a reviewer's browser would hold it."""
        digest = next(element["digest"] for element in self.state_now()["elements"] if element["key"] == _ELEMENT)
        assert isinstance(digest, str)
        return digest


def _write_png(path: Path, colour: tuple[int, int, int], size: tuple[int, int] = (1200, 300)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path, format="PNG")
    return sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def review(tmp_path: Path) -> Iterator[_Review]:
    runs = tmp_path / "runs"
    digests = {
        _DARK: _write_png(runs / "current" / "png" / f"{_DARK}.png", (20, 20, 30)),
        _LIGHT: _write_png(runs / "current" / "png" / f"{_LIGHT}.png", (230, 230, 240)),
    }
    (runs / "current" / "text").mkdir(parents=True)
    (runs / "current" / "text" / f"{_DARK}.txt").write_text("╭ Home ╮\n", encoding="utf-8", newline="\n")
    store_path = tmp_path / "review" / "notes.sqlite3"
    state = ReviewState(ReviewCatalogue(runs, settle_seconds=0.0), ReviewStore(store_path))
    state.refresh()
    server = ReviewHTTPServer(("127.0.0.1", 0), state)
    worker = threading.Thread(target=serve, args=(server,), kwargs={"interval": 0.05}, daemon=True)
    worker.start()
    try:
        yield _Review(
            port=server.server_address[1],
            runs=runs,
            store_path=store_path,
            state=state,
            digests=digests,
        )
    finally:
        server.shutdown()
        worker.join(timeout=10)


def test_the_state_lists_every_settled_frame_of_the_default_run(review: _Review) -> None:
    status, state = review.json("GET", "/api/state")

    assert status == 200
    assert isinstance(state, dict)
    assert state["run"] == "current"
    assert [(frame["stem"], frame["digest"]) for frame in state["frames"]] == [
        (_DARK, review.digests[_DARK]),
        (_LIGHT, review.digests[_LIGHT]),
    ]
    assert [frame["text"] for frame in state["frames"]] == [True, False]
    assert [(frame["element"], frame["state"]) for frame in state["frames"]] == [(_ELEMENT, "ready")] * 2
    assert state["notes"] == []


def test_the_state_groups_the_frames_into_the_element_they_show(review: _Review) -> None:
    state = review.state_now()

    assert state["elements"] == [
        {
            "key": _ELEMENT,
            "family": "fixture",
            "name": "home",
            "states": ["ready"],
            "frames": [_DARK, _LIGHT],
            "digest": element_digest(
                {
                    "home--ready/small/dark": review.digests[_DARK],
                    "home--ready/small/light": review.digests[_LIGHT],
                }
            ),
            "modified_at": state["latest_frame_at"],
        }
    ]
    assert state["states"] == [{"family": "fixture", "state": "ready"}]
    assert state["sign_offs"] == {}


def test_a_frame_image_is_served_byte_for_byte_and_cached_only_under_its_digest(review: _Review) -> None:
    on_disk = (review.runs / "current" / "png" / f"{_DARK}.png").read_bytes()

    status, headers, body = review.request("GET", f"/image/current/{_DARK}.png?v={review.digests[_DARK]}")
    assert (status, body) == (200, on_disk)
    assert headers["content-type"] == "image/png"
    assert "immutable" in headers["cache-control"]

    status, headers, _ = review.request("GET", f"/image/current/{_DARK}.png?v={'0' * 64}")
    assert status == 200
    assert headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "path",
    [
        "/image/current/..%2F..%2Freview%2Fnotes.sqlite3.png",
        "/image/current/..%5C..%5Creview%5Cnotes.png",
        "/image/current/home--ready__large__dark.png",
        "/image/elsewhere/home--ready__small__dark.png",
        "/text/current/home--ready__small__light.txt",
        "/nothing-here",
    ],
)
def test_nothing_outside_the_catalogue_is_served(review: _Review, path: str) -> None:
    status, _, _ = review.request("GET", path)

    assert status == 404


def test_a_thumbnail_is_a_narrowed_webp_of_the_frame(review: _Review) -> None:
    status, headers, body = review.request("GET", f"/thumb/current/{_DARK}.webp?v={review.digests[_DARK]}")

    assert status == 200
    assert headers["content-type"] == "image/webp"
    with Image.open(io.BytesIO(body)) as thumbnail:
        assert thumbnail.format == "WEBP"
        assert thumbnail.size == (THUMBNAIL_WIDTH, THUMBNAIL_WIDTH * 300 // 1200)


def test_the_text_reading_and_the_page_are_served_from_disk(review: _Review) -> None:
    status, headers, body = review.request("GET", f"/text/current/{_DARK}.txt")
    assert (status, body.decode("utf-8")) == (200, "╭ Home ╮\n")
    assert headers["content-type"].startswith("text/plain")

    status, headers, body = review.request("GET", "/")
    assert (status, body) == (200, PAGE_PATH.read_bytes())
    assert headers["content-type"].startswith("text/html")


def test_a_note_posted_from_the_page_is_filed_under_the_element_and_outlives_the_server(review: _Review) -> None:
    seen = review.element_digest()
    status, created = review.json(
        "POST",
        "/api/notes",
        {
            "run": "current",
            "element": _ELEMENT,
            "element_sha256": seen,
            "frame": {"stem": _DARK, "png_sha256": review.digests[_DARK]},
            "body": "Title is clipped.",
        },
    )

    assert status == 201
    assert isinstance(created, dict)
    state = review.state_now()
    assert [(note["id"], note["element_state"], note["frame_state"]) for note in state["notes"]] == [
        (created["id"], "current", "current"),
    ]

    stored = ReviewStore(review.store_path).notes()
    assert [
        (note.element_key, note.element_sha256, note.frame_key, note.frame_sha256, note.body) for note in stored
    ] == [
        (_ELEMENT, seen, "home--ready/small/dark", review.digests[_DARK], "Title is clipped."),
    ]


def test_a_note_says_when_the_frame_it_pointed_at_was_re_rendered(review: _Review) -> None:
    status, _ = review.json(
        "POST",
        "/api/notes",
        {
            "run": "current",
            "element": _ELEMENT,
            "element_sha256": review.element_digest(),
            "frame": {"stem": _LIGHT, "png_sha256": review.digests[_LIGHT]},
            "body": "Low contrast.",
        },
    )
    assert status == 201

    _write_png(review.runs / "current" / "png" / f"{_DARK}.png", (90, 20, 30))
    review.state.refresh()
    (note,) = review.state_now()["notes"]

    assert (note["element_state"], note["frame_state"]) == ("changed", "current")

    _write_png(review.runs / "current" / "png" / f"{_LIGHT}.png", (90, 90, 30))
    review.state.refresh()
    (note,) = review.state_now()["notes"]

    assert (note["element_state"], note["frame_state"]) == ("changed", "changed")


def test_a_write_that_is_not_json_is_refused_and_stores_nothing(review: _Review) -> None:
    status, _, _ = review.request(
        "POST",
        "/api/notes",
        b"run=current&element=fixture%3Ahome&body=hi",
        content_type="application/x-www-form-urlencoded",
    )

    assert status == 415
    assert ReviewStore(review.store_path).notes() == ()


_NOTE = {"run": "current", "element": _ELEMENT, "element_sha256": "a" * 64, "body": "x"}


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({**_NOTE, "element": "fixture:ledger-overview"}, 404),
        ({**_NOTE, "run": "elsewhere"}, 404),
        ({**_NOTE, "frame": {"stem": "home--ready__large__dark", "png_sha256": "a" * 64}}, 404),
        ({**_NOTE, "frame": {"stem": "login__small__dark", "png_sha256": "a" * 64}}, 404),
        ({**_NOTE, "frame": {"stem": _DARK, "png_sha256": "not-a-digest"}}, 400),
        ({**_NOTE, "element_sha256": "not-a-digest"}, 400),
        ({**_NOTE, "body": "   "}, 400),
        ({key: value for key, value in _NOTE.items() if key != "body"}, 400),
        ({key: value for key, value in _NOTE.items() if key != "run"}, 400),
        ({**_NOTE, "stem": _DARK}, 400),
    ],
)
def test_a_malformed_note_is_refused_and_stores_nothing(
    review: _Review,
    payload: dict[str, object],
    expected_status: int,
) -> None:
    status, answer = review.json("POST", "/api/notes", payload)

    assert status == expected_status
    assert isinstance(answer, dict)
    assert answer["error"]
    assert ReviewStore(review.store_path).notes() == ()


def test_resolve_reopen_and_delete_through_the_api(review: _Review) -> None:
    _, created = review.json("POST", "/api/notes", {**_NOTE, "body": "Low contrast."})
    assert isinstance(created, dict)
    note_id = created["id"]

    status, resolved = review.json("POST", f"/api/notes/{note_id}/resolved", {"resolved": True})
    assert status == 200
    assert isinstance(resolved, dict)
    assert resolved["resolved_at"]
    assert ReviewStore(review.store_path).notes(include_resolved=False) == ()

    status, _ = review.json("POST", f"/api/notes/{note_id}/resolved", {"resolved": False})
    assert status == 200
    assert len(ReviewStore(review.store_path).notes(include_resolved=False)) == 1

    status, _ = review.json("DELETE", f"/api/notes/{note_id}")
    assert status == 200
    assert ReviewStore(review.store_path).notes() == ()

    status, _ = review.json("DELETE", f"/api/notes/{note_id}")
    assert status == 404


def _sign_off(review: _Review, digest: str, *, reviewed: bool = True) -> int:
    status, _ = review.json(
        "POST",
        "/api/reviewed",
        {"run": "current", "element": _ELEMENT, "element_sha256": digest, "reviewed": reviewed},
    )
    return status


def test_a_sign_off_covers_every_frame_and_a_re_render_names_the_one_that_moved(review: _Review) -> None:
    assert _sign_off(review, review.element_digest()) == 200
    assert review.state_now()["sign_offs"] == {
        _ELEMENT: {
            "run": "current",
            "reviewed_at": ReviewStore(review.store_path).sign_offs()[_ELEMENT].reviewed_at,
            "current": True,
            "changed": [],
            "added": [],
            "removed": [],
        }
    }
    assert ReviewStore(review.store_path).sign_offs()[_ELEMENT].frames == {
        "home--ready/small/dark": review.digests[_DARK],
        "home--ready/small/light": review.digests[_LIGHT],
    }

    _write_png(review.runs / "current" / "png" / f"{_DARK}.png", (90, 20, 30))
    _write_png(review.runs / "current" / "png" / "home--empty__small__dark.png", (1, 2, 3))
    review.state.refresh()
    mark = review.state_now()["sign_offs"]

    assert (mark[_ELEMENT]["current"], mark[_ELEMENT]["changed"], mark[_ELEMENT]["added"]) == (
        False,
        ["home--ready/small/dark"],
        ["home--empty/small/dark"],
    )

    assert _sign_off(review, review.element_digest(), reviewed=False) == 200
    assert ReviewStore(review.store_path).sign_offs() == {}


def test_a_sign_off_against_images_the_page_no_longer_shows_is_refused(review: _Review) -> None:
    seen = review.element_digest()
    _write_png(review.runs / "current" / "png" / f"{_LIGHT}.png", (1, 200, 1))
    review.state.refresh()

    assert _sign_off(review, seen) == 409
    assert ReviewStore(review.store_path).sign_offs() == {}
    assert _sign_off(review, review.element_digest()) == 200


def _next_event(response: HTTPResponse) -> int:
    """Read the stream up to the next change event, skipping keep-alive comments."""
    while True:
        line = response.readline().decode("utf-8")
        if not line:
            raise AssertionError("the event stream closed")
        if line.startswith("data: "):
            return int(line.removeprefix("data: "))


def test_the_event_stream_announces_a_frame_that_lands_while_it_is_open(review: _Review) -> None:
    connection = HTTPConnection("127.0.0.1", review.port, timeout=10)
    try:
        connection.request("GET", "/events")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith("text/event-stream")
        opened_at = _next_event(response)

        _write_png(review.runs / "current" / "png" / "home--ready__medium__dark.png", (5, 5, 5))
        announced = _next_event(response)

        assert announced > opened_at
        _, state = review.json("GET", "/api/state")
        assert isinstance(state, dict)
        assert "home--ready__medium__dark" in {frame["stem"] for frame in state["frames"]}
    finally:
        connection.close()


# Documentation addresses (RFC 5737, RFC 3849) and a reserved name: the parse
# does not judge ranges, and a real node's address or name has no place here.
_NODE_V4 = "192.0.2.10"
_NODE_V6 = "2001:db8::10"
_NODE_NAME = "review-host.example.invalid"


def _status(backend: str, node: object) -> str:
    return json.dumps({"BackendState": backend, "Self": node, "Peer": None, "Version": "1.0"})


def test_a_running_node_yields_its_ipv4_address_and_magicdns_name() -> None:
    node = parse_tailnet_status(
        _status("Running", {"TailscaleIPs": [_NODE_V6, _NODE_V4], "DNSName": f"{_NODE_NAME}.", "OS": "windows"}),
    )

    assert node == TailnetNode(address=_NODE_V4, name=_NODE_NAME)


def test_a_node_without_magicdns_still_yields_its_address() -> None:
    node = parse_tailnet_status(_status("Running", {"TailscaleIPs": [_NODE_V4], "DNSName": ""}))

    assert node == TailnetNode(address=_NODE_V4, name=None)


@pytest.mark.parametrize(
    "payload",
    [
        _status("Stopped", None),
        _status("NeedsLogin", {"TailscaleIPs": [], "DNSName": ""}),
        _status("Running", {"TailscaleIPs": [_NODE_V6], "DNSName": f"{_NODE_NAME}."}),
        _status("Running", None),
        "tailscaled is not running",
        json.dumps({"Self": {"TailscaleIPs": [_NODE_V4]}}),
    ],
)
def test_anything_short_of_a_running_node_with_an_ipv4_address_is_refused(payload: str) -> None:
    with pytest.raises(TailnetUnavailableError):
        parse_tailnet_status(payload)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (str(ipaddress.IPv4Address(0)), True),
        (str(ipaddress.IPv6Address(0)), True),
        (f"[{ipaddress.IPv6Address(0)}]", True),
        ("", True),
        ("127.0.0.1", False),
        (_NODE_V4, False),
    ],
)
def test_wildcard_hosts_are_recognised(host: str, expected: bool) -> None:
    assert is_wildcard_host(host) is expected
