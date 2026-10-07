//! Read-only discovery of complete immutable versions beneath an explicit install prefix.
//! Metadata and hashes establish package consistency, not publisher authenticity.
use crate::{
    binary::{self, BinaryExpectation},
    error::Error,
    filesystem,
    package::{PackageManifest, Readiness},
    value::RelativePath,
};
use serde::Deserialize;
use std::{
    fs,
    path::{Path, PathBuf},
};

#[derive(Deserialize)]
pub struct DiscoveryContract {
    pub layout: Layout,
    pub installation_identity: Identity,
}
#[derive(Deserialize)]
pub struct Identity {
    pub application_id: String,
    pub channel: String,
}
#[derive(Deserialize)]
pub struct Layout {
    pub abi: u32,
    pub platform: String,
    pub installation: Installation,
    pub files: Files,
    pub application_images: Vec<Image>,
    pub entrypoint_suffix: String,
}
#[derive(Deserialize)]
pub struct Installation {
    pub schema: u32,
    pub marker: RelativePath,
    pub versions: RelativePath,
    pub maximum_versions: usize,
}
#[derive(Deserialize)]
pub struct Files {
    pub package_manifest: RelativePath,
}
#[derive(Deserialize)]
pub struct Image {
    pub name: String,
    pub placement: String,
    pub target: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Marker {
    schema: u32,
    application_id: String,
    channel: String,
    platform: String,
    abi: u32,
}
#[derive(Deserialize)]
struct VersionManifest {
    build: Build,
    #[serde(flatten)]
    package: PackageManifest,
}
#[derive(Deserialize)]
struct Build {
    application_id: String,
    version: String,
    channel: String,
    target: String,
}

#[derive(Clone, Debug)]
pub struct Selection {
    pub entrypoint: PathBuf,
    pub package: PathBuf,
    pub manager: PathBuf,
    pub version: [u32; 3],
}

/// Distribution identity permits only a canonical numeric release triple.
pub fn version(value: &str) -> Result<[u32; 3], Error> {
    let parts: Vec<_> = value.split('.').collect();
    if parts.len() != 3
        || parts.iter().any(|p| {
            p.is_empty()
                || !p.bytes().all(|c| c.is_ascii_digit())
                || (p.len() > 1 && p.starts_with('0'))
        })
    {
        return Err(Error::Invalid("noncanonical installed version".into()));
    }
    let mut result = [0; 3];
    for (slot, part) in result.iter_mut().zip(parts) {
        *slot = part
            .parse()
            .map_err(|_| Error::Invalid("installed version overflows".into()))?;
    }
    Ok(result)
}

impl DiscoveryContract {
    pub fn manager_member(&self) -> Result<RelativePath, Error> {
        let mut images = self
            .layout
            .application_images
            .iter()
            .filter(|image| image.target == "rust_manager");
        let image = images
            .next()
            .ok_or_else(|| Error::Invalid("manager image is not declared".into()))?;
        if images.next().is_some() || image.placement != "." {
            return Err(Error::Invalid("manager must be a unique root image".into()));
        }
        let member = RelativePath::new(format!("{}{}", image.name, self.layout.entrypoint_suffix))?;
        if member.as_str().contains('/') {
            return Err(Error::Invalid("manager image is not root-level".into()));
        }
        Ok(member)
    }

    /// A package contributes only its structurally declared versioned prefix.
    /// A stable entry image contributes its own directory. No cwd or sibling guessing.
    pub fn local_prefix(&self, image: &Path) -> Option<PathBuf> {
        let directory = image.parent()?;
        if self.layout.installation.marker.under(directory).is_file() {
            return Some(directory.to_path_buf());
        }
        version(directory.file_name()?.to_str()?).ok()?;
        let versions = directory.parent()?;
        let prefix = versions.parent()?;
        (self.layout.installation.versions.under(prefix) == versions).then(|| prefix.to_path_buf())
    }

