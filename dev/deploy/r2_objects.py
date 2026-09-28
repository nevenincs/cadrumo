"""Upload and list objects in a Cloudflare R2 bucket over its S3-compatible API.

A first-party client rather than an SDK or a cloud CLI: the publisher needs two
operations, ``PutObject`` and ``ListObjectsV2``, and signing them is a short,
fully specified algorithm (AWS Signature Version 4, which R2 implements with
the region ``auto``). Owning it keeps the delivery path free of a cloud CLI on
the runner and of a dependency pulled in for two calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import mimetypes
import threading
import time
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatch
from http.client import HTTPException, HTTPSConnection
from pathlib import Path
from types import MappingProxyType
from typing import Final
from urllib.parse import quote

from defusedxml import ElementTree

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory

_REGION: Final[str] = "auto"
_SERVICE: Final[str] = "s3"
_TIMEOUT_SECONDS: Final[int] = 60
_ATTEMPTS: Final[int] = 3
_S3_NAMESPACE: Final[str] = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_NO_QUERY: Final[Mapping[str, str]] = MappingProxyType(dict[str, str]())

#: Content types decided here rather than read from the host's MIME registry,
#: which differs between platforms (Windows maps ``.js`` from the registry) and
#: would make the served type depend on which machine published.
_CONTENT_TYPES: Final[Mapping[str, str]] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".xml": "application/xml",
    ".txt": "text/plain; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".wasm": "application/wasm",
    ".pdf": "application/pdf",
    ".map": "application/json",
}


@dataclass(frozen=True)
class R2Bucket:
    """One R2 bucket and the S3-compatible key that may write to it."""

    account_id: str
    name: str
    access_key_id: str
    secret_access_key: str

    @property
    def host(self) -> str:
        """Return the account's S3-compatible endpoint host."""
        return f"{self.account_id}.r2.cloudflarestorage.com"


def content_type_for(path: Path) -> str:
    """Return the served content type for one file, by extension."""
    suffix = path.suffix.lower()
    if suffix in _CONTENT_TYPES:
        return _CONTENT_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(path.name, strict=True)
    return guessed or "application/octet-stream"


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _object_path(bucket: R2Bucket, key: str) -> str:
    return f"/{quote(bucket.name, safe='')}/{quote(key, safe='/-_.~')}"


def signed_headers(
    bucket: R2Bucket,
    *,
    host: str,
    region: str = _REGION,
    method: str,
    path: str,
    query: Mapping[str, str],
    payload_hash: str,
    extra_headers: Mapping[str, str],
    now: datetime,
) -> dict[str, str]:
    """Return the request headers for one SigV4-signed R2 request.

    Args:
        bucket: The key the request is signed with.
        host: The endpoint host, which is part of the signature.
        region: The signing region; R2 signs with ``auto``.
        method: HTTP method.
        path: The already URI-encoded request path.
        query: Query parameters, unencoded.
        payload_hash: Hex SHA-256 of the request body.
        extra_headers: Additional headers that are signed and sent.
        now: The signing instant, injected so a signature is reproducible.
    """
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        **{name.lower(): value.strip() for name, value in extra_headers.items()},
    }
    canonical_query = "&".join(
        f"{quote(name, safe='-_.~')}={quote(value, safe='-_.~')}" for name, value in sorted(query.items())
    )
    signed = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
    canonical_request = "\n".join((method, path, canonical_query, canonical_headers, signed, payload_hash))
    scope = f"{date_stamp}/{region}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join(
        ("AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest())
    )
    signing_key = _hmac(
        _hmac(_hmac(_hmac(f"AWS4{bucket.secret_access_key}".encode(), date_stamp), region), _SERVICE),
        "aws4_request",
    )
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={bucket.access_key_id}/{scope}, SignedHeaders={signed}, Signature={signature}"
    )
    return headers


