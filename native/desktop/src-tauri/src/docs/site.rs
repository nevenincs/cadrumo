use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::{Path, PathBuf},
};

const MANIFEST_SCHEMA: u32 = 1;

/// The documentation manifest the packager writes beside the staged tree.
#[derive(Deserialize)]
struct Manifest {
    schema: u32,
    languages: Vec<String>,
    apex_language: String,
    entries: BTreeMap<String, RelativePath>,
    search: BTreeMap<String, RelativePath>,
    script_hashes: Vec<String>,
    files: BTreeMap<RelativePath, Sha256Digest>,
}

/// A documentation tree admitted for serving: its root and the manifest
/// inventory that decides which paths exist.
pub struct Site {
    root: PathBuf,
    files: BTreeSet<RelativePath>,
    script_hashes: Vec<String>,
    /// Each language's entry page, in the manifest's language order.
    entries: Vec<(String, RelativePath)>,
}

pub fn unavailable() -> ApplicationError {
    ApplicationError::new(ErrorCode::PackageUnavailable, Operation::Package)
}

fn refused(reason: &'static str) -> ApplicationError {
    unavailable().caused_by(std::io::Error::other(reason))
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
                .search
                .keys()
                .map(String::as_str)
                .eq(declared.iter().copied())
        {
            return Err(refused(
                "documentation languages disagree with their entries",
            ));
        }
        if !manifest
            .entries
            .values()
            .chain(manifest.search.values())
            .all(|path| manifest.files.contains_key(path))
        {
            return Err(refused("documentation entry is not in the inventory"));
        }
        if !manifest.script_hashes.iter().all(|hash| script_hash(hash)) {
            return Err(refused("documentation script hash is malformed"));
        }
        let mut entries = manifest.entries;
        let entries = manifest
            .languages
            .into_iter()
            .filter_map(|code| entries.remove(&code).map(|entry| (code, entry)))
            .collect();
        Ok(Self {
            root,
            files: manifest.files.into_keys().collect(),
            script_hashes: manifest.script_hashes,
            entries,
        })
    }

    /// The canonical root every served file must resolve beneath.
    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn contains(&self, path: &RelativePath) -> bool {
        self.files.contains(path)
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
