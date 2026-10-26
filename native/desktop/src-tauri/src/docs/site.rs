use super::request::read_contained;
use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
    sync::OnceLock,
};

const MANIFEST_SCHEMA: u32 = 2;

/// The documentation manifest the packager writes beside the stored tree.
/// `entries` and `search` are addresses a request asks for; `stored`, `pages`
/// and `files` describe the files the package actually holds, which are one
/// structure, each language's text, and the files one language alone needs.
#[derive(Deserialize)]
struct Manifest {
    schema: u32,
    languages: Vec<String>,
    apex_language: String,
    entries: BTreeMap<String, RelativePath>,
    search: RelativePath,
    script_hashes: Vec<String>,
    stored: Stored,
    pages: Vec<RelativePath>,
    files: BTreeMap<RelativePath, Sha256Digest>,
}

/// Where each stored kind lives under the documentation root.
#[derive(Deserialize)]
struct Stored {
    structure: RelativePath,
    languages: RelativePath,
    text: BTreeMap<String, RelativePath>,
}

/// One language's text file and its strings once they have been read.
struct Text {
    file: RelativePath,
    strings: OnceLock<Option<Vec<String>>>,
}

/// Where one address's bytes come from.
pub enum Served<'a> {
    /// A stored file served as it is, either one language's own or the one
    /// copy every language shares.
    File(RelativePath),
    /// A page composed from its structure and one language's strings.
    Page {
        structure: RelativePath,
        language: &'a str,
    },
}

/// A documentation tree admitted for serving: its root and the manifest that
/// decides which addresses exist and how each is served.
pub struct Site {
    root: PathBuf,
    files: BTreeSet<RelativePath>,
    script_hashes: Vec<String>,
    /// Each language's entry page, in the manifest's language order.
    entries: Vec<(String, RelativePath)>,
    /// The one search index, at the site's apex.
    search: RelativePath,
    apex_language: String,
    languages: BTreeSet<String>,
    structure: RelativePath,
    language_files: RelativePath,
    /// The site paths that are composed rather than served as they are.
    pages: BTreeSet<String>,
    text: BTreeMap<String, Text>,
}

pub fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Package)
}

fn refused(reason: &'static str) -> ApplicationError {
    unavailable().caused_by(std::io::Error::other(reason))
}

/// A path inside one of the stored directories, or `None` when the joined
/// path is not a portable relative path.
fn joined(prefix: &RelativePath, rest: &str) -> Option<RelativePath> {
    RelativePath::new(format!("{}/{rest}", prefix.as_str())).ok()
}