def _request(
    bucket: R2Bucket,
    *,
    method: str,
    path: str,
    query: Mapping[str, str] = _NO_QUERY,
    body: bytes = b"",
    extra_headers: Mapping[str, str] | None = None,
    connection: HTTPSConnection | None = None,
) -> tuple[int, bytes]:
    """Send one signed request, retrying transport failures, and return status and body."""
    target = path
    if query:
        target += "?" + "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(query.items()))
    last_error: Exception | None = None
    for _ in range(_ATTEMPTS):
        headers = signed_headers(
            bucket,
            host=bucket.host,
            method=method,
            path=path,
            query=query,
            payload_hash=hashlib.sha256(body).hexdigest(),
            extra_headers=extra_headers or {},
            now=datetime.now(UTC),
        )
        owned = connection is None
        active = connection or HTTPSConnection(bucket.host, timeout=_TIMEOUT_SECONDS)
        try:
            active.request(method, target, body=body, headers=headers)
            response = active.getresponse()
            payload = response.read()
            if response.status >= 500 or response.status == 429:
                last_error = OSError(f"R2 answered HTTP {response.status}")
                time.sleep(1)
                continue
            return response.status, payload
        except (HTTPException, TimeoutError, OSError) as exc:
            last_error = exc
            active.close()
            if not owned:
                connection = None
        finally:
            if owned:
                active.close()
    raise SystemExit(f"R2 {method} {path} failed after {_ATTEMPTS} attempts: {last_error}")


def put_object(
    bucket: R2Bucket,
    key: str,
    body: bytes,
    *,
    content_type: str,
    cache_control: str,
    connection: HTTPSConnection | None = None,
) -> None:
    """Write one object, refusing anything but a success."""
    status, payload = _request(
        bucket,
        method="PUT",
        path=_object_path(bucket, key),
        body=body,
        extra_headers={"content-type": content_type, "cache-control": cache_control},
        connection=connection,
    )
    if status != 200:
        raise SystemExit(f"R2 refused {key}: HTTP {status} {payload[:300]!r}")


def list_keys(bucket: R2Bucket, prefix: str) -> set[str]:
    """Return every key below ``prefix``, following continuation tokens."""
    keys: set[str] = set()
    token: str | None = None
    while True:
        query = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            query["continuation-token"] = token
        status, payload = _request(bucket, method="GET", path=f"/{quote(bucket.name, safe='')}", query=query)
        if status != 200:
            raise SystemExit(f"R2 refused to list {prefix!r}: HTTP {status} {payload[:300]!r}")
        document = ElementTree.fromstring(payload)
        keys.update(node.text or "" for node in document.iter(f"{_S3_NAMESPACE}Key"))
        truncated = (document.findtext(f"{_S3_NAMESPACE}IsTruncated") or "").strip() == "true"
        token = document.findtext(f"{_S3_NAMESPACE}NextContinuationToken")
        if not truncated or not token:
            return keys


def files_to_publish(root: Path, *, excludes: Iterable[str]) -> dict[str, Path]:
    """Return ``{relative key: file}`` for every file under ``root`` not excluded."""
    patterns = tuple(excludes)
    files: dict[str, Path] = {}
    for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES, require_root=True):
        relative = path.relative_to(root).as_posix()
        if any(fnmatch(relative, pattern) for pattern in patterns):
            continue
        files[relative] = path
    return files


def upload_tree(
    bucket: R2Bucket,
    root: Path,
    *,
    prefix: str,
    cache_control: str,
    excludes: Iterable[str] = (),
    workers: int = 64,
    report: Callable[[int, int], None] | None = None,
) -> set[str]:
    """Upload every file under ``root`` below ``prefix`` and return the written keys.

    Each worker thread keeps one connection, so a release of thousands of small
    files costs one TLS handshake per thread rather than one per object. A
    release is tens of thousands of small objects, most of them search-index
    fragments, and each PUT waits a round trip on R2 rather than on bandwidth or
    CPU, so the throughput scales with the number of requests in flight.
    """
    files = files_to_publish(root, excludes=excludes)
    local = threading.local()
    written: list[str] = []
    lock = threading.Lock()

    def upload(item: tuple[str, Path]) -> None:
        relative, path = item
        if not hasattr(local, "connection"):
            local.connection = HTTPSConnection(bucket.host, timeout=_TIMEOUT_SECONDS)
        key = f"{prefix}{relative}"
        put_object(
            bucket,
            key,
            path.read_bytes(),
            content_type=content_type_for(path),
            cache_control=cache_control,
            connection=local.connection,
        )
        with lock:
            written.append(key)
            if report is not None:
                report(len(written), len(files))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(upload, sorted(files.items())):
            pass
    return set(written)


