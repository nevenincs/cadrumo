use crate::{
    error::Error,
    filesystem,
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use std::{collections::BTreeMap, fs, path::Path};

/// Consumed fields of the assembler's existing manifest; no parallel file inventory.
#[derive(Debug, Deserialize)]
pub struct PackageManifest {
    pub layout: PackageLayout,
    pub python: String,
    pub distributions: BTreeMap<String, String>,
    pub files: BTreeMap<RelativePath, Sha256Digest>,
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
        for (relative, expected) in &self.files {
            let path = relative.under(root);
            filesystem::refuse_links(&path)?;
            match fs::metadata(&path) {
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                    return Ok(Readiness::Missing(relative.as_str().into()));
                }
                Err(e) => return Err(e.into()),
                Ok(meta) if !meta.is_file() => {
                    return Ok(Readiness::Incompatible(relative.as_str().into()));
                }
                Ok(_) => {}
            }
            if filesystem::digest(&path)? != *expected {
                return Ok(Readiness::Incompatible(relative.as_str().into()));
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
                if relative != *manifest_path && !self.files.contains_key(&relative) {
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
