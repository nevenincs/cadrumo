//! The per-user start claim: who may start the runtime of one storage root.
//!
//! The claim is the custody local lock on `.runtime/manager-start.lock`, the same lock the
//! runtime's Python owner takes on its own `.runtime/` leaves, so a crashed holder never
//! blocks a later start. A held claim means another manager is starting the runtime.

use crate::custody::{LocalLock, ensure_local_directory};
use crate::supervision::boot_record::BOOT_RECORD_LOCATION;
use std::io;
use std::path::{Path, PathBuf};
use std::time::Duration;

/// Location of the claim below the storage root, beside the runtime's boot record.
pub const START_CLAIM_LOCATION: [&str; 2] = [BOOT_RECORD_LOCATION[0], "manager-start.lock"];

/// The claim location under a storage root.
pub fn start_claim_path(storage_root: &Path) -> PathBuf {
    START_CLAIM_LOCATION
        .iter()
        .fold(storage_root.to_path_buf(), |path, part| path.join(part))
}

/// A held start claim. Dropping it releases the claim.
#[derive(Debug)]
pub struct StartClaim {
    _lock: LocalLock,
}

impl StartClaim {
    /// Take the claim for the absolute `storage_root`, polling until `patience` ends.
    ///
    /// The `.runtime` directory is created owner-only when absent. `Ok(None)` means
    /// another manager holds the claim, so the runtime is starting elsewhere; a zero
    /// patience makes one attempt.
    pub fn take(storage_root: &Path, patience: Duration) -> io::Result<Option<Self>> {
        if !storage_root.is_absolute() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "the storage root must be absolute",
            ));
        }
        ensure_local_directory(&storage_root.join(START_CLAIM_LOCATION[0]))?;
        Ok(
            LocalLock::acquire(&start_claim_path(storage_root), patience)?
                .map(|lock| Self { _lock: lock }),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::supervision::boot_record::boot_record_path;

    #[test]
    fn the_claim_sits_beside_the_boot_record() {
        let root = std::env::temp_dir();
        assert_eq!(
            start_claim_path(&root).parent(),
            boot_record_path(&root).parent()
        );
        assert_eq!(
            start_claim_path(&root),
            root.join(".runtime").join("manager-start.lock")
        );
    }

    #[test]
    fn a_relative_root_is_refused() {
        let error = StartClaim::take(Path::new("relative"), Duration::ZERO).expect_err("refused");
        assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
    }
}