def read_object(bucket: R2Bucket, key: str) -> bytes:
    """Read a required private release object, refusing missing data."""
    status, body = _request(bucket, method="GET", path=_object_path(bucket, key))
    if status != 200:
        raise ValueError(f"Cannot read release object {key}: HTTP {status}")
    return body


def object_inventory(bucket: R2Bucket, prefix: str) -> dict[str, tuple[int, str]]:
    """List exact sizes and object hashes, refusing incomplete pagination."""
    found: dict[str, tuple[int, str]] = {}
    token = ""
    seen: set[str] = set()
    while True:
        query = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
        if token:
            query["continuation-token"] = token
        status, body = _request(bucket, method="GET", path=f"/{quote(bucket.name, safe='')}", query=query)
        if status != 200:
            raise ValueError(f"Cannot inventory release: HTTP {status}")
        document = ElementTree.fromstring(body)
        for item in document.findall(f"{_S3_NAMESPACE}Contents"):
            key = item.findtext(f"{_S3_NAMESPACE}Key") or ""
            size = int(item.findtext(f"{_S3_NAMESPACE}Size") or "-1")
            etag = (item.findtext(f"{_S3_NAMESPACE}ETag") or "").strip('"')
            if not key or key in found:
                raise ValueError("Invalid or duplicate inventory key")
            found[key] = (size, etag)
        if document.findtext(f"{_S3_NAMESPACE}IsTruncated") != "true":
            return found
        token = document.findtext(f"{_S3_NAMESPACE}NextContinuationToken") or ""
        if not token or token in seen:
            raise ValueError("Incomplete R2 inventory pagination")
        seen.add(token)


def copy_public_object(source: R2Bucket, destination: R2Bucket, key: str, etag: str) -> None:
    """Copy verified search bytes server-side with immutable public metadata."""
    status, body = _request(
        destination,
        method="PUT",
        path=_object_path(destination, key),
        extra_headers={
            "x-amz-copy-source": _object_path(source, key),
            "x-amz-copy-source-if-match": f'"{etag}"',
            "x-amz-metadata-directive": "REPLACE",
            "content-type": "application/octet-stream",
            "cache-control": "public, max-age=31536000, immutable, no-transform",
        },
    )
    if status != 200 or ElementTree.fromstring(body).tag.endswith("Error"):
        raise ValueError(f"Public search copy failed: {key}, HTTP {status}")


@contextmanager
def deployment_lock(bucket: R2Bucket) -> Iterator[None]:
    """Serialize local and CI publishers with an atomic, non-expiring lease.

    A crashed publisher leaves the lock in place; an operator must inspect the
    recorded owner before removing it. Automatic expiry could let a slow upload
    race a second publisher and is intentionally not used.
    """
    key = "delivery/deployment-lock.json"
    owner = uuid.uuid4().hex
    body = json.dumps({"owner": owner, "created_at": datetime.now(UTC).isoformat()}).encode()
    status, _ = _request(
        bucket,
        method="PUT",
        path=_object_path(bucket, key),
        body=body,
        extra_headers={"if-none-match": "*", "content-type": "application/json"},
    )
    if status != 200:
        raise ValueError(f"Documentation deployment is locked or unavailable (HTTP {status}); inspect {key}")
    try:
        yield
    finally:
        current = json.loads(read_object(bucket, key))
        if current.get("owner") != owner:
            raise ValueError("Deployment lock owner changed; refusing to remove it")
        status, _ = _request(bucket, method="DELETE", path=_object_path(bucket, key))
        if status != 204:
            raise ValueError(f"Could not release deployment lock: HTTP {status}")
