//! The Linux per-session lock: a kernel-released `flock` in the user's runtime directory.
//!
//! `XDG_RUNTIME_DIR` belongs to one user and is closed to every other account, and the
//! lock file carries the native logind session in its name, so each session of
//! the user has its own lock.

use crate::custody::{LocalLock, effective_uid};
use std::fs;
use std::io;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::PathBuf;
use std::time::Duration;

/// The user's runtime directory, refused unless this user owns it and no one else may
/// enter it.
fn runtime_directory() -> io::Result<PathBuf> {
    let directory = std::env::var_os("XDG_RUNTIME_DIR")
        .map(PathBuf::from)
        .filter(|path| path.is_absolute())
        .ok_or_else(|| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "XDG_RUNTIME_DIR does not name a directory",
            )
        })?;
    let metadata = fs::symlink_metadata(&directory)?;
    if !metadata.is_dir()
        || metadata.permissions().mode() & 0o077 != 0
        || metadata.uid() != effective_uid()
    {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "the runtime directory is not private to this user",
        ));
    }
    Ok(directory)
}

/// Claim the lock file named `file_name` in the runtime directory.
pub(super) fn claim(file_name: &str, patience: Duration) -> io::Result<Option<LocalLock>> {
    let path = runtime_directory()?.join(file_name);
    let Some(lock) = LocalLock::acquire(&path, patience)? else {
        return Ok(None);
    };
    if lock.metadata()?.uid() != effective_uid() {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "another account owns the session lock",
        ));
    }
    Ok(Some(lock))
}
