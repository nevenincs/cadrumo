//! The runtime's custody local primitives, for the manager's records under `.runtime/`.
//!
//! The Python owner is `cadrumo.adapters.persistence.storage.custody.filesystem`. Where the
//! manager and the runtime meet on one file, this module does what that owner does:
//!
//! - Every operation first pins the parent directory: on Windows each path component is
//!   held open without delete sharing and verified to be a real directory; on POSIX the
//!   path is walked one no-follow component at a time and the parent descriptor is kept.
//! - The local lock opens one no-follow leaf below the pinned parent and holds it until it
//!   drops. Windows opens it for read and write with no sharing, so the kernel refuses
//!   every other open while it is held; POSIX takes `flock`. The kernel releases both when
//!   the holder ends, so a crashed holder never leaves a stale lock behind.
//! - A record is a regular file of 1 to `maximum_bytes` bytes, never a link or reparse
//!   point, read through one no-follow open.
//! - A record is written to an unguessable sibling, synced, and renamed over its target.
//!   On Windows a replacement that a reader's open handle denies is retried for one
//!   second, as the owner does.
//! - A record is cleared through a handle that was opened and verified first.
//!
//! `tests/custody_conformance.rs` holds both sides to this with real Python processes.

use std::fs::{File, Metadata};
use std::hash::{BuildHasher, RandomState};
use std::io::{self, Read};
use std::path::{Component, Path};
use std::time::{Duration, Instant};

#[cfg(unix)]
mod posix;
#[cfg(unix)]
use posix as platform;
#[cfg(windows)]
mod windows;
#[cfg(windows)]
use windows as platform;

#[cfg(target_os = "linux")]
pub(crate) use posix::effective_uid;

/// The pause between attempts on a held lock, as the Python owner polls.
const LOCK_POLL: Duration = Duration::from_millis(25);

/// A held kernel-released local lock. Dropping it releases the lock.
#[derive(Debug)]
pub struct LocalLock {
    // Declared first so the lock is released before the parent is unpinned.
    file: File,
    _anchor: platform::Anchor,
}

impl LocalLock {
    /// Take the lock at the absolute `path`, retrying while another holder has it.
    ///
    /// `Ok(None)` means another holder still has it when `patience` ends; a zero patience
    /// makes exactly one attempt. The lock file is created when absent and never removed.
    pub fn acquire(path: &Path, patience: Duration) -> io::Result<Option<Self>> {
        let (parent, name) = split(path)?;
        let anchor = platform::anchor(parent)?;
        let deadline = Instant::now() + patience;
        Ok(
            platform::acquire_lock(&anchor, path, name, deadline)?.map(|file| Self {
                file,
                _anchor: anchor,
            }),
        )
    }

    /// Metadata of the held lock file.
    pub fn metadata(&self) -> io::Result<Metadata> {
        self.file.metadata()
    }
}

/// Wait out one lock poll, or report that `deadline` has passed.
fn wait_for_lock(deadline: Instant) -> bool {
    let remaining = deadline.saturating_duration_since(Instant::now());
    if remaining.is_zero() {
        return false;
    }
    std::thread::sleep(LOCK_POLL.min(remaining));
    true
}

/// Create the single directory `path` below an existing parent, owner-only.
///
/// An existing real directory is accepted; a link, reparse point or file is refused. On
/// Windows the directory gets the security Python's `mkdir(mode=0o700)` applies, which
/// the files created in it inherit.
pub fn ensure_local_directory(path: &Path) -> io::Result<()> {
    let (parent, name) = split(path)?;
    let anchor = platform::anchor(parent)?;
    platform::create_private_directory(&anchor, path, name)
}

/// Read a bounded record, or prove its absence through the same no-follow open.
///
/// `Ok(None)` means the record does not exist. A missing parent directory is an error of
/// kind [`io::ErrorKind::NotFound`]; a record that is empty, above `maximum_bytes`, a link,
/// a reparse point or not a regular file is an error of kind
/// [`io::ErrorKind::InvalidData`].
pub fn read_optional_local_record(path: &Path, maximum_bytes: u64) -> io::Result<Option<Vec<u8>>> {
    let (parent, name) = split(path)?;
    let anchor = platform::anchor(parent)?;
    match platform::open_record(&anchor, path, name)? {
        Some(file) => read_bounded(file, maximum_bytes).map(Some),
        None => Ok(None),
    }
}

