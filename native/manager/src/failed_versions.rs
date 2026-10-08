//! Bounded per-user cutover failures. Corrupt or foreign records fail closed.
use crate::{contract::MANAGER_FAILED_VERSIONS, custody};
use cadrumo_application::installation::version;
use serde::{Deserialize, Serialize};
use std::{
    io,
    path::{Path, PathBuf},
};

const LIMIT: usize = 32;
const BYTES: u64 = 4096;
#[derive(Default, Debug, PartialEq, Eq)]
pub struct FailedVersions(Vec<Failure>);
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct Failure {
    version: String,
    previous: String,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Record {
    schema: u32,
    versions: Vec<Failure>,
}

pub fn path(root: &Path) -> PathBuf {
    root.join(MANAGER_FAILED_VERSIONS)
}
impl FailedVersions {
    pub fn read(root: &Path) -> io::Result<Self> {
        let bytes = match custody::read_optional_local_record(&path(root), BYTES) {
            Ok(Some(bytes)) => bytes,
            Ok(None) => return Ok(Self::default()),
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(Self::default()),
            Err(error) => return Err(error),
        };
        let record: Record = serde_json::from_slice(&bytes).map_err(io::Error::other)?;
        if record.schema != 1 || record.versions.len() > LIMIT {
            return Err(io::ErrorKind::InvalidData.into());
        }
        let mut previous = None;
        for release in &record.versions {
            let number = version(&release.version).map_err(io::Error::other)?;
            if version(&release.previous).map_err(io::Error::other)? >= number {
                return Err(io::ErrorKind::InvalidData.into());
            }
            if previous.is_some_and(|prior| prior >= number) {
                return Err(io::ErrorKind::InvalidData.into());
            }
            previous = Some(number);
        }
        Ok(Self(record.versions))
    }
    pub fn contains(&self, release: &str) -> bool {
        self.0.iter().any(|failed| failed.version == release)
    }
    pub fn restoration(&self, release: &str) -> Option<&str> {
        self.0
            .iter()
            .find(|failed| failed.version == release)
            .map(|failed| failed.previous.as_str())
    }
    pub fn record(root: &Path, release: &str, previous: &str) -> io::Result<()> {
        if version(previous).map_err(io::Error::other)?
            >= version(release).map_err(io::Error::other)?
        {
            return Err(io::ErrorKind::InvalidInput.into());
        }
        let mut failed = Self::read(root)?;
        if !failed.contains(release) {
            failed.0.push(Failure {
                version: release.into(),
                previous: previous.into(),
            });
        }
        failed
            .0
            .sort_by_key(|release| version(&release.version).expect("validated release"));
        // Ordinary selection never downgrades. Keep the newest bounded failure history.
        if failed.0.len() > LIMIT {
            failed.0.drain(..failed.0.len() - LIMIT);
        }
        failed.store(root)
    }
    pub fn retry(root: &Path) -> io::Result<()> {
        // Explicit Retry may replace malformed owner-custody data, but never links.
        Self::default().store(root)
    }
    fn store(self, root: &Path) -> io::Result<()> {
        custody::ensure_local_directory(root)?;
        custody::ensure_local_directory(
            path(root)
                .parent()
                .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidInput))?,
        )?;
        let bytes = serde_json::to_vec(&Record {
            schema: 1,
            versions: self.0,
        })
        .map_err(io::Error::other)?;
        custody::write_local_record(&path(root), &bytes, BYTES)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn failure_is_per_version_persists_and_explicit_retry_clears_it() {
        let root = std::env::temp_dir().join(format!(
            "manager-failed-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        assert!(!FailedVersions::read(&root).unwrap().contains("1.0.0"));
        FailedVersions::record(&root, "1.0.0", "0.9.0").unwrap();
        FailedVersions::record(&root, "1.0.0", "0.9.0").unwrap();
        let failures = FailedVersions::read(&root).unwrap();
        assert!(failures.contains("1.0.0"));
        assert_eq!(failures.restoration("1.0.0"), Some("0.9.0"));
        assert!(!failures.contains("1.0.1"));
        for bytes in [
            br#"{"schema":1,"versions":[{"version":"1.0.0","previous":"0.9.0"},{"version":"1.0.0","previous":"0.9.0"}]}"#.as_slice(),
            br#"{"schema":1,"versions":[{"version":"01.0.0","previous":"0.9.0"}]}"#,
            br#"{"schema":1,"versions":[{"version":"1.0.0","previous":"1.0.0"}]}"#,
            br#"{"schema":1,"versions":[],"extra":true}"#,
        ] {
            custody::write_local_record(&path(&root), bytes, BYTES).unwrap();
            assert!(FailedVersions::read(&root).is_err());
        }
        FailedVersions::retry(&root).unwrap();
        assert_eq!(
            FailedVersions::read(&root).unwrap(),
            FailedVersions::default()
        );
        std::fs::remove_dir_all(root).unwrap();
    }
}
