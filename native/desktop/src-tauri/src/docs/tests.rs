use super::{
    compose,
    media::{self, MediaTypes},
    open,
    policy::{self, CLOSED, SCHEME},
    request::{member_path, respond},
    site::{self, Site},
};
use cadrumo_application::error::application::ErrorCode;
use std::{
    fs,
    path::{Path, PathBuf},
};
use tauri::{
    Config,
    http::{Method, Request, Response, StatusCode, header},
    utils::config::{Csp, FrontendDist, WindowConfig},
};

const DIGEST: &str = "0000000000000000000000000000000000000000000000000000000000000000";
const HASH: &str = "sha256-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6g=";

/// The format vector `dev/docs/tests/test_shared_structure.py` pins too: the
/// same structure and strings must compose to the same page on both sides.
const VECTOR_STRUCTURE: &str = "<p>\u{e000}0\u{e001}</p><i>\u{e000}a\u{e001}</i>";
const VECTOR_PAGE: &str = "<p>uno</p><i>dos & tres</i>";
const SPANISH_PAGE: &str = "<p>una</p><i>dos y tres</i>";

/// Eleven strings, of which the vector's structure names the first and the
/// eleventh; the nine between stand for the strings other pages name.
fn strings(first: &str, eleventh: &str) -> Vec<String> {
    let mut strings = vec![String::from("unnamed"); 11];
    strings[0] = first.to_owned();
    strings[10] = eleventh.to_owned();
    strings
}

struct Scratch(PathBuf);
impl Scratch {
    fn new(label: &str) -> Self {
        let path = std::env::temp_dir().join(format!(
            "cadrumo-docs-{label}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir_all(&path).unwrap();
        Self(path)
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        if let Err(error) = fs::remove_dir_all(&self.0) {
            eprintln!("docs fixture left at {:?}: {error}", self.0);
        }
    }
}

fn write(root: &Path, relative: &str, bytes: &[u8]) {
    let path = root.join(relative);
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, bytes).unwrap();
}

/// The stored form of a two-language site: `structure/` holds a page's
/// structure or a file every language shares, `text/<language>.json` holds a
/// language's strings and `languages/<language>/` the rest.
struct Package {
    /// Stored paths and their bytes; the manifest lists every one.
    stored: Vec<(String, Vec<u8>)>,
    /// Stored paths the manifest lists and the tree does not hold.
    absent: Vec<String>,
    /// Paths written into the tree that the manifest does not list.
    unlisted: Vec<(String, Vec<u8>)>,
    /// Site paths composed from their structure.
    pages: Vec<String>,
}

impl Package {
    /// One page, each language's text and the one search index at the apex.
    fn new() -> Self {
        let mut package = Self {
            stored: Vec::new(),
            absent: Vec::new(),
            unlisted: Vec::new(),
            pages: vec!["index.html".into()],
        };
        package.add("structure/index.html", VECTOR_STRUCTURE.as_bytes());
        package.add("structure/pagefind/pagefind.js", b"one index");
        package.text("en", &strings("uno", "dos & tres"));
        package.text("es", &strings("una", "dos y tres"));
        package
    }

    fn add(&mut self, path: &str, bytes: &[u8]) -> &mut Self {
        self.stored.push((path.to_owned(), bytes.to_vec()));
        self
    }

    /// A file every language shares, stored once, its bytes its site path.
    fn shared(&mut self, site_path: &str) -> &mut Self {
        self.add(&format!("structure/{site_path}"), site_path.as_bytes())
    }

    fn text(&mut self, language: &str, strings: &[String]) -> &mut Self {
        let json = serde_json::to_vec(strings).unwrap();
        self.add(&format!("text/{language}.json"), &json)
    }

    /// Replaces the bytes of an already stored path.
    fn replace(&mut self, path: &str, bytes: &[u8]) -> &mut Self {
        let stored = self
            .stored
            .iter_mut()
            .find(|(stored, _)| stored == path)
            .expect("a stored path");
        stored.1 = bytes.to_vec();
        self
    }

    fn manifest(&self) -> serde_json::Value {
        let files: serde_json::Map<String, serde_json::Value> = self
            .stored
            .iter()
            .map(|(path, _)| path.clone())
            .chain(self.absent.iter().cloned())
            .map(|path| (path, serde_json::Value::from(DIGEST)))
            .collect();
        serde_json::json!({
            "schema": 2,
            "languages": ["en", "es"],
            "apex_language": "en",
            "entries": {"en": "index.html", "es": "es/index.html"},
            "search": "pagefind/pagefind.js",
            "script_hashes": [HASH],
            "stored": {
                "structure": "structure",
                "languages": "languages",
                "text": {"en": "text/en.json", "es": "text/es.json"},
            },
            "pages": self.pages,
            "files": files,
        })
    }