/// Atomically replace the record at `path` with `payload`, durably.
pub fn write_local_record(path: &Path, payload: &[u8], maximum_bytes: u64) -> io::Result<()> {
    let length = u64::try_from(payload.len()).map_err(|_| refused("record exceeds its bound"))?;
    if length < 1 || length > maximum_bytes {
        return Err(refused("a record holds 1 to maximum_bytes bytes"));
    }
    let (parent, name) = split(path)?;
    let anchor = platform::anchor(parent)?;
    platform::replace_record(&anchor, path, name, payload)
}

/// Remove the record at `path` through a verified handle; an absent record is cleared.
pub fn clear_local_record(path: &Path) -> io::Result<()> {
    let (parent, name) = split(path)?;
    let anchor = platform::anchor(parent)?;
    platform::clear_record(&anchor, path, name)
}

/// The parent directory and file name of an absolute path that names one child.
fn split(path: &Path) -> io::Result<(&Path, &std::ffi::OsStr)> {
    let invalid = || {
        io::Error::new(
            io::ErrorKind::InvalidInput,
            "a local record path must be absolute and name one child",
        )
    };
    if !path.is_absolute() {
        return Err(invalid());
    }
    match path.components().next_back() {
        Some(Component::Normal(name)) => Ok((path.parent().ok_or_else(invalid)?, name)),
        _ => Err(invalid()),
    }
}

fn refused(message: &'static str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message)
}

/// Read an opened, verified regular file whose size is within its bound.
fn read_bounded(mut file: File, maximum_bytes: u64) -> io::Result<Vec<u8>> {
    let size = file.metadata()?.len();
    if size < 1 || size > maximum_bytes {
        return Err(refused("record is not a bounded regular file"));
    }
    let mut raw = Vec::new();
    file.by_ref()
        .take(maximum_bytes + 1)
        .read_to_end(&mut raw)?;
    if u64::try_from(raw.len()).ok() != Some(size) {
        return Err(refused("record changed during its bounded read"));
    }
    Ok(raw)
}