    /// Registered entry points are hints; every prefix, complete package and executable
    /// is verified before it can be returned. The newest compatible complete version wins.
    pub fn discover(&self, image: &Path, registered: &[PathBuf]) -> Result<Selection, Error> {
        let member = self.manager_member()?;
        let mut prefixes: Vec<PathBuf> = self.local_prefix(image).into_iter().collect();
        for entry in registered {
            if entry.file_name() == Some(Path::new(member.as_str()).as_os_str())
                && let Some(prefix) = entry.parent()
                && !prefixes.iter().any(|p| p == prefix)
            {
                prefixes.push(prefix.to_path_buf());
            }
        }
        let mut newest: Option<Selection> = None;
        for prefix in prefixes {
            if let Ok(candidate) = self.inspect(&prefix)
                && newest
                    .as_ref()
                    .is_none_or(|old| candidate.version > old.version)
            {
                newest = Some(candidate);
            }
        }
        newest.ok_or_else(|| {
            Error::Incompatible("no complete compatible manager installation".into())
        })
    }

    pub fn inspect(&self, prefix: &Path) -> Result<Selection, Error> {
        filesystem::absolute_root(prefix)?;
        let layout = &self.layout;
        let marker: Marker = filesystem::json_file(&layout.installation.marker.under(prefix))?;
        if marker.schema != layout.installation.schema
            || marker.application_id != self.installation_identity.application_id
            || marker.channel != self.installation_identity.channel
            || marker.platform != layout.platform
            || marker.abi != layout.abi
        {
            return Err(Error::Incompatible("installation identity differs".into()));
        }
        let versions = layout.installation.versions.under(prefix);
        filesystem::absolute_root(&versions)?;
        let member = self.manager_member()?;
        let entrypoint = member.under(prefix);
        let expected = BinaryExpectation::host()?;
        let mut newest: Option<Selection> = None;
        let mut entry_verified = false;
        for (count, entry) in fs::read_dir(&versions)?.enumerate() {
            if count >= layout.installation.maximum_versions {
                return Err(Error::LimitExceeded);
            }
            let entry = entry?;
            let Some(name) = entry.file_name().to_str().map(str::to_owned) else {
                continue;
            };
            let Ok(number) = version(&name) else { continue };
            let package = entry.path();
            let inspect = || -> Result<_, Error> {
                filesystem::absolute_root(&package)?;
                let manifest: VersionManifest =
                    filesystem::json_file(&layout.files.package_manifest.under(&package))?;
                let target = if layout.platform == "windows-x64" {
                    "windows-x86-64"
                } else {
                    &layout.platform
                };
                if manifest.build.application_id != marker.application_id
                    || manifest.build.channel != marker.channel
                    || manifest.build.version != name
                    || manifest.build.target != target
                {
                    return Err(Error::Incompatible("version identity differs".into()));
                }
                let inspected = manifest.package.inspect(
                    &package,
                    &layout.files.package_manifest,
                    &layout.platform,
                    layout.abi,
                )?;
                if inspected.readiness != Readiness::Ready {
                    return Err(Error::Integrity("incomplete installed version".into()));
                }
                let digest = inspected
                    .manifest
                    .files
                    .get(&member)
                    .ok_or_else(|| Error::Invalid("manager absent from inventory".into()))?
                    .clone();
                let manager = member.under(&package);
                binary::verify(&manager, &digest, expected)?;
                Ok((manager, digest))
            };
            let Ok((manager, digest)) = inspect() else {
                continue;
            };
            // A stable entry can still contain an older manager's bytes. It must match
            // a complete version; its startup redirects before claiming runtime ownership.
            if !entry_verified {
                entry_verified = binary::verify(&entrypoint, &digest, expected).is_ok();
            }
            if newest.as_ref().is_none_or(|old| number > old.version) {
                newest = Some(Selection {
                    entrypoint: entrypoint.clone(),
                    package,
                    manager,
                    version: number,
                });
            }
        }
        if !entry_verified {
            return Err(Error::Integrity(
                "stable manager entry point is missing or modified".into(),
            ));
        }
        newest.ok_or_else(|| Error::Incompatible("no complete compatible installed version".into()))
    }
}
