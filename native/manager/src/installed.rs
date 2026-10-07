//! Admission of the package selected by this manager image.

use crate::supervision::{
    adoption::{InstalledVersion, InstalledVersions},
    environment::{ManagedLocations, runtime_environment},
    launch::{LaunchTarget, runtime_image},
    supervisor::VersionProbe,
};
use cadrumo_application::{
    child::ChildConfiguration,
    diagnostics::lifecycle::InspectionRefusal,
    error::Error as ApplicationCause,
    package::{PackageManifest, Readiness},
    runtime,
    value::RelativePath,
};
use std::{error::Error, fmt, io, path::Path, time::Duration};

#[derive(Debug)]
pub struct InspectionFailure {
    pub refusal: InspectionRefusal,
    cause: io::Error,
}

impl InspectionFailure {
    fn new(refusal: InspectionRefusal, cause: io::Error) -> Self {
        Self { refusal, cause }
    }
    fn refused(refusal: InspectionRefusal) -> Self {
        Self::new(refusal, io::ErrorKind::InvalidData.into())
    }
}
impl fmt::Display for InspectionFailure {
    fn fmt(&self, output: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(output, "manager inspection refused: {:?}", self.refusal)
    }
}
impl Error for InspectionFailure {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        Some(&self.cause)
    }
}

fn package_failure(error: ApplicationCause) -> InspectionFailure {
    let refusal = if matches!(error, ApplicationCause::Integrity(_)) {
        InspectionRefusal::PackageIntegrityRefused
    } else {
        InspectionRefusal::PackageUnavailable
    };
    InspectionFailure::new(refusal, io::Error::other(error))
}

#[derive(Clone)]
pub struct InstalledRuntime {
    pub target: LaunchTarget,
    query: ChildConfiguration,
    version: InstalledVersion,
}

