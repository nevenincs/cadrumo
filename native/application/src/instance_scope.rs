//! The storage-root scope of per-user single-instance names.
//!
//! The desktop window lock and the manager's session lock and IPC name each admit
//! one holder per storage root. The scope is the root's storage identity: the digest
//! of its physical identity that names the runtime serving that root and that the
//! runtime reports in its handshake. Two paths to one directory share a scope and two
//! roots never do. The channel stays in the identifier, so stable and preview never
//! share a scope either. The joining grammar is declared by the transport contract.

use crate::runtime_client::Endpoint;
use cadrumo_platform::INSTANCE_ROOT_SCOPE;
use std::{io, path::Path};

/// The longest scoped identifier a lock or IPC name accepts.
const IDENTIFIER_BYTES: usize = 128;

fn plain(identifier: &str) -> bool {
    !identifier.is_empty()
        && identifier.len() <= IDENTIFIER_BYTES
        && identifier
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'-' | b'_'))
        && !identifier.starts_with('.')
        && !identifier.ends_with('.')
}

/// `identifier` scoped to the root whose storage identity is `storage_identity`.
pub fn root_scoped(identifier: &str, storage_identity: &str) -> io::Result<String> {
    let identity = storage_identity.len() == 64
        && storage_identity
            .bytes()
            .all(|byte| matches!(byte, b'0'..=b'9' | b'a'..=b'f'));
    let scoped = format!("{identifier}{INSTANCE_ROOT_SCOPE}{storage_identity}");
    if !plain(identifier) || !identity || !plain(&scoped) {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "an instance scope needs a plain identifier and a storage identity",
        ));
    }
    Ok(scoped)
}

/// The storage identity of `root`, creating the root owner-only when it is absent
/// so that a first launch has an identity to claim under.
pub fn storage_scope(root: &Path) -> io::Result<String> {
    cadrumo_platform::storage::create_storage_root(root)?;
    Endpoint::of(root)
        .map(|endpoint| endpoint.storage_identity)
        .map_err(|_| {
            io::Error::new(
                io::ErrorKind::PermissionDenied,
                "the storage root has no identity this account owns",
            )
        })
}

/// `identifier` scoped to the storage root at `root`.
pub fn scoped_to_root(identifier: &str, root: &Path) -> io::Result<String> {
    root_scoped(identifier, &storage_scope(root)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn shared_vectors_match_the_canonical_owner() {
        for vector in cadrumo_platform::INSTANCE_SCOPE_VECTORS {
            assert_eq!(
                root_scoped(vector.identifier, vector.storage_identity).unwrap(),
                vector.expected_identifier
            );
        }
        assert!(cadrumo_platform::INSTANCE_SCOPE_VECTORS.len() >= 6);
    }

    #[test]
    fn malformed_identifiers_and_identities_are_refused() {
        let identity = "f".repeat(64);
        for identifier in ["", ".id", "id.", "id/x", "mé", &"a".repeat(59)] {
            assert!(root_scoped(identifier, &identity).is_err(), "{identifier}");
        }
        for identity in [
            "",
            &"0".repeat(63),
            &"0".repeat(65),
            &"A".repeat(64),
            &"g".repeat(64),
        ] {
            assert!(
                root_scoped("md.neve.cadrumo", identity).is_err(),
                "{identity}"
            );
        }
        assert!(root_scoped(&"a".repeat(58), &identity).is_ok());
    }

    struct Scratch(std::path::PathBuf);
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    /// Aliases of one directory share a scope; another directory, or another
    /// channel's identifier on the same directory, does not.
    #[test]
    fn one_root_has_one_scope_and_two_roots_two() {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let scratch = Scratch(
            std::fs::canonicalize(std::env::temp_dir())
                .unwrap()
                .join(format!("cadrumo-scope-{}-{nanos}", std::process::id())),
        );
        let first = scratch.0.join("first");
        let second = scratch.0.join("second");
        // An absent root is created, so it has an identity to scope by.
        let scoped = scoped_to_root("md.neve.cadrumo", &first).unwrap();
        assert!(first.is_dir());
        std::fs::create_dir(&second).unwrap();
        assert_eq!(
            scoped,
            scoped_to_root("md.neve.cadrumo", &first.join("..").join("first")).unwrap()
        );
        #[cfg(unix)]
        {
            let alias = scratch.0.join("alias");
            std::os::unix::fs::symlink(&first, &alias).unwrap();
            assert_eq!(scoped, scoped_to_root("md.neve.cadrumo", &alias).unwrap());
        }
        assert_ne!(scoped, scoped_to_root("md.neve.cadrumo", &second).unwrap());
        assert_ne!(
            scoped,
            scoped_to_root("md.neve.cadrumo.preview", &first).unwrap()
        );
        let identity = Endpoint::of(&first).unwrap().storage_identity;
        assert_eq!(
            scoped,
            format!("md.neve.cadrumo{INSTANCE_ROOT_SCOPE}{identity}")
        );
    }
}
