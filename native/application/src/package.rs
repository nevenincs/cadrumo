use crate::{
    error::Error,
    filesystem,
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use std::{collections::BTreeMap, fs, path::Path};

pub mod release;

/// Consumed fields of the assembler's existing manifest; no parallel file inventory.
#[derive(Debug, Deserialize)]
pub struct PackageManifest {
    pub layout: PackageLayout,
    pub python: String,
    pub distributions: BTreeMap<String, String>,
    pub files: BTreeMap<RelativePath, Sha256Digest>,
    /// Subtrees inventoried by a hashed member manifest instead of listing each file here.
    #[serde(default)]
    pub delegated_inventories: BTreeMap<RelativePath, RelativePath>,
    /// The assembler's statement of whether the user documentation tree ships.
    pub user_docs: Option<UserDocsStatement>,
}

#[derive(Debug, Deserialize)]
pub struct UserDocsStatement {
    pub directory: RelativePath,
    pub bundled: bool,
}

#[derive(Debug, Deserialize)]
struct DelegatedInventory {
    files: BTreeMap<RelativePath, Sha256Digest>,
}

#[derive(Debug, Deserialize)]
pub struct PackageLayout {
    pub abi: u32,
    pub platform: String,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum Readiness {
    Ready,
    Missing(String),
    Incompatible(String),
    NeedsUser(String),
}

#[derive(Debug)]
pub struct PackageInspection {
    pub manifest: PackageManifest,
    pub readiness: Readiness,
}

impl PackageManifest {
    pub fn read(root: &Path, manifest: &RelativePath) -> Result<Self, Error> {
        filesystem::absolute_root(root)?;
        filesystem::json_file(&manifest.under(root))
    }

    /// Expected platform spelling is projected by the caller; aliases are not guessed.
    pub fn inspect(
        self,
        root: &Path,
        manifest_path: &RelativePath,
        platform: &str,
        abi: u32,
    ) -> Result<PackageInspection, Error> {
        filesystem::absolute_root(root)?;
        let readiness = if self.layout.platform != platform || self.layout.abi != abi {
            Readiness::Incompatible("package target or ABI differs".into())
        } else {
            self.check_files(root, manifest_path)?
        };
        Ok(PackageInspection {
            manifest: self,
            readiness,
        })
    }

    fn check_files(&self, root: &Path, manifest_path: &RelativePath) -> Result<Readiness, Error> {
        if self.files.is_empty() || self.files.contains_key(manifest_path) {
            return Err(Error::Invalid("invalid package file inventory".into()));
        }
        // Documentation may be absent only because the manifest says so.
        let Some(docs) = &self.user_docs else {
            return Err(Error::Invalid(
                "package manifest does not state whether user documentation is bundled; rebuild the package"
                    .into(),
            ));
        };
        let prefix = format!("{}/", docs.directory.as_str());
        if docs.bundled != self.delegated_inventories.contains_key(&docs.directory)
            || (!docs.bundled
                && self
                    .files
                    .keys()
                    .any(|name| name.as_str().starts_with(&prefix)))
        {
            return Err(Error::Invalid(
                "package documentation statement disagrees with its inventory".into(),
            ));
        }
        for (relative, expected) in &self.files {
            if let Some(readiness) = check_file(root, relative, expected)? {
                return Ok(readiness);
            }
        }
        // Each delegated manifest was hash-checked above as a listed file before it is trusted.
        let mut inventory = self.files.clone();
        for (prefix, member) in &self.delegated_inventories {
            if !self.files.contains_key(member)
                || !member
                    .as_str()
                    .starts_with(&format!("{}/", prefix.as_str()))
            {
                return Err(Error::Invalid(
                    "delegated inventory must be a listed file beneath its prefix".into(),
                ));
            }
            let nested: DelegatedInventory = filesystem::json_file(&member.under(root))?;
            for (relative, expected) in nested.files {
                let joined =
                    RelativePath::new(format!("{}/{}", prefix.as_str(), relative.as_str()))?;
                if inventory.contains_key(&joined) {
                    return Err(Error::Invalid(format!(
                        "delegated inventory entry collides with a package file: {}",
                        joined.as_str()
                    )));
                }
                if let Some(readiness) = check_file(root, &joined, &expected)? {
                    return Ok(readiness);
                }
                inventory.insert(joined, expected);
            }
        }
        let mut pending = vec![root.to_path_buf()];
        while let Some(directory) = pending.pop() {
            for entry in fs::read_dir(directory)? {
                let path = entry?.path();
                filesystem::refuse_links(&path)?;
                if path.is_dir() {
                    pending.push(path);
                    continue;
                }
                let relative = path
                    .strip_prefix(root)
                    .map_err(|_| Error::Invalid("package path escaped".into()))?;
                let relative = RelativePath::from_native(relative)?;
                if relative != *manifest_path && !inventory.contains_key(&relative) {
                    return Ok(Readiness::Incompatible(format!(
                        "unexpected file: {}",
                        relative.as_str()
                    )));
                }
            }
        }
        Ok(Readiness::Ready)
    }
}

fn check_file(
    root: &Path,
    relative: &RelativePath,
    expected: &Sha256Digest,
) -> Result<Option<Readiness>, Error> {
    let path = relative.under(root);
    filesystem::refuse_links(&path)?;
    match fs::metadata(&path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Some(Readiness::Missing(relative.as_str().into())));
        }
        Err(e) => return Err(e.into()),
        Ok(meta) if !meta.is_file() => {
            return Ok(Some(Readiness::Incompatible(relative.as_str().into())));
        }
        Ok(_) => {}
    }
    if filesystem::digest(&path)? != *expected {
        return Ok(Some(Readiness::Incompatible(relative.as_str().into())));
    }
    Ok(None)
}
