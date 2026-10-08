//! Read-only discovery of complete immutable versions beneath an explicit install prefix.
//! Metadata and hashes establish package consistency, not publisher authenticity.
pub mod maintenance;
use crate::{
    binary::{self, BinaryExpectation},
    component::Cancellation,
    error::Error,
    filesystem,
    package::{PackageManifest, Readiness},
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use std::{
    fs,
    path::{Path, PathBuf},
    sync::Arc,
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
    #[serde(default)]
    pub publication: Option<RelativePath>,
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
    #[serde(default)]
    publication: Option<RelativePath>,
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
    pub lease: Option<Arc<maintenance::Lease>>,
}

/// Scoped native registrations are hints, verified through the same package catalogue.
#[derive(Default)]
pub struct RegistrationHints<'a> {
    pub this_user: Option<&'a Path>,
    pub all_users: Option<&'a Path>,
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
    /// is verified before it can be returned. A complete this-user registration wins
    /// before version comparison across the local and all-users fallback prefixes.
    pub fn discover(
        &self,
        image: &Path,
        registered: &RegistrationHints<'_>,
    ) -> Result<Selection, Error> {
        self.discover_cancellable(image, registered, &Cancellation::default())
    }

    /// Cancellation is fatal through prefix and version fallback, not a damaged candidate.
    pub fn discover_cancellable(
        &self,
        image: &Path,
        registered: &RegistrationHints<'_>,
        cancellation: &Cancellation,
    ) -> Result<Selection, Error> {
        cancellation.check()?;
        let member = self.manager_member()?;
        let mut prefixes: Vec<(PathBuf, bool)> = self
            .local_prefix(image)
            .into_iter()
            .map(|prefix| (prefix, false))
            .collect();
        for (hint, this_user) in [(registered.this_user, true), (registered.all_users, false)] {
            cancellation.check()?;
            let Some(entry) = hint else { continue };
            if entry.file_name() == Some(Path::new(member.as_str()).as_os_str())
                && let Some(prefix) = entry.parent()
            {
                if let Some((_, preferred)) = prefixes.iter_mut().find(|(p, _)| p == prefix) {
                    *preferred |= this_user;
                } else {
                    prefixes.push((prefix.to_path_buf(), this_user));
                }
            }
        }
        let mut preferred: Option<Selection> = None;
        let mut newest: Option<Selection> = None;
        for (prefix, this_user) in prefixes {
            cancellation.check()?;
            let inspected = self.inspect_cancellable(&prefix, cancellation);
            cancellation.check()?;
            if matches!(inspected, Err(Error::Cancelled)) {
                return Err(Error::Cancelled);
            }
            if let Ok(candidate) = inspected {
                let winner = if this_user {
                    &mut preferred
                } else {
                    &mut newest
                };
                if winner
                    .as_ref()
                    .is_none_or(|old| candidate.version > old.version)
                {
                    *winner = Some(candidate);
                }
            }
        }
        cancellation.check()?;
        preferred.or(newest).ok_or_else(|| {
            Error::Incompatible("no complete compatible manager installation".into())
        })
    }

    pub fn inspect(&self, prefix: &Path) -> Result<Selection, Error> {
        self.inspect_cancellable(prefix, &Cancellation::default())
    }

    pub fn inspect_cancellable(
        &self,
        prefix: &Path,
        cancellation: &Cancellation,
    ) -> Result<Selection, Error> {
        cancellation.check()?;
        filesystem::absolute_root(prefix)?;
        let layout = &self.layout;
        let marker: Marker = filesystem::json_file_cancellable(
            &layout.installation.marker.under(prefix),
            cancellation,
        )?;
        if marker.schema != layout.installation.schema
            || marker.application_id != self.installation_identity.application_id
            || marker.channel != self.installation_identity.channel
            || marker.platform != layout.platform
            || marker.abi != layout.abi
        {
            return Err(Error::Incompatible("installation identity differs".into()));
        }
        let versions = layout.installation.versions.under(prefix);
        let publication = match marker.publication.as_ref() {
            Some(path) if Some(path) == layout.installation.publication.as_ref() => {
                Some(maintenance::Store::new(
                    path.under(prefix),
                    maintenance::Identity {
                        application_id: marker.application_id.clone(),
                        channel: marker.channel.clone(),
                        platform: marker.platform.clone(),
                    },
                    layout.installation.maximum_versions,
                )?)
            }
            Some(_) => {
                return Err(Error::Invalid(
                    "undeclared installation publication path".into(),
                ));
            }
            None => None,
        };
        filesystem::absolute_root(&versions)?;
        let member = self.manager_member()?;
        let entrypoint = member.under(prefix);
        let expected = BinaryExpectation::host()?;
        let mut newest: Option<Selection> = None;
        let mut entry_verified = false;
        let mut candidates = Vec::new();
        for (count, entry) in fs::read_dir(&versions)?.enumerate() {
            cancellation.check()?;
            if count >= layout.installation.maximum_versions {
                return Err(Error::LimitExceeded);
            }
            let entry = entry?;
            let Some(name) = entry.file_name().to_str().map(str::to_owned) else {
                continue;
            };
            let Ok(number) = version(&name) else { continue };
            candidates.push((number, name, entry.path()));
        }
        // Enumeration is bounded before selection: invalid names and entries after
        // a ready candidate still count toward the installation's version limit.
        candidates.sort_unstable_by_key(|candidate| std::cmp::Reverse(candidate.0));
        for (number, name, package) in candidates {
            cancellation.check()?;
            let inspect = || -> Result<_, Error> {
                let lease = publication
                    .as_ref()
                    .map(|store| {
                        let manifest = self.manifest_digest(&package, cancellation)?;
                        store.acquire(&name, &manifest).map(Arc::new)
                    })
                    .transpose()?;
                let (manager, digest) = self.inspect_package(&package, &name, cancellation)?;
                Ok((manager, digest, lease))
            };
            let inspected = inspect();
            cancellation.check()?;
            if matches!(inspected, Err(Error::Cancelled)) {
                return Err(Error::Cancelled);
            }
            let Ok((manager, digest, lease)) = inspected else {
                continue;
            };
            // A stable entry can still contain an older manager's bytes. It must match
            // a complete version; its startup redirects before claiming runtime ownership.
            if !entry_verified {
                cancellation.check()?;
                entry_verified = binary::verify(&entrypoint, &digest, expected).is_ok();
                cancellation.check()?;
            }
            if newest.is_none() {
                newest = Some(Selection {
                    entrypoint: entrypoint.clone(),
                    package,
                    manager,
                    version: number,
                    lease,
                });
            }
            if newest.is_some() && entry_verified {
                break;
            }
        }
        if !entry_verified {
            cancellation.check()?;
            return Err(Error::Integrity(
                "stable manager entry point is missing or modified".into(),
            ));
        }
        cancellation.check()?;
        newest.ok_or_else(|| Error::Incompatible("no complete compatible installed version".into()))
    }

    pub(crate) fn manifest_digest(
        &self,
        package: &Path,
        cancellation: &Cancellation,
    ) -> Result<Sha256Digest, Error> {
        cancellation.check()?;
        let bytes = filesystem::json_bytes(&self.layout.files.package_manifest.under(package))?;
        filesystem::digest_reader(&mut bytes.as_slice(), cancellation)
    }

    pub(crate) fn inspect_package(
        &self,
        package: &Path,
        name: &str,
        cancellation: &Cancellation,
    ) -> Result<(PathBuf, Sha256Digest), Error> {
        filesystem::absolute_root(package)?;
        let layout = &self.layout;
        let manifest: VersionManifest = filesystem::json_file_cancellable(
            &layout.files.package_manifest.under(package),
            cancellation,
        )?;
        let target = if layout.platform == "windows-x64" {
            "windows-x86-64"
        } else {
            &layout.platform
        };
        if manifest.build.application_id != self.installation_identity.application_id
            || manifest.build.channel != self.installation_identity.channel
            || manifest.build.version != name
            || manifest.build.target != target
        {
            return Err(Error::Incompatible("version identity differs".into()));
        }
        let inspected = manifest.package.inspect_cancellable(
            package,
            &layout.files.package_manifest,
            &layout.platform,
            layout.abi,
            cancellation,
        )?;
        if inspected.readiness != Readiness::Ready {
            return Err(Error::Integrity("incomplete installed version".into()));
        }
        let member = self.manager_member()?;
        let digest = inspected
            .manifest
            .files
            .get(&member)
            .ok_or_else(|| Error::Invalid("manager absent from inventory".into()))?
            .clone();
        let manager = member.under(package);
        cancellation.check()?;
        binary::verify(&manager, &digest, BinaryExpectation::host()?)?;
        cancellation.check()?;
        Ok((manager, digest))
    }
}
