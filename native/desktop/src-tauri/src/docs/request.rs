use super::{
    compose,
    media::MediaTypes,
    policy::SCHEME,
    site::{Served, Site},
};
use cadrumo_application::value::RelativePath;
use std::{fs, path::Path};
use tauri::http::{Method, Request, Response, StatusCode, header};

const HOST: &str = "localhost";
const DIRECTORY_INDEX: &str = "index.html";
const NO_SNIFF: &str = "nosniff";

/// Answers one request on the documentation scheme. An address is served only
/// when `media` types its name, and its bytes come from the stored form, a
/// page being composed on the way out. Every response, refusals included,
/// carries `policy` and `nosniff`.
pub fn respond(
    site: &Site,
    media: &MediaTypes,
    policy: &str,
    request: &Request<Vec<u8>>,
) -> Response<Vec<u8>> {
    let head = match *request.method() {
        Method::GET => false,
        Method::HEAD => true,
        _ => return refusal(StatusCode::METHOD_NOT_ALLOWED, policy),
    };
    if !addressed(request) {
        return refusal(StatusCode::NOT_FOUND, policy);
    }
    let Some(path) = member_path(request.uri().path()) else {
        return refusal(StatusCode::BAD_REQUEST, policy);
    };
    // The address's own name decides the media type, whatever it is stored as.
    let Some(content_type) = media.of_member(&path) else {
        return refusal(StatusCode::NOT_FOUND, policy);
    };
    let Some(served) = site.resolve(&path) else {
        return refusal(StatusCode::NOT_FOUND, policy);
    };
    let bytes = match served {
        Served::File(stored) => match read_contained(site.root(), &stored) {
            Some(bytes) => bytes,
            None => return refusal(StatusCode::NOT_FOUND, policy),
        },
        Served::Page {
            structure,
            language,
        } => {
            let Some(stored) = read_contained(site.root(), &structure) else {
                return refusal(StatusCode::NOT_FOUND, policy);
            };
            // A structure that is not text, a slot the language has no string
            // for and an unreadable text are all a broken package. Half a page
            // must never reach the frame, so nothing is sent.
            let composed = std::str::from_utf8(&stored)
                .ok()
                .zip(site.text(language))
                .and_then(|(structure, strings)| compose::page(structure, strings));
            match composed {
                Some(page) => page.into_bytes(),
                None => return refusal(StatusCode::INTERNAL_SERVER_ERROR, policy),
            }
        }
    };
    let length = bytes.len();
    response(StatusCode::OK, policy)
        .header(header::CONTENT_TYPE, content_type.clone())
        .header(header::CONTENT_LENGTH, length)
        .body(if head { Vec::new() } else { bytes })
        .unwrap_or_else(|_| failed())
}

/// Wry hands every `http(s)://cadrumo-docs.*` request to this scheme and
/// rewrites only the exact local host back to `cadrumo-docs://localhost`, so
/// anything else is a request for another host.
fn addressed(request: &Request<Vec<u8>>) -> bool {
    let uri = request.uri();
    uri.scheme_str() == Some(SCHEME)
        && uri
            .authority()
            .is_some_and(|authority| authority.as_str() == HOST)
}

/// Turns a request path into a manifest key. Dot segments, empty segments,
/// backslashes, drive or stream separators and controls are refused, as is
/// any percent escape that would encode a separator, a dot, a percent sign or
/// a control, so no decoded form can mean a different path than it reads.
pub fn member_path(raw: &str) -> Option<RelativePath> {
    let relative = raw.strip_prefix('/')?;
    let mut decoded = Vec::with_capacity(relative.len());
    let mut bytes = relative.bytes();
    while let Some(byte) = bytes.next() {
        if byte == b'%' {
            let high = hex(bytes.next()?)?;
            let low = hex(bytes.next()?)?;
            let value = high << 4 | low;
            if b"/\\.%".contains(&value) || value < 0x20 || value == 0x7f {
                return None;
            }
            decoded.push(value);
        } else if byte == b'\\' {
            return None;
        } else {
            decoded.push(byte);
        }
    }
    let mut path = String::from_utf8(decoded).ok()?;
    if path.is_empty() || path.ends_with('/') {
        path.push_str(DIRECTORY_INDEX);
    }
    RelativePath::new(path).ok()
}

fn hex(byte: u8) -> Option<u8> {
    char::from(byte).to_digit(16).map(|digit| digit as u8)
}

/// Reads a stored file only when it resolves beneath the root and is not
/// itself a link, so a replaced file or directory cannot redirect a read
/// elsewhere. Structures and text files are read through here too.
pub(super) fn read_contained(root: &Path, path: &RelativePath) -> Option<Vec<u8>> {
    let candidate = path.under(root);
    let metadata = fs::symlink_metadata(&candidate).ok()?;
    if !metadata.is_file() || linked(&metadata) {
        return None;
    }
    let resolved = fs::canonicalize(&candidate).ok()?;
    if !resolved.starts_with(root) {
        return None;
    }
    fs::read(resolved).ok()
}

#[cfg(windows)]
fn linked(metadata: &fs::Metadata) -> bool {
    use std::os::windows::fs::MetadataExt;
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
    metadata.file_type().is_symlink()
        || metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
}

#[cfg(not(windows))]
fn linked(metadata: &fs::Metadata) -> bool {
    metadata.file_type().is_symlink()
}

fn response(status: StatusCode, policy: &str) -> tauri::http::response::Builder {
    Response::builder()
        .status(status)
        .header(header::CONTENT_SECURITY_POLICY, policy)
        .header(header::X_CONTENT_TYPE_OPTIONS, NO_SNIFF)
        .header(header::CACHE_CONTROL, "no-cache")
}

pub fn refusal(status: StatusCode, policy: &str) -> Response<Vec<u8>> {
    let mut builder = response(status, policy)
        .header(header::CONTENT_TYPE, "text/plain; charset=utf-8")
        .header(header::CONTENT_LENGTH, 0);
    if status == StatusCode::METHOD_NOT_ALLOWED {
        builder = builder.header(header::ALLOW, "GET, HEAD");
    }
    builder.body(Vec::new()).unwrap_or_else(|_| failed())
}

/// A response whose headers could not be built still refuses everything.
fn failed() -> Response<Vec<u8>> {
    let mut response = Response::new(Vec::new());
    *response.status_mut() = StatusCode::INTERNAL_SERVER_ERROR;
    let headers = response.headers_mut();
    headers.insert(
        header::CONTENT_SECURITY_POLICY,
        header::HeaderValue::from_static(super::policy::CLOSED),
    );
    headers.insert(
        header::X_CONTENT_TYPE_OPTIONS,
        header::HeaderValue::from_static(NO_SNIFF),
    );
    response
}
