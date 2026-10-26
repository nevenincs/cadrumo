//! Real metadata subprocesses refuse incompatible recovery and retain no probe owner.
#![cfg(all(windows, feature = "fixture-test-mode"))]

use cadrumo_manager::{
    activation_probe::require_retry_support,
    failed_versions::{FailedVersions, path},
    supervision::process::{InspectError, open_process},
};
use std::{
    collections::BTreeMap,
    fs, io,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::{Duration, Instant},
};

const FIXTURE: &str = env!("CARGO_BIN_EXE_cadrumo-manager-fixture");

struct Fixture(PathBuf);
impl Fixture {
    fn new(mode: &str) -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let root = std::env::temp_dir().join(format!(
            "manager-retry-metadata-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed),
        ));
        fs::create_dir(&root).unwrap();
        fs::write(root.join("retry-probe-mode"), mode).unwrap();
        FailedVersions::record(&root, "1.0.0", "0.9.0").unwrap();
        Self(root)
    }

    fn assert_settled(&self, unchanged: &[u8]) {
        let pid: u32 = fs::read_to_string(self.0.join("retry-probe-pid"))
            .unwrap()
            .parse()
            .unwrap();
        assert!(matches!(open_process(pid), Err(InspectError::NotRunning)));
        assert_eq!(fs::read(path(&self.0)).unwrap(), unchanged);
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn snapshot(root: &Path) -> BTreeMap<PathBuf, Option<Vec<u8>>> {
    fn collect(root: &Path, directory: &Path, entries: &mut BTreeMap<PathBuf, Option<Vec<u8>>>) {
        for entry in fs::read_dir(directory).unwrap() {
            let entry = entry.unwrap();
            let path = entry.path();
            let kind = entry.file_type().unwrap();
            let relative = path.strip_prefix(root).unwrap().to_path_buf();
            if kind.is_dir() {
                entries.insert(relative, None);
                collect(root, &path, entries);
            } else {
                assert!(kind.is_file());
                entries.insert(relative, Some(fs::read(path).unwrap()));
            }
        }
    }
    let mut entries = BTreeMap::new();
    collect(root, root, &mut entries);
    entries
}

#[test]
fn capable_legacy_and_failed_metadata_children_are_joined_without_state_edits() {
    for (mode, expected) in [
        ("capable", None),
        ("legacy", Some(io::ErrorKind::Unsupported)),
        ("failed", Some(io::ErrorKind::Unsupported)),
    ] {
        let fixture = Fixture::new(mode);
        let unchanged = fs::read(path(&fixture.0)).unwrap();
        let result = require_retry_support(FIXTURE.as_ref(), &fixture.0);
        assert_eq!(result.err().map(|error| error.kind()), expected, "{mode}");
        fixture.assert_settled(&unchanged);
    }
}

#[test]
fn timeout_terminates_and_joins_only_the_metadata_child() {
    let fixture = Fixture::new("timeout");
    let unchanged = fs::read(path(&fixture.0)).unwrap();
    let started = Instant::now();
    let error = require_retry_support(FIXTURE.as_ref(), &fixture.0).unwrap_err();
    assert_eq!(error.kind(), io::ErrorKind::TimedOut);
    assert!(started.elapsed() < Duration::from_secs(6));
    fixture.assert_settled(&unchanged);
}

#[test]
fn current_manager_supports_retry_without_opening_admission_or_runtime_ownership() {
    let fixture = Fixture::new("capable");
    let unchanged = fs::read(path(&fixture.0)).unwrap();
    let before = snapshot(&fixture.0);
    require_retry_support(env!("CARGO_BIN_EXE_cadrumo-manager").as_ref(), &fixture.0).unwrap();
    assert_eq!(snapshot(&fixture.0), before);
    assert_eq!(fs::read(path(&fixture.0)).unwrap(), unchanged);
}
