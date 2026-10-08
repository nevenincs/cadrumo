"""Raw HTTP transport for a single package/version index lookup.

Callers choose their own endpoint and response policies, then interpret status
codes and any returned metadata at their owning boundary.
"""

from __future__ import annotations

import http.client
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote

from packaging.version import Version


class EndpointQueryPolicy(StrEnum):
    """Whether an index endpoint's query string belongs on the request path."""

    OMIT = "omit"
    PRESERVE = "preserve"


class ResponseReadPolicy(StrEnum):
    """How much of a response to consume for this index question."""

    FULL_BODY = "full-body"
    FIRST_BYTE = "first-byte"


@dataclass(frozen=True, slots=True)
class PackageIndexResponse:
    """The raw status and response body read under the caller's policy."""

    status: int
    body: bytes


def package_index_connection(
    scheme: str,
    hostname: str,
    port: int | None,
    *,
    timeout_s: int,
) -> http.client.HTTPConnection:
    """Construct an HTTP(S) connection after endpoint policy validation."""
    if scheme == "https":
        connection_type = http.client.HTTPSConnection
    elif scheme == "http":
        connection_type = http.client.HTTPConnection
    else:
        raise ValueError(f"unsupported package-index scheme {scheme!r}")
    return connection_type(hostname, port, timeout=timeout_s)


def package_version_request_target(
    endpoint_path: str,
    endpoint_query: str,
    project: str,
    version: str | Version,
    *,
    query_policy: EndpointQueryPolicy,
) -> str:
    """Build the ``/<project>/<version>/json`` target from separate segments."""
    target = f"{endpoint_path.rstrip('/')}/{quote(project, safe='')}/{quote(str(version), safe='')}/json"
    if query_policy is EndpointQueryPolicy.PRESERVE and endpoint_query:
        target = f"{target}?{endpoint_query}"
    elif query_policy is not EndpointQueryPolicy.OMIT and query_policy is not EndpointQueryPolicy.PRESERVE:
        raise ValueError(f"unsupported package-index query policy {query_policy!r}")
    return target


def request_package_version(
    connection: http.client.HTTPConnection,
    request_target: str,
    *,
    read_policy: ResponseReadPolicy,
) -> PackageIndexResponse:
    """GET one package version, consume its explicit response policy, and close."""
    try:
        connection.request("GET", request_target, headers={"Accept": "application/json"})
        response = connection.getresponse()
        if read_policy is ResponseReadPolicy.FULL_BODY:
            body = response.read()
        elif read_policy is ResponseReadPolicy.FIRST_BYTE:
            body = response.read(1)
        else:
            raise ValueError(f"unsupported package-index response read policy {read_policy!r}")
        return PackageIndexResponse(status=response.status, body=body)
    finally:
        connection.close()
