//! Whether a runtime already owning the storage root may be adopted, or is foreign.
//!
//! The manager adopts a running runtime only when the live process matches its boot record
//! by pid and creation time, its image is the runtime of a complete installed version that
//! the record names, its token is not fully elevated, it runs in the manager's own session,
//! and the record reports native admission. Anything else is foreign: it is reported and
//! never stopped.

use super::boot_record::BootRecord;
use super::process::ProcessIdentity;
use super::protocol::Admission;
use std::fs;
use std::path::{Path, PathBuf};

/// One complete installed version, as the installation catalogue knows it.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct InstalledVersion {
    pub version: String,
    pub package_root: PathBuf,
    /// The runtime host image of this version.
    pub runtime_image: PathBuf,
}

/// The complete installed versions. A later Step implements it over the versioned layout.
pub trait InstalledVersions: Send {
    /// The complete installed version whose package holds `image`, if any.
    fn containing(&self, image: &Path) -> Option<InstalledVersion>;
    /// Whether this user recorded a failed cutover to `version`.
    fn failed(&self, version: &str) -> bool;
}

/// Why a runtime owning the root is not adopted.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ForeignReason {
    /// The owner published no boot record.
    RecordAbsent,
    /// The boot record is not a valid record.
    RecordUnreadable,
    /// No live process has the record's pid.
    StaleRecord,
    /// The live process with that pid started at another time.
    IdentityMismatch,
    /// The process could not be inspected.
    Uninspectable,
    /// The process runs in another session.
    OtherSession,
    /// The process token is fully elevated, or its elevation could not be read.
    Elevated,
    /// The runtime admits development peers.
    DevelopmentAdmission,
    /// The image is not the runtime of a complete installed version.
    NotInstalled,
    /// The record names another version or package than the image belongs to.
    VersionMismatch,
    /// This user recorded a failed cutover to that version.
    FailedVersion,
}

/// Decide adoption of `process` against its `record`.
pub fn assess(
    record: &BootRecord,
    process: &ProcessIdentity,
    own_session: Option<u32>,
    versions: &dyn InstalledVersions,
) -> Result<InstalledVersion, ForeignReason> {
    if record.pid != process.pid || record.process_created != process.created {
        return Err(ForeignReason::IdentityMismatch);
    }
    if own_session.is_none() || process.session != own_session {
        return Err(ForeignReason::OtherSession);
    }
    if process.fully_elevated != Some(false) {
        return Err(ForeignReason::Elevated);
    }
    if record.admission != Admission::Native {
        return Err(ForeignReason::DevelopmentAdmission);
    }
    let installed = versions
        .containing(&process.image)
        .filter(|installed| same_path(&installed.runtime_image, &process.image))
        .ok_or(ForeignReason::NotInstalled)?;
    let same_package = record
        .package_directory
        .as_deref()
        .is_some_and(|directory| same_path(directory, &installed.package_root));
    if record.version != installed.version || !same_package {
        return Err(ForeignReason::VersionMismatch);
    }
    if versions.failed(&installed.version) {
        return Err(ForeignReason::FailedVersion);
    }
    Ok(installed)
}

/// Compare two paths by their resolved location where both resolve, else literally.
fn same_path(left: &Path, right: &Path) -> bool {
    match (fs::canonicalize(left), fs::canonicalize(right)) {
        (Ok(left), Ok(right)) => left == right,
        _ => left == right,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Catalogue {
        installed: InstalledVersion,
        failed: bool,
    }

    impl InstalledVersions for Catalogue {
        fn containing(&self, image: &Path) -> Option<InstalledVersion> {
            image
                .starts_with(&self.installed.package_root)
                .then(|| self.installed.clone())
        }

        fn failed(&self, _version: &str) -> bool {
            self.failed
        }
    }

    fn root() -> PathBuf {
        PathBuf::from(if cfg!(windows) {
            "C:\\nonexistent-cadrumo\\1.2.3"
        } else {
            "/nonexistent-cadrumo/1.2.3"
        })
    }

    fn catalogue(failed: bool) -> Catalogue {
        Catalogue {
            installed: InstalledVersion {
                version: "1.2.3".into(),
                package_root: root(),
                runtime_image: root().join("bin").join("cadrumo-runtime.exe"),
            },
            failed,
        }
    }

    fn record() -> BootRecord {
        BootRecord {
            boot_id: "0f8fad5b-d9cb-469f-a165-70867728950e".into(),
            pid: 40,
            process_created: 7,
            version: "1.2.3".into(),
            package_directory: Some(root()),
            admission: Admission::Native,
        }
    }

    fn process() -> ProcessIdentity {
        ProcessIdentity {
            pid: 40,
            created: 7,
            image: root().join("bin").join("cadrumo-runtime.exe"),
            fully_elevated: Some(false),
            session: Some(1),
        }
    }

    fn verdict(
        record: BootRecord,
        process: ProcessIdentity,
        failed: bool,
    ) -> Result<(), ForeignReason> {
        assess(&record, &process, Some(1), &catalogue(failed)).map(|_| ())
    }

    #[test]
    fn a_matching_installed_native_runtime_in_this_session_is_adopted() {
        assert_eq!(verdict(record(), process(), false), Ok(()));
    }

    #[test]
    fn each_failed_condition_makes_the_runtime_foreign() {
        let cases: [(BootRecord, ProcessIdentity, bool, ForeignReason); 9] = [
            (
                BootRecord {
                    process_created: 8,
                    ..record()
                },
                process(),
                false,
                ForeignReason::IdentityMismatch,
            ),
            (
                BootRecord {
                    pid: 44,
                    ..record()
                },
                process(),
                false,
                ForeignReason::IdentityMismatch,
            ),
            (
                record(),
                ProcessIdentity {
                    session: Some(2),
                    ..process()
                },
                false,
                ForeignReason::OtherSession,
            ),
            (
                record(),
                ProcessIdentity {
                    fully_elevated: Some(true),
                    ..process()
                },
                false,
                ForeignReason::Elevated,
            ),
            (
                record(),
                ProcessIdentity {
                    fully_elevated: None,
                    ..process()
                },
                false,
                ForeignReason::Elevated,
            ),
            (
                BootRecord {
                    admission: Admission::Development,
                    ..record()
                },
                process(),
                false,
                ForeignReason::DevelopmentAdmission,
            ),
            (
                record(),
                ProcessIdentity {
                    image: root().join("bin").join("python.exe"),
                    ..process()
                },
                false,
                ForeignReason::NotInstalled,
            ),
            (
                BootRecord {
                    version: "1.2.4".into(),
                    ..record()
                },
                process(),
                false,
                ForeignReason::VersionMismatch,
            ),
            (record(), process(), true, ForeignReason::FailedVersion),
        ];
        for (record, process, failed, reason) in cases {
            assert_eq!(verdict(record, process, failed), Err(reason), "{reason:?}");
        }
    }

    #[test]
    fn a_record_without_a_package_directory_is_not_adopted() {
        let record = BootRecord {
            package_directory: None,
            ..record()
        };
        assert_eq!(
            verdict(record, process(), false),
            Err(ForeignReason::VersionMismatch)
        );
    }

    #[test]
    fn an_unknown_own_session_adopts_nothing() {
        assert_eq!(
            assess(&record(), &process(), None, &catalogue(false)).map(|_| ()),
            Err(ForeignReason::OtherSession)
        );
    }
}