    fn write_into(&self, root: &Path) {
        for (path, bytes) in self.stored.iter().chain(&self.unlisted) {
            write(root, path, bytes);
        }
        write(
            root,
            "manifest.json",
            self.manifest().to_string().as_bytes(),
        );
    }
}

/// Writes a package into a scratch tree and returns where it is.
fn staged(label: &str, package: &Package) -> (Scratch, PathBuf) {
    let scratch = Scratch::new(label);
    let root = scratch.0.join("user");
    package.write_into(&root);
    (scratch, root)
}

fn admitted(label: &str, package: &Package) -> (Scratch, Site) {
    let (scratch, root) = staged(label, package);
    let site = Site::open(&root, &root.join("manifest.json")).unwrap();
    (scratch, site)
}

/// A staged tree holding the stored form and `extra` as files every language
/// shares, each file's bytes its own site path.
fn tree(label: &str, extra: &[String]) -> (Scratch, Site) {
    let mut package = Package::new();
    for site_path in extra {
        package.shared(site_path);
    }
    admitted(label, &package)
}

/// The files every language shares in the richer fixture. `objects.inv` is
/// outside the media table and `absent.html` is listed without being stored.
const SHARED: &[&str] = &[
    "_static/furo.css",
    "pagefind/pagefind-worker.js",
    "pagefind/pagefind-entry.json",
    "pagefind/wasm.en.pagefind",
    "pagefind/index/en_1.pf_index",
    "pagefind/fragment/en_1.pf_fragment",
    "objects.inv",
];

/// The stored form plus shared files, one Spanish-only file, a listed file
/// absent from disk and a file on disk the manifest does not list.
fn fixture(label: &str) -> (Scratch, Site) {
    admitted(label, &rich())
}

fn rich() -> Package {
    let mut package = Package::new();
    for site_path in SHARED {
        package.shared(site_path);
    }
    package.add("languages/es/local.js", b"es only");
    package.absent.push("structure/absent.html".into());
    package
        .unlisted
        .push(("stray.html".into(), b"stray".to_vec()));
    package
}

/// The media-type table the package layout declares for this build.
fn declared() -> MediaTypes {
    MediaTypes::declared().unwrap()
}

/// The layout's `user_docs.media_types`, read independently of the host's
/// parser.
fn declared_table() -> serde_json::Value {
    let contract: serde_json::Value = serde_json::from_str(media::CONTRACT).unwrap();
    contract["layout"]["user_docs"]["media_types"].clone()
}

fn get(method: Method, uri: &str) -> Request<Vec<u8>> {
    Request::builder()
        .method(method)
        .uri(uri)
        .body(Vec::new())
        .unwrap()
}

const POLICY: &str = "default-src 'self'; frame-ancestors http://tauri.localhost";

fn assert_guarded(response: &Response<Vec<u8>>, policy: &str) {
    assert_eq!(
        response.headers()[header::CONTENT_SECURITY_POLICY],
        policy,
        "{:?}",
        response.status()
    );
    assert_eq!(
        response.headers()[header::X_CONTENT_TYPE_OPTIONS],
        "nosniff"
    );
}

fn served(site: &Site, method: Method, uri: &str) -> Response<Vec<u8>> {
    let response = respond(site, &declared(), POLICY, &get(method, uri));
    assert_guarded(&response, POLICY);
    response
}

fn address(site: &Site, path: &str) -> Response<Vec<u8>> {
    served(
        site,
        Method::GET,
        &format!("cadrumo-docs://localhost{path}"),
    )
}

#[test]
fn paths_map_to_manifest_keys_only_without_escapes() {
    for (raw, key) in [
        ("/index.html", "index.html"),
        ("/", "index.html"),
        ("/es/", "es/index.html"),
        ("/_static/furo.css", "_static/furo.css"),
        (
            "/pagefind/index/en%5F1.pf_index",
            "pagefind/index/en_1.pf_index",
        ),
        ("/how-to/caf%C3%A9.html", "how-to/café.html"),
    ] {
        assert_eq!(member_path(raw).unwrap().as_str(), key, "{raw}");
    }
    for raw in [
        "",
        "index.html",
        "/../index.html",
        "/es/../index.html",
        "/./index.html",
        "/es/.",
        "/..",
        "/a//b.html",
        "//server/share/index.html",
        "/C:/Windows/win.ini",
        "/index.html:stream",
        "/es\\index.html",
        "/%2e%2e/index.html",
        "/%2E%2E/index.html",
        "/.%2e/index.html",
        "/es%2findex.html",
        "/es%2Findex.html",
        "/es%5cindex.html",
        "/%252e%252e/index.html",
        "/index%00.html",
        "/index%0a.html",
        "/index%7f.html",
        "/index%.html",
        "/index%2.html",
        "/index%zz.html",
        "/%ff.html",
        "/CON.html",
        "/index.html.",
    ] {
        assert!(member_path(raw).is_none(), "{raw:?}");
    }
}

/// The vector both sides of the format pin, replayed from
/// `test_the_format_is_the_one_the_desktop_host_composes`: the same structure
/// and the same eleven strings compose to the same page.
#[test]
fn the_shared_format_vector_composes_to_its_page() {
    let strings: Vec<String> = std::iter::once("uno")
        .chain(std::iter::repeat_n("", 9))
        .chain(std::iter::once("dos & tres"))
        .map(str::to_owned)
        .collect();
    assert_eq!(strings.len(), 11);
    assert_eq!(
        compose::page(VECTOR_STRUCTURE, &strings).unwrap(),
        VECTOR_PAGE
    );
    // A structure without a slot is the page, and a page is left alone.
    assert_eq!(compose::page(VECTOR_PAGE, &strings).unwrap(), VECTOR_PAGE);
}

/// One structure plus each language's text gives each language's page, at the
/// addresses the language switcher uses.
#[test]
fn each_language_gets_its_own_page_from_the_one_structure() {
    let (_scratch, site) = fixture("languages");
    for (path, page) in [
        ("/index.html", VECTOR_PAGE),
        ("/", VECTOR_PAGE),
        ("/es/index.html", SPANISH_PAGE),
        ("/es/", SPANISH_PAGE),
    ] {
        let response = address(&site, path);
        assert_eq!(response.status(), StatusCode::OK, "{path}");
        assert_eq!(
            response.headers()[header::CONTENT_TYPE],
            "text/html; charset=utf-8",
            "{path}"
        );
        assert_eq!(response.body(), page.as_bytes(), "{path}");
    }
}

/// A file identical in every language is stored once and answers every
/// language's address for it.
#[test]
fn a_shared_file_answers_every_language_from_one_stored_copy() {
    let (scratch, site) = fixture("shared");
    for site_path in SHARED.iter().filter(|path| **path != "objects.inv") {
        let stored = scratch.0.join("user/structure").join(site_path);
        assert!(stored.is_file(), "{site_path}");
        for prefix in ["", "es/"] {
            let response = address(&site, &format!("/{prefix}{site_path}"));
            assert_eq!(response.status(), StatusCode::OK, "{prefix}{site_path}");
            assert_eq!(response.body(), site_path.as_bytes(), "{prefix}{site_path}");
        }
    }
}

/// A file one language alone has is served for that language and nowhere else.
#[test]
fn a_language_file_answers_its_own_language_only() {
    let (_scratch, site) = fixture("language-file");
    let served = address(&site, "/es/local.js");
    assert_eq!(served.status(), StatusCode::OK);
    assert_eq!(served.body(), b"es only");
    for path in ["/local.js", "/en/local.js"] {
        assert_eq!(
            address(&site, path).status(),
            StatusCode::NOT_FOUND,
            "{path}"
        );
    }
}

/// The stored layout is not a site: no request reaches a structure, a text
/// file or a language directory under its stored name.
#[test]
fn the_stored_layout_is_not_addressable() {
    let (_scratch, site) = fixture("stored");
    for path in [
        "/structure/index.html",
        "/structure/_static/furo.css",
        "/structure/pagefind/pagefind.js",
        "/es/structure/index.html",
        "/text/en.json",
        "/text/es.json",
        "/es/text/es.json",
        "/languages/es/local.js",
        "/languages/en/index.html",
        "/es/languages/es/local.js",
        "/manifest.json",
    ] {
        let response = address(&site, path);
        assert_eq!(response.status(), StatusCode::NOT_FOUND, "{path}");
        assert!(response.body().is_empty(), "{path}");
    }
}

/// A broken stored form is refused whole: no response carries part of a page.
#[test]
fn a_broken_stored_page_is_refused_without_partial_content() {
    let malformed = [
        // A slot the language has no string for.
        "<p>\u{e000}b\u{e001}</p>",
        // Delimiters that do not pair, and digits outside base 36.
        "<p>\u{e000}0</p>",
        "<p>0\u{e001}</p>",
        "<p>\u{e000}\u{e001}</p>",
        "<p>\u{e000}0!\u{e001}</p>",
        "<p>\u{e000}A\u{e001}</p>",
        "<p>\u{e000}-1\u{e001}</p>",
        // One number has one spelling, so a padded slot is malformed.
        "<p>\u{e000}00\u{e001}</p>",
    ];
    for (index, structure) in malformed.iter().enumerate() {
        let mut package = Package::new();
        package.replace("structure/index.html", structure.as_bytes());
        let (_scratch, site) = admitted(&format!("malformed-{index}"), &package);
        let response = address(&site, "/index.html");
        assert_eq!(
            response.status(),
            StatusCode::INTERNAL_SERVER_ERROR,
            "{structure:?}"
        );
        assert!(response.body().is_empty(), "{structure:?}");
    }
    // A structure that is not text at all.
    let mut bytes = Package::new();
    bytes.replace("structure/index.html", &[0xff, 0xfe]);
    let (_scratch, site) = admitted("not-text", &bytes);
    assert_eq!(
        address(&site, "/index.html").status(),
        StatusCode::INTERNAL_SERVER_ERROR
    );
    // Text that is absent, is not JSON, or is not a list of strings. The
    // other language keeps composing, because only its own text is broken.
    for (index, text) in [
        None,
        Some(&b"{"[..]),
        Some(&b"{\"0\":\"uno\"}"[..]),
        Some(&b"[1,2]"[..]),
    ]
    .into_iter()
    .enumerate()
    {
        let mut package = Package::new();
        match text {
            Some(bytes) => {
                package.replace("text/es.json", bytes);
            }
            None => {
                package.stored.retain(|(path, _)| path != "text/es.json");
                package.absent.push("text/es.json".into());
            }
        }
        let (_scratch, site) = admitted(&format!("text-{index}"), &package);
        let refused = address(&site, "/es/index.html");
        assert_eq!(
            refused.status(),
            StatusCode::INTERNAL_SERVER_ERROR,
            "{index}"
        );
        assert!(refused.body().is_empty(), "{index}");
        let apex = address(&site, "/index.html");
        assert_eq!(apex.status(), StatusCode::OK, "{index}");
        assert_eq!(apex.body(), VECTOR_PAGE.as_bytes(), "{index}");
    }
}

/// Every name and extension the layout declares is served as its declared
/// type, under a nested directory as at the root.
#[test]
fn every_declared_name_and_extension_is_served_as_its_declared_type() {
    let table = declared_table();
    let names = table["names"].as_object().unwrap();
    let extensions = table["extensions"].as_object().unwrap();
    assert!(!names.is_empty() && !extensions.is_empty());
    let mut expected = Vec::new();
    for (name, media) in names {
        expected.push((name.clone(), media.as_str().unwrap()));
    }
    for (extension, media) in extensions {
        let probe = format!("probe.{extension}");
        assert!(!names.contains_key(&probe), "{probe}");
        expected.push((probe, media.as_str().unwrap()));
    }
    let members: Vec<String> = expected
        .iter()
        .flat_map(|(name, _)| [name.clone(), format!("nested/{name}")])
        .collect();
    let (_scratch, site) = tree("declared", &members);
    let media = declared();
    for (name, declared) in &expected {
        assert_eq!(media.of(name).unwrap(), declared, "{name}");
        for member in [name.clone(), format!("nested/{name}")] {
            let response = address(&site, &format!("/{member}"));
            assert_eq!(response.status(), StatusCode::OK, "{member}");
            assert_eq!(
                response.headers()[header::CONTENT_TYPE],
                *declared,
                "{member}"
            );
            assert_eq!(response.body(), member.as_bytes(), "{member}");
        }
    }
}

/// An address the table does not type is not served, and its refusal carries
/// the policy and `nosniff` like every other response.
#[test]
fn undeclared_types_are_refused_with_the_policy_and_nosniff() {
    let table = declared_table();
    let undeclared = [
        "objects.inv",
        "furo.css.map",
        "index.HTML",
        "index.htm",
        "readme.txt",
        "font.ttf",
        "demo.gif",
        "Makefile",
        "html",
    ];
    for name in undeclared {
        let extension = name.rsplit_once('.').map(|(_, extension)| extension);
        assert!(table["names"].get(name).is_none(), "{name}");
        assert!(
            extension.is_none_or(|extension| table["extensions"].get(extension).is_none()),
            "{name}"
        );
    }
    let members: Vec<String> = undeclared
        .iter()
        .map(|name| format!("_static/{name}"))
        .collect();
    let (_scratch, site) = tree("undeclared", &members);
    for member in &members {
        assert!(
            site.resolve(&member_path(&format!("/{member}")).unwrap())
                .is_some()
        );
        for method in [Method::GET, Method::HEAD] {
            let uri = format!("cadrumo-docs://localhost/{member}");
            let response = served(&site, method, &uri);
            assert_eq!(response.status(), StatusCode::NOT_FOUND, "{member}");
            assert!(response.body().is_empty(), "{member}");
        }
    }
}

/// The case list the packaging gate's parser replays too: the same table
/// and names must give the same type, or none, on both sides.
const SHARED_CASES: &str = include_str!("media_type_cases.json");

#[test]
fn media_types_agree_with_the_packaging_gate_on_the_shared_cases() {
    let shared: serde_json::Value = serde_json::from_str(SHARED_CASES).unwrap();
    let media = MediaTypes::from_table(shared["table"].clone()).unwrap();
    let cases: Vec<(String, Option<String>)> =
        serde_json::from_value(shared["cases"].clone()).unwrap();
    assert!(!cases.is_empty());
    let mut members = Vec::new();
    for (name, expected) in &cases {
        let resolved = media.of(name).map(|value| value.to_str().unwrap());
        assert_eq!(resolved, expected.as_deref(), "{name}");
        if member_path(&format!("/{name}")).is_some() {
            members.extend([format!("cases/{name}"), format!("cases/nested/{name}")]);
        } else {
            // A name no request can address must not be one the table serves.
            assert_eq!(expected, &None, "{name}");
        }
    }
    let (_scratch, site) = tree("shared", &members);
    for member in &members {
        let name = member.rsplit('/').next().unwrap();
        let (_, expected) = cases.iter().find(|(case, _)| case == name).unwrap();
        let request = get(Method::GET, &format!("cadrumo-docs://localhost/{member}"));
        let response = respond(&site, &media, POLICY, &request);
        assert_guarded(&response, POLICY);
        match expected {
            Some(declared) => {
                assert_eq!(response.status(), StatusCode::OK, "{member}");
                assert_eq!(
                    response.headers()[header::CONTENT_TYPE],
                    declared.as_str(),
                    "{member}"
                );
            }
            None => assert_eq!(response.status(), StatusCode::NOT_FOUND, "{member}"),
        }
    }
}

#[test]
fn malformed_media_type_tables_refuse_the_scheme() {
    let shared: serde_json::Value = serde_json::from_str(SHARED_CASES).unwrap();
    let malformed = shared["malformed"].as_array().unwrap();
    assert!(!malformed.is_empty());
    // A type is sent as a header value, so it must be a valid one.
    let unsendable = serde_json::json!({
        "names": {},
        "extensions": {"html": "text/html\r\nx-injected: 1"}
    });
    for table in malformed.iter().chain([&unsendable]) {
        let error = MediaTypes::from_table(table.clone())
            .err()
            .expect("refused");
        assert_eq!(error.code, ErrorCode::PackageUnavailable, "{table}");
    }
}

#[test]
fn the_contract_must_declare_the_media_type_table() {
    assert!(MediaTypes::from_contract(media::CONTRACT).is_ok());
    let contract: serde_json::Value = serde_json::from_str(media::CONTRACT).unwrap();
    let mut absent = contract.clone();
    absent["layout"]["user_docs"]
        .as_object_mut()
        .unwrap()
        .remove("media_types");
    let mut empty = contract;
    empty["layout"]["user_docs"]["media_types"]["extensions"] = serde_json::json!({});
    for text in [absent.to_string(), empty.to_string(), "{".to_owned()] {
        let error = MediaTypes::from_contract(&text).err().expect("refused");
        assert_eq!(error.code, ErrorCode::PackageUnavailable);
    }
}

/// Every address carries its own type and the length of what it answers with,
/// composed or stored, and HEAD sends that length with no body.
#[test]
fn addresses_are_served_with_their_type_and_head_has_no_body() {
    let (_scratch, site) = fixture("members");
    for (path, media, body) in [
        ("/index.html", "text/html; charset=utf-8", VECTOR_PAGE),
        ("/", "text/html; charset=utf-8", VECTOR_PAGE),
        ("/es/", "text/html; charset=utf-8", SPANISH_PAGE),
        ("/es/index.html", "text/html; charset=utf-8", SPANISH_PAGE),
        (
            "/_static/furo.css?v=8d1f3b",
            "text/css; charset=utf-8",
            "_static/furo.css",
        ),
        (
            "/es/_static/furo.css",
            "text/css; charset=utf-8",
            "_static/furo.css",
        ),
        (
            "/pagefind/pagefind.js",
            "text/javascript; charset=utf-8",
            "one index",
        ),
        (
            "/pagefind/pagefind-worker.js",
            "text/javascript; charset=utf-8",
            "pagefind/pagefind-worker.js",
        ),
        (
            "/pagefind/pagefind-entry.json",
            "application/json",
            "pagefind/pagefind-entry.json",
        ),
        (
            "/pagefind/index/en_1.pf_index",
            "application/octet-stream",
            "pagefind/index/en_1.pf_index",
        ),
        (
            "/pagefind/wasm.en.pagefind",
            "application/octet-stream",
            "pagefind/wasm.en.pagefind",
        ),
        ("/es/local.js", "text/javascript; charset=utf-8", "es only"),
    ] {
        let length = body.len().to_string();
        let response = address(&site, path);
        assert_eq!(response.status(), StatusCode::OK, "{path}");
        assert_eq!(response.headers()[header::CONTENT_TYPE], media, "{path}");
        assert_eq!(response.body(), body.as_bytes(), "{path}");
        assert_eq!(
            response.headers()[header::CONTENT_LENGTH],
            length.as_str(),
            "{path}"
        );
        let head = served(
            &site,
            Method::HEAD,
            &format!("cadrumo-docs://localhost{path}"),
        );
        assert_eq!(head.status(), StatusCode::OK, "{path}");
        assert!(head.body().is_empty(), "{path}");
        assert_eq!(
            head.headers()[header::CONTENT_LENGTH],
            length.as_str(),
            "{path}"
        );
    }
}

#[test]
fn refusals_carry_the_policy_and_nosniff() {
    let (_scratch, site) = fixture("refusals");
    for (method, uri, status) in [
        (
            Method::POST,
            "cadrumo-docs://localhost/index.html",
            StatusCode::METHOD_NOT_ALLOWED,
        ),
        (
            Method::PUT,
            "cadrumo-docs://localhost/index.html",
            StatusCode::METHOD_NOT_ALLOWED,
        ),
        (
            Method::OPTIONS,
            "cadrumo-docs://localhost/index.html",
            StatusCode::METHOD_NOT_ALLOWED,
        ),
        (
            Method::DELETE,
            "cadrumo-docs://localhost/index.html",
            StatusCode::METHOD_NOT_ALLOWED,
        ),
        // Wry forwards every http(s)://cadrumo-docs.* host unchanged.
        (
            Method::GET,
            "http://cadrumo-docs.example.com/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "https://cadrumo-docs.localhost.example/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "http://cadrumo-docs.localhost/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://other/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost:8080/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://user@localhost/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "tauri://localhost/index.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/stray.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/manifest.json",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/absent.html",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/objects.inv",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/_/api/v3/embed/",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/_/api/v3/embed/?url=x",
            StatusCode::NOT_FOUND,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/%2e%2e/manifest.json",
            StatusCode::BAD_REQUEST,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/es/%2e%2e/index.html",
            StatusCode::BAD_REQUEST,
        ),
        (
            Method::GET,
            "cadrumo-docs://localhost/es/../index.html",
            StatusCode::BAD_REQUEST,
        ),
        (
            Method::HEAD,
            "cadrumo-docs://localhost/es%2findex.html",
            StatusCode::BAD_REQUEST,
        ),
    ] {
        let response = served(&site, method.clone(), uri);
        assert_eq!(response.status(), status, "{method} {uri}");
        assert!(response.body().is_empty(), "{uri}");
        if status == StatusCode::METHOD_NOT_ALLOWED {
            assert_eq!(response.headers()[header::ALLOW], "GET, HEAD");
        }
    }
}

#[test]
fn links_inside_the_tree_cannot_redirect_a_stored_read_outside_it() {
    let scratch = Scratch::new("links");
    let root = scratch.0.join("user");
    let outside = scratch.0.join("outside");
    write(&outside, "local.js", b"outside");
    let mut package = Package::new();
    package.add("languages/es/local.js", b"inside");
    package.write_into(&root);
    let spanish = root.join("languages").join("es");
    fs::remove_dir_all(&spanish).unwrap();
    link_directory(&outside, &spanish);
    let site = Site::open(&root, &root.join("manifest.json")).unwrap();
    assert!(fs::read(root.join("languages/es/local.js")).unwrap() == b"outside");
    assert_eq!(
        address(&site, "/es/local.js").status(),
        StatusCode::NOT_FOUND
    );
    assert_eq!(address(&site, "/index.html").body(), VECTOR_PAGE.as_bytes());

    // The same containment covers a structure and a language's text, which a
    // page is composed from and which no request names directly.
    let other = Scratch::new("links-stored");
    let root = other.0.join("user");
    let outside = other.0.join("outside");
    write(&outside, "furo.css", b"outside");
    write(
        &outside,
        "es.json",
        serde_json::to_vec(&strings("fuera", "fuera"))
            .unwrap()
            .as_slice(),
    );
    let mut package = Package::new();
    package.shared("_static/furo.css");
    package.write_into(&root);
    let shared = root.join("structure").join("_static");
    let text = root.join("text");
    for stored in [&shared, &text] {
        fs::remove_dir_all(stored).unwrap();
    }
    link_directory(&outside, &shared);
    link_directory(&outside, &text);
    let site = Site::open(&root, &root.join("manifest.json")).unwrap();
    assert_eq!(
        address(&site, "/_static/furo.css").status(),
        StatusCode::NOT_FOUND
    );
    for path in ["/index.html", "/es/index.html"] {
        assert_eq!(
            address(&site, path).status(),
            StatusCode::INTERNAL_SERVER_ERROR,
            "{path}"
        );
    }
}

#[cfg(windows)]
fn link_directory(target: &Path, link: &Path) {
    // A junction needs no privilege, unlike a Windows symbolic link.
    fs::create_dir_all(link.parent().unwrap()).unwrap();
    let status = std::process::Command::new("cmd")
        .arg("/C")
        .arg("mklink")
        .arg("/J")
        .arg(link)
        .arg(target)
        .stdout(std::process::Stdio::null())
        .status()
        .unwrap();
    assert!(status.success());
}

#[cfg(not(windows))]
fn link_directory(target: &Path, link: &Path) {
    fs::create_dir_all(link.parent().unwrap()).unwrap();
    std::os::unix::fs::symlink(target, link).unwrap();
}

#[test]
fn the_manifest_must_describe_a_consistent_stored_form() {
    let package = rich();
    let (_scratch, root) = staged("manifest", &package);
    let manifest_path = root.join("manifest.json");
    fs::remove_file(&manifest_path).unwrap();
    let missing = Site::open(&root, &manifest_path).err().unwrap();
    assert_eq!(missing.code, ErrorCode::PackageUnavailable);
    let valid = package.manifest();
    let mutate = |change: &dyn Fn(&mut serde_json::Value)| {
        let mut value = valid.clone();
        change(&mut value);
        fs::write(&manifest_path, value.to_string()).unwrap();
        Site::open(&root, &manifest_path)
    };
    assert!(mutate(&|_| {}).is_ok());
    for change in [
        &(|v: &mut serde_json::Value| v["schema"] = 1.into()) as &dyn Fn(&mut serde_json::Value),
        &|v| v["schema"] = 3.into(),
        &|v| v["languages"] = serde_json::json!([]),
        &|v| v["languages"] = serde_json::json!(["en", "en"]),
        &|v| v["languages"] = serde_json::json!(["en", "ES"]),
        &|v| v["apex_language"] = "ca".into(),
        // An entry that no stored file and no page answers.
        &|v| v["entries"]["es"] = "es/nowhere.html".into(),
        &|v| v["entries"]["es"] = "../index.html".into(),
        &|v| {
            v["entries"].as_object_mut().unwrap().remove("es");
        },
        // The apex language's site is at the top, so no entry sits under it.
        &|v| v["entries"]["en"] = "en/index.html".into(),
        &|v| v["search"] = "pagefind/absent.js".into(),
        &|v| v["script_hashes"] = serde_json::json!(["sha256-abc"]),
        &|v| {
            v["script_hashes"] =
                serde_json::json!(["sha384-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6g="])
        },
        &|v| {
            v["script_hashes"] = serde_json::json!([
                "sha256-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6g='; script-src *"
            ])
        },
        // The text languages must be exactly the declared languages.
        &|v| {
            v["stored"]["text"].as_object_mut().unwrap().remove("es");
        },
        &|v| v["stored"]["text"]["ca"] = "text/ca.json".into(),
        // A text file or a page's structure outside the inventory.
        &|v| v["stored"]["text"]["es"] = "text/absent.json".into(),
        &|v| v["stored"]["structure"] = "structures".into(),
        &|v| v["pages"] = serde_json::json!(["index.html", "how-to/absent.html"]),
        &|v| v["files"]["a/../b.html"] = DIGEST.into(),
        &|v| v["files"]["structure/index.html"] = "not-a-digest".into(),
    ] {
        let error = mutate(change).err().expect("refused");
        assert_eq!(error.code, ErrorCode::PackageUnavailable);
    }
    let elsewhere = root.parent().unwrap().join("manifest.json");
    fs::write(&elsewhere, valid.to_string()).unwrap();
    assert!(Site::open(&root, &elsewhere).is_err());
    assert!(Site::open(Path::new("user"), Path::new("user/manifest.json")).is_err());
}

#[test]
fn script_hashes_admit_only_sha256_sources() {
    assert!(site::script_hash(HASH));
    for value in [
        "",
        "sha256-",
        "47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6g=",
        "sha256-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6g",
        "sha256-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6=g",
        "sha256-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6 =",
        "'sha256-47DEQpj8HBSa+/TjIW5Adh6bkdwGzRRYkKlTZKN0F6g='",
    ] {
        assert!(!site::script_hash(value), "{value:?}");
    }
}

#[test]
fn development_override_requires_a_staged_manifest_and_packaged_docs_stay_in_the_package() {
    let (scratch, _) = fixture("override");
    let staged = scratch.0.join("user");
    let package = scratch.0.join("package");
    let packaged_docs = package.join("docs/user");
    fs::create_dir_all(&packaged_docs).unwrap();
    let packaged_manifest = packaged_docs.join("manifest.json");
    let absent = open(&package, &packaged_docs, &packaged_manifest, None)
        .err()
        .unwrap();
    assert_eq!(absent.code, ErrorCode::PackageUnavailable);
    let selected = open(
        &package,
        &packaged_docs,
        &packaged_manifest,
        Some(staged.clone().into_os_string()),
    )
    .unwrap();
    assert_eq!(selected.root(), fs::canonicalize(&staged).unwrap());
    let unstaged = scratch.0.join("unstaged");
    write(&unstaged, "index.html", b"no manifest");
    let refused = open(
        &package,
        &packaged_docs,
        &packaged_manifest,
        Some(unstaged.into_os_string()),
    )
    .err()
    .unwrap();
    assert_eq!(refused.code, ErrorCode::PackageUnavailable);
    let blank = open(
        &package,
        &packaged_docs,
        &packaged_manifest,
        Some("".into()),
    )
    .err()
    .unwrap();
    assert_eq!(blank.code, ErrorCode::PackageUnavailable);
    let outside = open(&package, &staged, &staged.join("manifest.json"), None)
        .err()
        .unwrap();
    assert_eq!(outside.code, ErrorCode::PackageUnavailable);
}

#[test]
fn docs_origin_follows_the_platform_scheme_rule() {
    assert_eq!(
        policy::origin_for(true, false),
        "http://cadrumo-docs.localhost"
    );
    assert_eq!(
        policy::origin_for(true, true),
        "https://cadrumo-docs.localhost"
    );
    assert_eq!(policy::origin_for(false, false), "cadrumo-docs://localhost");
    assert_eq!(policy::origin_for(false, true), "cadrumo-docs://localhost");
    let mut window = WindowConfig::default();
    let insecure = policy::origin(&window);
    window.use_https_scheme = true;
    let secure = policy::origin(&window);
    if cfg!(windows) {
        assert_eq!(insecure, "http://cadrumo-docs.localhost");
        assert_eq!(secure, "https://cadrumo-docs.localhost");
    } else {
        assert_eq!(insecure, "cadrumo-docs://localhost");
        assert_eq!(secure, "cadrumo-docs://localhost");
    }
    assert_eq!(SCHEME, "cadrumo-docs");
}

#[test]
fn docs_policy_isolates_documentation_scripts_and_frames_only_the_shell() {
    let hashes = vec![HASH.to_owned()];
    let windows =
        policy::content_security_policy(&hashes, &["http://tauri.localhost".into()]).unwrap();
    assert_eq!(
        windows,
        format!(
            "default-src 'self'; script-src 'self' 'wasm-unsafe-eval' '{HASH}'; worker-src 'self'; \
             style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; \
             connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'; \
             form-action 'self'; frame-ancestors http://tauri.localhost"
        )
    );
    let linux = policy::content_security_policy(&hashes, &["tauri://localhost".into()]).unwrap();
    assert!(linux.ends_with("; frame-ancestors tauri://localhost"));
    // In a development build the shell origins include the dev server.
    let mut config = Config::default();
    let dev: tauri::Url = "http://127.0.0.1:1420/".parse().unwrap();
    config.build.dev_url = Some(dev.clone());
    config.build.frontend_dist = Some(FrontendDist::Url(dev));
    let mut window = WindowConfig::default();
    let origins = crate::shell::origins(&config, &window);
    assert!(tauri::is_dev() && origins.contains(&"http://127.0.0.1:1420".to_owned()));
    let development = policy::content_security_policy(&hashes, &origins).unwrap();
    assert!(development.ends_with(&format!("; frame-ancestors {}", origins.join(" "))));
    window.use_https_scheme = true;
    let secure =
        policy::content_security_policy(&hashes, &crate::shell::origins(&config, &window)).unwrap();
    if cfg!(windows) {
        assert!(secure.contains("frame-ancestors https://tauri.localhost http://127.0.0.1:1420"));
    }
    for origins in [
        vec![],
        vec!["http://tauri.localhost; script-src *".to_owned()],
        vec!["http://tauri.localhost 'unsafe-inline'".to_owned()],
        vec!["*".to_owned()],
        vec!["tauri.localhost".to_owned()],
    ] {
        assert!(
            policy::content_security_policy(&hashes, &origins).is_err(),
            "{origins:?}"
        );
    }
    assert!(CLOSED.contains("frame-ancestors 'none'") && CLOSED.contains("default-src 'none'"));
}

#[test]
fn shell_policy_must_frame_exactly_the_docs_origin() {
    let origin = "http://cadrumo-docs.localhost";
    let with = |csp: Option<&str>| {
        let mut config = Config::default();
        config.app.security.csp = csp.map(|policy| Csp::Policy(policy.into()));
        policy::shell_frames(&config, origin)
    };
    assert!(with(Some(
        "default-src 'self'; frame-src http://cadrumo-docs.localhost"
    )));
    assert!(!with(Some("default-src 'self'; frame-src 'none'")));
    assert!(!with(Some(
        "default-src 'self'; frame-src http://cadrumo-docs.localhost *"
    )));
    assert!(!with(Some(
        "default-src 'self'; frame-src https://cadrumo-docs.localhost"
    )));
    assert!(!with(Some("default-src 'self'")));
    assert!(!with(None));
}

/// The build writes the shell policy's frame source from the same rule this
/// crate applies at runtime; the generated configuration must agree.
#[test]
fn generated_shell_policy_frames_the_runtime_docs_origin() {
    let config: Config = serde_json::from_str(
        &std::env::var("TAURI_CONFIG").expect("the host test runner passes the generated config"),
    )
    .unwrap();
    let window = config.app.windows.first().unwrap();
    assert!(policy::shell_frames(&config, &policy::origin(window)));
}

/// Serves a real staged documentation tree: the development override when
/// set, otherwise the selected package's documentation.
#[cfg(feature = "live-package-tests")]
#[test]
fn staged_documentation_serves_pages_search_and_worker_with_the_policy() {
    let (root, development) = match std::env::var_os(super::DEVELOPMENT_ROOT) {
        Some(root) if !root.is_empty() => (PathBuf::from(&root), Some(root)),
        _ => (
            PathBuf::from(
                std::env::var_os("CADRUMO_DESKTOP_PACKAGE_ROOT").expect("select real package"),
            )
            .join("docs/user"),
            None,
        ),
    };
    let package = root.parent().unwrap().parent().unwrap().to_owned();
    let site = open(&package, &root, &root.join("manifest.json"), development).unwrap();
    let manifest: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("manifest.json")).unwrap()).unwrap();
    let hashes: Vec<String> = serde_json::from_value(manifest["script_hashes"].clone()).unwrap();
    assert_eq!(site.script_hashes(), hashes.as_slice());
    let shell = if cfg!(windows) {
        "http://tauri.localhost"
    } else {
        "tauri://localhost"
    };
    let csp = policy::content_security_policy(&hashes, &[shell.into()]).unwrap();
    for hash in &hashes {
        assert!(csp.contains(&format!("'{hash}'")));
    }
    // The staged form holds one search index at the apex and one structure
    // per page, so the probes are addresses and not stored paths.
    let search = manifest["search"].as_str().unwrap().to_owned();
    let directory = search.rsplit_once('/').map_or("", |(parent, _)| parent);
    let files = manifest["files"].as_object().unwrap();
    let first = |suffix: &str| {
        files
            .keys()
            .filter_map(|key| key.rsplit_once('/'))
            .find(|(parent, name)| parent.contains(directory) && name.ends_with(suffix))
            .map(|(parent, name)| {
                let kept = parent.rsplit_once(directory).unwrap().1;
                format!("{directory}{kept}/{name}")
            })
            .unwrap_or_else(|| panic!("no {suffix} in the staged search index"))
    };
    let mut probes = vec![
        (search.clone(), "text/javascript; charset=utf-8"),
        (
            format!("{directory}/pagefind-worker.js"),
            "text/javascript; charset=utf-8",
        ),
        (
            format!("{directory}/pagefind-entry.json"),
            "application/json",
        ),
        (first(".pf_index"), "application/octet-stream"),
        (first(".pf_fragment"), "application/octet-stream"),
        (first(".pf_meta"), "application/octet-stream"),
        (first(".pagefind"), "application/octet-stream"),
    ];
    for language in manifest["languages"].as_array().unwrap() {
        let entry = manifest["entries"][language.as_str().unwrap()]
            .as_str()
            .unwrap();
        probes.push((entry.to_owned(), "text/html; charset=utf-8"));
    }
    for (path, media) in probes {
        let response = respond(
            &site,
            &declared(),
            &csp,
            &get(Method::GET, &format!("cadrumo-docs://localhost/{path}")),
        );
        assert_guarded(&response, &csp);
        assert_eq!(response.status(), StatusCode::OK, "{path}");
        assert_eq!(response.headers()[header::CONTENT_TYPE], media, "{path}");
        assert!(!response.body().is_empty(), "{path}");
        println!("served {path} as {media}, {} bytes", response.body().len());
    }
    let refused = respond(
        &site,
        &declared(),
        &csp,
        &get(Method::GET, "cadrumo-docs://localhost/_/api/v3/embed/"),
    );
    assert_eq!(refused.status(), StatusCode::NOT_FOUND);
    assert_guarded(&refused, &csp);
}