impl InstalledRuntime {
    pub fn inspect(locations: &ManagedLocations) -> Result<Self, InspectionFailure> {
        let package = locations.package_root();
        require_no_failed_marker(locations.storage_root())?;
        require_package(package)?;
        let query = ChildConfiguration::new(
            package.join(crate::contract::EXECUTABLE),
            package.to_path_buf(),
            runtime_environment(locations.storage_root(), Some(package), std::env::vars_os())
                .map_err(|cause| {
                    InspectionFailure::new(InspectionRefusal::EnvironmentUnavailable, cause)
                })?
                .into_iter()
                .collect(),
        )
        .map_err(|cause| {
            InspectionFailure::new(
                InspectionRefusal::EnvironmentUnavailable,
                io::Error::other(cause),
            )
        })?;
        let identity = probe(&query).map_err(|cause| {
            InspectionFailure::new(InspectionRefusal::RuntimeProbeFailed, cause)
        })?;
        require_identity(&identity, locations.storage_root())?;
        let target = LaunchTarget::installed(
            locations,
            identity.storage_identity,
            identity.version.clone(),
        )
        .map_err(|_| InspectionFailure::refused(InspectionRefusal::LaunchTargetRefused))?;
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

fn require_no_failed_marker(root: &Path) -> Result<(), InspectionFailure> {
    if failed_version_marker(root) {
        Err(InspectionFailure::refused(
            InspectionRefusal::FailedVersionMarker,
        ))
    } else {
        Ok(())
    }
}

fn require_package(package: &Path) -> Result<(), InspectionFailure> {
    let manifest_path =
        RelativePath::new(crate::contract::MODE_PACKAGE_MANIFEST).map_err(package_failure)?;
    let manifest = PackageManifest::read(package, &manifest_path).map_err(package_failure)?;
    let platform = if cfg!(all(windows, target_arch = "x86_64")) {
        "windows-x64"
    } else {
        return Err(InspectionFailure::new(
            InspectionRefusal::UnsupportedPlatform,
            io::ErrorKind::Unsupported.into(),
        ));
    };
    let inspection = manifest
        .inspect(package, &manifest_path, platform, crate::contract::ABI)
        .map_err(package_failure)?;
    match inspection.readiness {
        Readiness::Ready => Ok(()),
        Readiness::Incompatible(_) => Err(InspectionFailure::refused(
            InspectionRefusal::PackageIncompatible,
        )),
        Readiness::Missing(_) | Readiness::NeedsUser(_) => Err(InspectionFailure::refused(
            InspectionRefusal::PackageIncomplete,
        )),
    }
}

fn require_identity(
    identity: &runtime::RuntimeIdentity,
    root: &Path,
) -> Result<(), InspectionFailure> {
    if !same_directory(&identity.storage, root) || identity.version != crate::identity::VERSION {
        Err(InspectionFailure::refused(
            InspectionRefusal::RuntimeIdentityMismatch,
        ))
    } else {
        Ok(())
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

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::diagnostics::{DiagnosticSource, Diagnostics};
    use std::{
        fs,
        path::PathBuf,
        sync::atomic::{AtomicUsize, Ordering},
    };

    struct Scratch(PathBuf);
    impl Scratch {
        fn new() -> Self {
            static NEXT: AtomicUsize = AtomicUsize::new(0);
            let root = std::env::temp_dir().join(format!(
                "manager-inspection-fixture-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&root).unwrap();
            Self(root)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn marker_and_runtime_identity_refusals_remain_distinct_and_scrubbed() {
        let scratch = Scratch::new();
        let root = scratch.0.join("root");
        let other = scratch.0.join("synthetic-private-root");
        fs::create_dir(&root).unwrap();
        fs::create_dir(&other).unwrap();
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let log = scratch.0.join("fixture.log");
        diagnostics.configure_file(&log, 16384, 1).unwrap();
        require_no_failed_marker(&root).unwrap();
        let marker = root.join(".runtime/manager-failed-versions.json");
        fs::create_dir(marker.parent().unwrap()).unwrap();
        fs::write(marker, b"synthetic-private-marker").unwrap();
        let failed = require_no_failed_marker(&root).unwrap_err();
        assert_eq!(failed.refusal, InspectionRefusal::FailedVersionMarker);
        crate::diagnostics::inspection_failed(&diagnostics, failed);
        let identity = runtime::RuntimeIdentity {
            storage: other,
            storage_identity: "a".repeat(64),
            version: crate::identity::VERSION.into(),
        };
        let failed = require_identity(&identity, &root).unwrap_err();
        assert_eq!(failed.refusal, InspectionRefusal::RuntimeIdentityMismatch);
        crate::diagnostics::inspection_failed(&diagnostics, failed);
        let mut identity = runtime::RuntimeIdentity {
            storage: root.clone(),
            storage_identity: "a".repeat(64),
            version: crate::identity::VERSION.into(),
        };
        require_identity(&identity, &root).unwrap();
        identity.version = "synthetic-private-version".into();
        assert_eq!(
            require_identity(&identity, &root).unwrap_err().refusal,
            InspectionRefusal::RuntimeIdentityMismatch
        );
        let log = fs::read_to_string(log).unwrap();
        assert!(log.contains("failed_version_marker"));
        assert!(log.contains("runtime_identity_mismatch"));
        assert!(!log.contains("synthetic-private"));
    }

    #[cfg(all(windows, target_arch = "x86_64"))]
    #[test]
    fn real_package_integrity_and_missing_file_refusals_have_different_records() {
        let scratch = Scratch::new();
        let package = scratch.0.join("package");
        let manifest = package.join(crate::contract::MODE_PACKAGE_MANIFEST);
        fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        let document = serde_json::json!({
            "layout": {"abi": crate::contract::ABI, "platform": "windows-x64"},
            "python": "3.14", "distributions": {},
            "files": {"fixture.bin": "a".repeat(64)},
            "user_docs": {"directory": "docs/user", "bundled": false}
        });
        fs::write(&manifest, serde_json::to_vec(&document).unwrap()).unwrap();
        let diagnostics = Diagnostics::new(DiagnosticSource::Manager);
        let log = scratch.0.join("fixture.log");
        diagnostics.configure_file(&log, 16384, 1).unwrap();
        let failure = require_package(&package).unwrap_err();
        assert_eq!(failure.refusal, InspectionRefusal::PackageIncomplete);
        crate::diagnostics::inspection_failed(&diagnostics, failure);
        fs::write(package.join("fixture.bin"), b"synthetic-private-file").unwrap();
        let failure = require_package(&package).unwrap_err();
        assert_eq!(failure.refusal, InspectionRefusal::PackageIncompatible);
        crate::diagnostics::inspection_failed(&diagnostics, failure);
        let log = fs::read_to_string(log).unwrap();
        assert!(log.contains("package_incomplete"));
        assert!(log.contains("package_incompatible"));
        assert!(!log.contains("synthetic-private"));
    }
}
