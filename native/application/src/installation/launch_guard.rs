//! Exact-package process admission shares the native publication lock owner.
use super::{DiscoveryContract, LaunchPolicy, Marker, VersionManifest, maintenance, version};
use crate::{component::Cancellation, error::Error, filesystem};
use std::{fs, path::Path, sync::Arc};

impl DiscoveryContract {
    /// Retain this lease through the process lifetime, independently of its parent.
    /// This grants removal exclusion only: existing package-integrity, peer and
    /// runtime admission checks still apply. No newer package is ever selected.
    pub fn acquire_package(
        &self,
        package: &Path,
    ) -> Result<Option<Arc<maintenance::Lease>>, Error> {
        filesystem::absolute_root(package)?;
        #[cfg(windows)]
        if package.components().any(|component| match component {
            std::path::Component::Normal(name) => name.to_string_lossy().ends_with(['.', ' ']),
            _ => false,
        }) {
            return Err(Error::Invalid(
                "noncanonical Windows package spelling".into(),
            ));
        }
        if !fs::metadata(package)?.is_dir() {
            return Err(Error::Invalid("package root is not a directory".into()));
        }
        let components = Path::new(self.layout.installation.versions.as_str())
            .components()
            .count();
        for candidate in package.ancestors() {
            let Some(versions) = candidate.parent() else {
                continue;
            };
            let Some(prefix) = versions.ancestors().nth(components) else {
                continue;
            };
            if !same_path(&self.layout.installation.versions.under(prefix), versions) {
                continue;
            }
            if candidate != package {
                return Err(Error::Invalid(
                    "package is nested beneath an installed version".into(),
                ));
            }
            let release = package
                .file_name()
                .and_then(|name| name.to_str())
                .ok_or_else(|| Error::Invalid("installed version is not UTF-8".into()))?;
            version(release)?;
            return self.acquire_installed_package(prefix, package, release);
        }
        // A package presented as the installation root is not a portable fallback.
        match fs::symlink_metadata(self.layout.installation.marker.under(package)) {
            Ok(_) => Err(Error::Invalid(
                "installation root is not a versioned package".into(),
            )),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(error) => Err(error.into()),
        }
    }

    fn acquire_installed_package(
        &self,
        prefix: &Path,
        package: &Path,
        release: &str,
    ) -> Result<Option<Arc<maintenance::Lease>>, Error> {
        filesystem::absolute_root(prefix)?;
        let marker: Marker = filesystem::json_file(&self.layout.installation.marker.under(prefix))?;
        if marker.schema != self.layout.installation.schema
            || marker.application_id != self.installation_identity.application_id
            || marker.channel != self.installation_identity.channel
            || marker.platform != self.layout.platform
            || marker.abi != self.layout.abi
        {
            return Err(Error::Incompatible("installation identity differs".into()));
        }
        if marker.launch_policy == Some(LaunchPolicy::Portable) && marker.publication.is_none() {
            if let Some(publication) = self.layout.installation.publication.as_ref() {
                match fs::symlink_metadata(publication.under(prefix)) {
                    Ok(_) => {
                        return Err(Error::Integrity(
                            "portable policy conflicts with native publication".into(),
                        ));
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
                    Err(error) => return Err(error.into()),
                }
            }
            return Ok(None);
        }
        if marker.launch_policy != Some(LaunchPolicy::Native) {
            return Err(Error::Integrity(
                "installed package requires explicit launch policy".into(),
            ));
        }
        let publication = marker
            .publication
            .as_ref()
            .filter(|path| Some(*path) == self.layout.installation.publication.as_ref())
            .ok_or_else(|| {
                Error::Integrity("installed package requires declared publication".into())
            })?;
        let bytes = filesystem::json_bytes(&self.layout.files.package_manifest.under(package))?;
        let manifest: VersionManifest = serde_json::from_slice(&bytes)?;
        let target = if self.layout.platform == "windows-x64" {
            "windows-x86-64"
        } else {
            &self.layout.platform
        };
        if manifest.build.application_id != self.installation_identity.application_id
            || manifest.build.channel != self.installation_identity.channel
            || manifest.build.version != release
            || manifest.build.target != target
            || manifest.package.layout.platform != self.layout.platform
            || manifest.package.layout.abi != self.layout.abi
        {
            return Err(Error::Incompatible("own package identity differs".into()));
        }
        let digest = filesystem::digest_reader(&mut bytes.as_slice(), &Cancellation::default())?;
        let store = maintenance::Store::new(
            publication.under(prefix),
            maintenance::Identity {
                application_id: marker.application_id,
                channel: marker.channel,
                platform: marker.platform,
            },
            self.layout.installation.maximum_versions,
        )?;
        let lease = store.acquire(release, &digest)?;
        let snapshot = store.snapshot()?;
        let owner = snapshot
            .versions()
            .find(|(name, _)| *name == release)
            .map(|(_, product)| &product.owner)
            .ok_or_else(|| Error::Integrity("own version publication disappeared".into()))?;
        if !same_path(owner.prefix(), prefix) {
            return Err(Error::Integrity(
                "native owner prefix differs from own package".into(),
            ));
        }
        Ok(Some(Arc::new(lease)))
    }
}

fn same_path(expected: &Path, actual: &Path) -> bool {
    #[cfg(windows)]
    {
        let mut left = expected.components();
        let mut right = actual.components();
        loop {
            match (left.next(), right.next()) {
                (None, None) => return true,
                (Some(a), Some(b)) if a == b => {}
                (Some(a), Some(b))
                    if a.as_os_str()
                        .to_str()
                        .zip(b.as_os_str().to_str())
                        .is_some_and(|(a, b)| a.eq_ignore_ascii_case(b)) => {}
                _ => return false,
            }
        }
    }
    #[cfg(not(windows))]
    {
        expected == actual
    }
}