/// An unguessable `{pid}.{token}.tmp` suffix for a staging sibling.
fn staging_suffix() -> String {
    let process = std::process::id();
    // RandomState draws its keys from the operating system's random source.
    let token = RandomState::new().hash_one(process);
    format!("{process}.{token:016x}.tmp")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);

    impl Scratch {
        fn new(label: &str) -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "cadrumo-manager-custody-{label}-{}-{nanos}",
                std::process::id()
            ));
            std::fs::create_dir_all(&path).expect("scratch directory");
            Self(path)
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn relative_and_parentless_paths_are_refused() {
        for path in [Path::new("relative"), Path::new("relative/record.json")] {
            let error = read_optional_local_record(path, 8).expect_err("relative");
            assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
        }
        let root = std::env::temp_dir();
        let dotted = root.join("..");
        let error = read_optional_local_record(&dotted, 8).expect_err("dot-dot leaf");
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
    }

    #[test]
    fn a_record_round_trips_and_clears() {
        let scratch = Scratch::new("round-trip");
        let directory = scratch.0.join(".runtime");
        ensure_local_directory(&directory).expect("directory");
        ensure_local_directory(&directory).expect("an existing directory is accepted");
        let record = directory.join("record.json");
        assert_eq!(
            read_optional_local_record(&record, 64).expect("absent"),
            None
        );
        write_local_record(&record, b"{\"a\":1}", 64).expect("write");
        write_local_record(&record, b"{\"a\":2}", 64).expect("replace");
        assert_eq!(
            read_optional_local_record(&record, 64).expect("read"),
            Some(b"{\"a\":2}".to_vec())
        );
        let leftovers: Vec<_> = std::fs::read_dir(&directory)
            .expect("listing")
            .map(|entry| entry.expect("entry").file_name())
            .collect();
        assert_eq!(leftovers, [std::ffi::OsString::from("record.json")]);
        clear_local_record(&record).expect("clear");
        clear_local_record(&record).expect("clearing an absent record");
        assert_eq!(
            read_optional_local_record(&record, 64).expect("absent"),
            None
        );
    }

    #[test]
    fn records_outside_their_bound_are_refused() {
        let scratch = Scratch::new("bounds");
        let record = scratch.0.join("record.json");
        assert_eq!(
            write_local_record(&record, b"", 8)
                .expect_err("empty")
                .kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(
            write_local_record(&record, b"123456789", 8)
                .expect_err("oversized")
                .kind(),
            io::ErrorKind::InvalidData
        );
        std::fs::write(&record, b"123456789").expect("oversized record");
        assert_eq!(
            read_optional_local_record(&record, 8)
                .expect_err("oversized")
                .kind(),
            io::ErrorKind::InvalidData
        );
        std::fs::write(&record, b"").expect("empty record");
        assert_eq!(
            read_optional_local_record(&record, 8)
                .expect_err("empty")
                .kind(),
            io::ErrorKind::InvalidData
        );
    }

    #[test]
    fn a_missing_parent_is_not_found_and_a_directory_is_no_record() {
        let scratch = Scratch::new("parent");
        let missing = scratch.0.join("absent").join("record.json");
        assert_eq!(
            read_optional_local_record(&missing, 8)
                .expect_err("missing parent")
                .kind(),
            io::ErrorKind::NotFound
        );
        let directory = scratch.0.join("directory");
        std::fs::create_dir(&directory).expect("directory");
        assert!(read_optional_local_record(&directory, 8).is_err());
        assert!(LocalLock::acquire(&directory, Duration::ZERO).is_err());
        let file = scratch.0.join("file");
        std::fs::write(&file, b"x").expect("file");
        assert!(ensure_local_directory(&file).is_err());
    }

    #[test]
    fn a_held_lock_refuses_a_second_holder_until_released() {
        let scratch = Scratch::new("lock");
        let path = scratch.0.join("claim.lock");
        let first = LocalLock::acquire(&path, Duration::ZERO)
            .expect("acquire")
            .expect("free");
        assert!(
            LocalLock::acquire(&path, Duration::from_millis(60))
                .expect("attempt")
                .is_none()
        );
        drop(first);
        assert!(
            LocalLock::acquire(&path, Duration::ZERO)
                .expect("acquire")
                .is_some()
        );
    }

    #[cfg(windows)]
    #[test]
    fn a_reparse_point_leaf_is_refused() {
        let scratch = Scratch::new("reparse");
        let target = scratch.0.join("target");
        std::fs::create_dir(&target).expect("target");
        let junction = scratch.0.join("junction");
        let status = std::process::Command::new("cmd")
            .args(["/C", "mklink", "/J"])
            .arg(&junction)
            .arg(&target)
            .stdout(std::process::Stdio::null())
            .status()
            .expect("mklink");
        assert!(status.success());
        assert!(read_optional_local_record(&junction, 8).is_err());
        assert!(LocalLock::acquire(&junction, Duration::ZERO).is_err());
        assert!(read_optional_local_record(&junction.join("record.json"), 8).is_err());
        assert!(ensure_local_directory(&junction).is_err());
    }

    #[cfg(unix)]
    #[test]
    fn a_symbolic_link_leaf_is_refused() {
        let scratch = Scratch::new("link");
        let target = scratch.0.join("target");
        std::fs::write(&target, b"x").expect("target");
        let link = scratch.0.join("link");
        std::os::unix::fs::symlink(&target, &link).expect("link");
        assert!(read_optional_local_record(&link, 8).is_err());
        assert!(LocalLock::acquire(&link, Duration::ZERO).is_err());
        assert!(clear_local_record(&link).is_err());
    }
}