#[test]
fn published_entries_are_docs_origin_urls_that_map_back_to_their_members() {
    let localized = "gu\u{ed}a de inicio#1.html";
    let mut package = Package::new();
    package.add(&format!("languages/es/{localized}"), b"page");
    let described = |mut value: serde_json::Value| {
        value["entries"]["es"] = format!("es/{localized}").into();
        value
    };
    let scratch = Scratch::new("published");
    let root = scratch.0.join("user");
    package.write_into(&root);
    write(
        &root,
        "manifest.json",
        described(package.manifest()).to_string().as_bytes(),
    );
    let site = Site::open(&root, &root.join("manifest.json")).unwrap();
    for windows in [true, false] {
        let origin = policy::origin_for(windows, false);
        let published = serde_json::to_value(super::published(&site, &origin).unwrap()).unwrap();
        assert_eq!(
            published,
            serde_json::json!({
                "origin": origin,
                "languages": [
                    {"code": "en", "entry": format!("{origin}/index.html")},
                    {"code": "es", "entry": format!("{origin}/es/gu%C3%ADa%20de%20inicio%231.html")},
                ],
            })
        );
        for (language, member) in published["languages"]
            .as_array()
            .unwrap()
            .iter()
            .zip(["index.html", &format!("es/{localized}")])
        {
            let entry = tauri::Url::parse(language["entry"].as_str().unwrap()).unwrap();
            // A custom scheme has an opaque URL origin; compare the text.
            assert!(entry.as_str().starts_with(&format!("{origin}/")), "{entry}");
            assert_eq!(
                member_path(entry.path()).unwrap().as_str(),
                member,
                "{entry}"
            );
        }
    }
}