impl Site {
    /// Admits the tree at `root` described by `manifest`, which must sit
    /// inside it. Only the manifest is read; the tree itself is not walked.
    pub fn open(root: &Path, manifest: &Path) -> Result<Self> {
        if !root.is_absolute() || manifest.parent() != Some(root) {
            return Err(refused(
                "documentation manifest must sit at an absolute docs root",
            ));
        }
        let bytes = match fs::read(manifest) {
            Ok(bytes) => bytes,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
                return Err(refused("the package carries no user documentation"));
            }
            Err(error) => return Err(unavailable().caused_by(error)),
        };
        let manifest: Manifest =
            serde_json::from_slice(&bytes).map_err(|e| unavailable().caused_by(e))?;
        let root = fs::canonicalize(root).map_err(|e| unavailable().caused_by(e))?;
        Self::admit(root, manifest)
    }

    fn admit(root: PathBuf, manifest: Manifest) -> Result<Self> {
        if manifest.schema != MANIFEST_SCHEMA {
            return Err(refused("unsupported documentation manifest schema"));
        }
        let declared: BTreeSet<&str> = manifest.languages.iter().map(String::as_str).collect();
        if declared.is_empty()
            || declared.len() != manifest.languages.len()
            || !manifest.languages.iter().all(|code| language_code(code))
            || !declared.contains(manifest.apex_language.as_str())
            || !manifest
                .entries
                .keys()
                .map(String::as_str)
                .eq(declared.iter().copied())
            || !manifest
                .stored
                .text
                .keys()
                .map(String::as_str)
                .eq(declared.iter().copied())
        {
            return Err(refused(
                "documentation languages disagree with their entries",
            ));
        }
        if !manifest.script_hashes.iter().all(|hash| script_hash(hash)) {
            return Err(refused("documentation script hash is malformed"));
        }
        if !manifest
            .stored
            .text
            .values()
            .all(|path| manifest.files.contains_key(path))
        {
            return Err(refused("a language's text is not in the inventory"));
        }
        let mut entries = manifest.entries;
        let ordered = manifest
            .languages
            .iter()
            .filter_map(|code| entries.remove(code).map(|entry| (code.clone(), entry)))
            .collect();
        let site = Self {
            root,
            files: manifest.files.into_keys().collect(),
            script_hashes: manifest.script_hashes,
            entries: ordered,
            search: manifest.search,
            apex_language: manifest.apex_language,
            languages: manifest.languages.into_iter().collect(),
            structure: manifest.stored.structure,
            language_files: manifest.stored.languages,
            pages: manifest.pages.into_iter().map(String::from).collect(),
            text: manifest
                .stored
                .text
                .into_iter()
                .map(|(code, file)| {
                    (
                        code,
                        Text {
                            file,
                            strings: OnceLock::new(),
                        },
                    )
                })
                .collect(),
        };
        if !site.pages.iter().all(|page| {
            joined(&site.structure, page).is_some_and(|path| site.files.contains(&path))
        }) {
            return Err(refused("a page's structure is not in the inventory"));
        }
        if !std::iter::once(&site.search)
            .chain(site.entries.iter().map(|(_, entry)| entry))
            .all(|address| site.resolve(address).is_some())
        {
            return Err(refused("documentation entry is not servable"));
        }
        Ok(site)
    }

    /// The canonical root every served file must resolve beneath.
    pub fn root(&self) -> &Path {
        &self.root
    }

    /// Where an address's bytes come from, in the order the addresses are
    /// defined: the language's own file, then its page, then the one copy
    /// every language shares. The stored directories are no addresses of
    /// their own, because a request for one asks for a site path that no
    /// page and no stored file answers.
    pub fn resolve<'a>(&'a self, path: &RelativePath) -> Option<Served<'a>> {
        let (language, site_path) = self.addressed(path);
        if let Some(own) = joined(&self.language_files, &format!("{language}/{site_path}"))
            .filter(|path| self.files.contains(path))
        {
            return Some(Served::File(own));
        }
        let structure = joined(&self.structure, site_path).filter(|p| self.files.contains(p))?;
        Some(if self.pages.contains(site_path) {
            Served::Page {
                structure,
                language,
            }
        } else {
            Served::File(structure)
        })
    }

    /// The language a request path belongs to and the path inside that
    /// language's site. The apex language's site is at the top, so a first
    /// segment naming it is a site path and not a language prefix.
    fn addressed<'a, 'p>(&'a self, path: &'p RelativePath) -> (&'a str, &'p str) {
        let raw = path.as_str();
        match raw.split_once('/') {
            Some((first, rest)) if first != self.apex_language => match self.languages.get(first) {
                Some(code) => (code.as_str(), rest),
                None => (&self.apex_language, raw),
            },
            _ => (&self.apex_language, raw),
        }
    }

    /// One language's strings, read once and kept: a text file is megabytes
    /// of JSON and every page of that language needs it. A file that cannot
    /// be read, is not JSON or is not a list of strings gives `None`, and
    /// that outcome is kept too, so a broken package is read once as well.
    pub fn text(&self, language: &str) -> Option<&[String]> {
        let text = self.text.get(language)?;
        text.strings
            .get_or_init(|| serde_json::from_slice(&read_contained(&self.root, &text.file)?).ok())
            .as_deref()
    }

    pub fn script_hashes(&self) -> &[String] {
        &self.script_hashes
    }

    pub fn entries(&self) -> &[(String, RelativePath)] {
        &self.entries
    }
}

fn language_code(code: &str) -> bool {
    (2..=3).contains(&code.len()) && code.bytes().all(|byte| byte.is_ascii_lowercase())
}

/// A CSP hash source body for SHA-256: `sha256-` and 44 base64 characters.
/// The value enters a response header, so nothing else is admitted.
pub(super) fn script_hash(value: &str) -> bool {
    let Some(encoded) = value.strip_prefix("sha256-") else {
        return false;
    };
    encoded.len() == 44
        && encoded.ends_with('=')
        && !encoded[..43].contains('=')
        && encoded[..43]
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || byte == b'+' || byte == b'/')
}
