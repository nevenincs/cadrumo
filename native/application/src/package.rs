use crate::{
    component::Cancellation,
    error::Error,
    filesystem,
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs::{self, File},
    io::Read,
    path::Path,
};

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
        Self::read_cancellable(root, manifest, &Cancellation::default())
    }

    pub fn read_cancellable(
        root: &Path,
        manifest: &RelativePath,
        cancellation: &Cancellation,
    ) -> Result<Self, Error> {
        cancellation.check()?;
        filesystem::absolute_root(root)?;
        filesystem::json_file_cancellable(&manifest.under(root), cancellation)
    }

    /// Expected platform spelling is projected by the caller; aliases are not guessed.
    pub fn inspect(
        self,
        root: &Path,
        manifest_path: &RelativePath,
        platform: &str,
        abi: u32,
    ) -> Result<PackageInspection, Error> {
        self.inspect_cancellable(root, manifest_path, platform, abi, &Cancellation::default())
    }

    /// Cooperative cancellation between entries and stream chunks; filesystem calls
    /// themselves remain synchronous and are not forcibly interruptible.
    pub fn inspect_cancellable(
        self,
        root: &Path,
        manifest_path: &RelativePath,
        platform: &str,
        abi: u32,
        cancellation: &Cancellation,
    ) -> Result<PackageInspection, Error> {
        cancellation.check()?;
        filesystem::absolute_root(root)?;
        let readiness = if self.layout.platform != platform || self.layout.abi != abi {
            Readiness::Incompatible("package target or ABI differs".into())
        } else {
            self.check_files(root, manifest_path, cancellation)?
        };
        cancellation.check()?;
        Ok(PackageInspection {
            manifest: self,
            readiness,
        })
    }

    fn check_files(
        &self,
        root: &Path,
        manifest_path: &RelativePath,
        cancellation: &Cancellation,
    ) -> Result<Readiness, Error> {
        cancellation.check()?;
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
        let mut inventory = self.files.clone();
        let mut admitted_manifests = BTreeMap::new();
        for (prefix, member) in &self.delegated_inventories {
            cancellation.check()?;
            if !self.files.contains_key(member)
                || !member
                    .as_str()
                    .starts_with(&format!("{}/", prefix.as_str()))
            {
                return Err(Error::Invalid(
                    "delegated inventory must be a listed file beneath its prefix".into(),
                ));
            }
            let expected = &self.files[member];
            // The same bounded, digest-verified bytes supply the nested inventory.
            // Only this small set needs a path walk before the tree is traversed.
            let nested = match read_delegated(root, member, expected, cancellation)? {
                Admission::Admitted(nested) => nested,
                Admission::Refused(readiness) => return Ok(readiness),
            };
            admitted_manifests.insert(member.clone(), expected.clone());
            for (relative, expected) in nested.files {
                cancellation.check()?;
                let joined =
                    RelativePath::new(format!("{}/{}", prefix.as_str(), relative.as_str()))?;
                if inventory.contains_key(&joined) {
                    return Err(Error::Invalid(format!(
                        "delegated inventory entry collides with a package file: {}",
                        joined.as_str()
                    )));
                }
                inventory.insert(joined, expected);
            }
        }
        let mut pending = vec![root.to_path_buf()];
        while let Some(directory) = pending.pop() {
            cancellation.check()?;
            for entry in fs::read_dir(directory)? {
                cancellation.check()?;
                let path = entry?.path();
                // Ancestors were admitted when entering the root and each
                // descended directory. Check this entry without following it.
                let metadata = fs::symlink_metadata(&path)?;
                filesystem::refuse_metadata_links(&metadata)?;
                let relative = path
                    .strip_prefix(root)
                    .map_err(|_| Error::Invalid("package path escaped".into()))?;
                if metadata.is_dir() {
                    // Directories need not be inventoried. A nonportable name
                    // cannot match an inventoried regular file; keep descending
                    // as before, with strict relative-path checks on every leaf.
                    if let Ok(relative) = RelativePath::from_native(relative)
                        && inventory.contains_key(&relative)
                    {
                        return Ok(Readiness::Incompatible(relative.as_str().into()));
                    }
                    pending.push(path);
                    continue;
                }
                let relative = RelativePath::from_native(relative)?;
                let Some(expected) = inventory.remove(&relative) else {
                    if relative == *manifest_path && metadata.is_file() {
                        continue;
                    }
                    return Ok(Readiness::Incompatible(format!(
                        "unexpected file: {}",
                        relative.as_str()
                    )));
                };
                if !metadata.is_file() {
                    return Ok(Readiness::Incompatible(relative.as_str().into()));
                }
                // Delegated bytes were already hashed before expansion. They
                // still pass this traversal's own-entry link and type checks.
                if admitted_manifests.get(&relative) == Some(&expected) {
                    continue;
                }
                let mut file = match open_regular(&path, &relative)? {
                    Admission::Admitted(file) => file,
                    Admission::Refused(readiness) => return Ok(readiness),
                };
                if filesystem::digest_reader(&mut file, cancellation)? != expected {
                    return Ok(Readiness::Incompatible(relative.as_str().into()));
                }
            }
        }
        if let Some((missing, _)) = inventory.into_iter().next() {
            return Ok(Readiness::Missing(missing.as_str().into()));
        }
        Ok(Readiness::Ready)
    }
}

enum Admission<T> {
    Admitted(T),
    Refused(Readiness),
}

fn open_regular(path: &Path, member: &RelativePath) -> Result<Admission<File>, Error> {
    let file = match File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Admission::Refused(Readiness::Missing(
                member.as_str().into(),
            )));
        }
        Err(error) => return Err(error.into()),
    };
    if !file.metadata()?.is_file() {
        return Ok(Admission::Refused(Readiness::Incompatible(
            member.as_str().into(),
        )));
    }
    Ok(Admission::Admitted(file))
}

fn read_delegated(
    root: &Path,
    member: &RelativePath,
    expected: &Sha256Digest,
    cancellation: &Cancellation,
) -> Result<Admission<DelegatedInventory>, Error> {
    cancellation.check()?;
    let path = member.under(root);
    filesystem::refuse_links(&path)?;
    match fs::symlink_metadata(&path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            return Ok(Admission::Refused(Readiness::Missing(
                member.as_str().into(),
            )));
        }
        Err(e) => return Err(e.into()),
        Ok(meta) if !meta.is_file() => {
            return Ok(Admission::Refused(Readiness::Incompatible(
                member.as_str().into(),
            )));
        }
        Ok(meta) => filesystem::refuse_metadata_links(&meta)?,
    }
    let file = match open_regular(&path, member)? {
        Admission::Admitted(file) => file,
        Admission::Refused(readiness) => return Ok(Admission::Refused(readiness)),
    };
    let mut bytes = Vec::new();
    cancellation.check()?;
    let read = file
        .take(filesystem::JSON_BYTES_LIMIT + 1)
        .read_to_end(&mut bytes);
    cancellation.check()?;
    read?;
    if bytes.len() as u64 > filesystem::JSON_BYTES_LIMIT {
        return Err(Error::LimitExceeded);
    }
    let actual = Sha256Digest::new(format!("{:x}", Sha256::digest(&bytes)))?;
    cancellation.check()?;
    if actual != *expected {
        return Ok(Admission::Refused(Readiness::Incompatible(
            member.as_str().into(),
        )));
    }
    let nested = serde_json::from_slice(&bytes);
    cancellation.check()?;
    Ok(Admission::Admitted(nested?))
}
