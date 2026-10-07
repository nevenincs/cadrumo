//! Admission of the package selected by this manager image.

use crate::supervision::{
    adoption::{InstalledVersion, InstalledVersions},
    environment::{ManagedLocations, runtime_environment},
    launch::{LaunchTarget, runtime_image},
    supervisor::VersionProbe,
};
use cadrumo_application::{
    child::ChildConfiguration,
    package::{PackageManifest, Readiness},
    runtime,
    value::RelativePath,
};
use std::{io, path::Path, time::Duration};

#[derive(Clone)]
pub struct InstalledRuntime {
    pub target: LaunchTarget,
    query: ChildConfiguration,
    version: InstalledVersion,
}

impl InstalledRuntime {
    pub fn inspect(locations: &ManagedLocations) -> io::Result<Self> {
        let package = locations.package_root();
        if failed_version_marker(locations.storage_root()) {
            return Err(io::Error::other(
                "manager_failed_version_requires_catalogue",
            ));
        }
        let manifest_path =
            RelativePath::new(crate::contract::MODE_PACKAGE_MANIFEST).map_err(io::Error::other)?;
        let manifest = PackageManifest::read(package, &manifest_path).map_err(io::Error::other)?;
        let platform = if cfg!(all(windows, target_arch = "x86_64")) {
            "windows-x64"
        } else {
            return Err(io::ErrorKind::Unsupported.into());
        };
        let inspection = manifest
            .inspect(package, &manifest_path, platform, crate::contract::ABI)
            .map_err(io::Error::other)?;
        if inspection.readiness != Readiness::Ready {
            return Err(io::Error::other("manager_package_incomplete"));
        }
        let query = ChildConfiguration::new(
            package.join(crate::contract::EXECUTABLE),
            package.to_path_buf(),
            runtime_environment(locations.storage_root(), Some(package), std::env::vars_os())?
                .into_iter()
                .collect(),
        )
        .map_err(io::Error::other)?;
        let identity = probe(&query)?;
        if !same_directory(&identity.storage, locations.storage_root())
            || identity.version != crate::identity::VERSION
        {
            return Err(io::Error::other("manager_runtime_identity_mismatch"));
        }
        let target = LaunchTarget::installed(
            locations,
            identity.storage_identity,
            identity.version.clone(),
        )
        .map_err(|_| io::Error::other("manager_launch_target_refused"))?;
        Ok(Self {
            target,
            query,
            version: InstalledVersion {
                version: identity.version,
                package_root: package.to_path_buf(),
                runtime_image: runtime_image(package),
            },
        })
    }
}

fn probe(query: &ChildConfiguration) -> io::Result<runtime::RuntimeIdentity> {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?
        .block_on(runtime::identity(query, Duration::from_secs(30)))
        .map_err(io::Error::other)
}

impl VersionProbe for InstalledRuntime {
    fn reprobe(&mut self) -> Option<String> {
        let identity = probe(&self.query).ok()?;
        (same_directory(&identity.storage, self.target.storage_root())
            && identity.storage_identity == self.target.storage_identity()
            && identity.version == self.version.version)
            .then_some(identity.version)
    }
}

impl InstalledVersions for InstalledRuntime {
    fn containing(&self, image: &Path) -> Option<InstalledVersion> {
        let same = |path: &Path| std::fs::canonicalize(path).ok();
        let expected = same(&self.version.runtime_image)?;
        (same(image).as_ref() == Some(&expected)).then(|| self.version.clone())
    }

    fn failed(&self, _version: &str) -> bool {
        // Until the installation catalogue owns version-specific decoding,
        // any marker (including an unreadable or linked one) prevents adoption.
        failed_version_marker(self.target.storage_root())
    }
}

fn failed_version_marker(root: &Path) -> bool {
    !matches!(
        std::fs::symlink_metadata(root.join(".runtime/manager-failed-versions.json")),
        Err(error) if error.kind() == io::ErrorKind::NotFound
    )
}

fn same_directory(actual: &Path, expected: &Path) -> bool {
    match (
        std::fs::canonicalize(actual),
        std::fs::canonicalize(expected),
    ) {
        (Ok(actual), Ok(expected)) => actual == expected,
        _ => false,
    }
}
