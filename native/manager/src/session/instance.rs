//! One manager per logon session: the per-session single-instance lock.
//!
//! The lock name joins the manager's component identifier, `{application_id}.manager`
//! from the identity projection, with the user and the session. Neither the image path nor
//! the installation scope enters it, so every installed version and scope of one channel
//! contends for the same lock in a session.
//!
//! - *Windows:* a named mutex in the session's `Local\` namespace, owned by the user with
//!   the only access entry. An object of that name that another account owns, that this
//!   user cannot open fully, or that has another type is refused as
//!   [`io::ErrorKind::PermissionDenied`]. The kernel abandons the mutex when its holder
//!   ends, and the next claim takes it.
//! - *Linux:* `{manager id}.session.{XDG_SESSION_ID}.lock` in the user's private
//!   `XDG_RUNTIME_DIR`, locked with the kernel-released custody lock.

use std::io;
use std::time::Duration;

/// A held per-session lock. Dropping it releases the lock.
///
/// On Windows the mutex belongs to the thread that claimed it, so the lock is held and
/// released on that thread.
pub struct SessionLock {
    #[cfg(windows)]
    _mutex: super::windows::SessionMutex,
    #[cfg(target_os = "linux")]
    _lock: crate::custody::LocalLock,
}

const MAXIMUM_IDENTIFIER_BYTES: usize = 128;

/// Refuse a component identifier that is not a plain reverse-DNS name.
fn validated(manager_id: &str) -> io::Result<&str> {
    let valid = !manager_id.is_empty()
        && manager_id.len() <= MAXIMUM_IDENTIFIER_BYTES
        && manager_id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'-' | b'_'))
        && !manager_id.starts_with('.')
        && !manager_id.ends_with('.');
    if valid {
        Ok(manager_id)
    } else {
        Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "the manager identifier is not a reverse-DNS identifier",
        ))
    }
}

/// The session-local name of the lock for `manager_id`, `user` and `session`.
#[cfg(windows)]
pub fn session_lock_name(manager_id: &str, user: &str, session: &str) -> io::Result<String> {
    Ok(format!(
        "Local\\{}.{user}.session.{session}.lock",
        validated(manager_id)?
    ))
}

/// The file name of the lock for `manager_id` and `session` in the runtime directory.
#[cfg(target_os = "linux")]
pub fn session_lock_name(manager_id: &str, _user: &str, session: &str) -> io::Result<String> {
    Ok(format!("{}.session.{session}.lock", validated(manager_id)?))
}

/// Claim this session's lock for `manager_id`, polling until `patience` ends.
///
/// `Ok(None)` means another manager in this session holds it.
pub fn claim_session(manager_id: &str, patience: Duration) -> io::Result<Option<SessionLock>> {
    claim_platform(manager_id, patience)
}

#[cfg(windows)]
fn claim_platform(manager_id: &str, patience: Duration) -> io::Result<Option<SessionLock>> {
    let current = super::ManagerSession::current()?;
    let user = super::windows::User::current()?;
    let name = session_lock_name(manager_id, &user.sid, &current.session)?;
    Ok(super::windows::claim(&name, &user, patience)?.map(|mutex| SessionLock { _mutex: mutex }))
}

#[cfg(target_os = "linux")]
fn claim_platform(manager_id: &str, patience: Duration) -> io::Result<Option<SessionLock>> {
    let current = super::ManagerSession::current()?;
    let name = session_lock_name(manager_id, &current.user, &current.session)?;
    Ok(super::linux::claim(&name, patience)?.map(|lock| SessionLock { _lock: lock }))
}

#[cfg(not(any(windows, target_os = "linux")))]
fn claim_platform(manager_id: &str, _patience: Duration) -> io::Result<Option<SessionLock>> {
    validated(manager_id)?;
    Err(io::ErrorKind::Unsupported.into())
}

#[cfg(all(test, windows))]
mod tests {
    use super::super::windows::squat::{Kind, squat};
    use super::super::windows::{User, claim};
    use super::*;
    use std::sync::mpsc;
    use std::time::{SystemTime, UNIX_EPOCH};

    /// A manager identifier no real installation uses, unique to one test.
    fn manager_id(label: &str) -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        format!(
            "test.cadrumo.{label}-{}-{nanos}.manager",
            std::process::id()
        )
    }

    #[test]
    fn the_name_is_session_local_and_derives_from_identity_user_and_session() {
        let name =
            session_lock_name("md.neve.cadrumo.manager", "S-1-5-21-1-2-3-1001", "2").expect("name");
        assert_eq!(
            name,
            "Local\\md.neve.cadrumo.manager.S-1-5-21-1-2-3-1001.session.2.lock"
        );
        let preview = session_lock_name(
            "md.neve.cadrumo.preview.manager",
            "S-1-5-21-1-2-3-1001",
            "2",
        )
        .expect("name");
        assert_ne!(name, preview);
        assert_ne!(
            name,
            session_lock_name("md.neve.cadrumo.manager", "S-1-5-21-1-2-3-1001", "3").expect("name")
        );
        for invalid in ["", ".md", "md.", "md\\neve", "md neve", "Global\\md"] {
            assert!(
                session_lock_name(invalid, "S-1", "1").is_err(),
                "{invalid:?}"
            );
        }
    }

    #[test]
    fn the_production_name_uses_the_projected_manager_identifier() {
        let name = session_lock_name(crate::identity::MANAGER_ID, "S-1", "1").expect("name");
        assert!(name.starts_with(&format!("Local\\{}.", crate::identity::MANAGER_ID)));
    }

    #[test]
    fn one_holder_per_session_and_release_passes_it_on() {
        let manager = manager_id("holder");
        let (held, holding) = mpsc::channel();
        let (release, released) = mpsc::channel::<()>();
        let holder_id = manager.clone();
        let holder = std::thread::spawn(move || {
            let lock = claim_session(&holder_id, Duration::ZERO)
                .expect("claim")
                .expect("free");
            held.send(()).expect("report");
            released.recv().expect("release");
            drop(lock);
        });
        holding.recv().expect("held");
        assert!(
            claim_session(&manager, Duration::from_millis(80))
                .expect("claim")
                .is_none()
        );
        release.send(()).expect("release");
        holder.join().expect("holder");
        let lock = claim_session(&manager, Duration::from_secs(2)).expect("claim");
        assert!(lock.is_some());
    }

    #[test]
    fn the_holding_thread_cannot_claim_again() {
        let manager = manager_id("again");
        let _lock = claim_session(&manager, Duration::ZERO)
            .expect("claim")
            .expect("free");
        let error = claim_session(&manager, Duration::ZERO)
            .err()
            .expect("refused");
        assert_eq!(error.kind(), io::ErrorKind::AlreadyExists);
    }

    #[test]
    fn a_squatted_name_is_refused_as_foreign() {
        let user = User::current().expect("user");
        let session = super::super::ManagerSession::current()
            .expect("session")
            .session;
        // Only SYNCHRONIZE for this user: the claim cannot open it fully.
        let access = session_lock_name(&manager_id("access"), &user.sid, &session).expect("name");
        let _squatter = squat(
            Kind::Mutex,
            &access,
            &format!("D:P(A;;0x00100000;;;{})", user.sid),
        );
        let error = claim(&access, &user, Duration::ZERO)
            .err()
            .expect("refused");
        assert_eq!(error.kind(), io::ErrorKind::PermissionDenied, "{error}");
        // An object of another type under the lock name is refused too.
        let typed = session_lock_name(&manager_id("type"), &user.sid, &session).expect("name");
        let _squatter = squat(Kind::Event, &typed, &format!("D:P(A;;GA;;;{})", user.sid));
        let error = claim(&typed, &user, Duration::ZERO).err().expect("refused");
        assert_eq!(error.kind(), io::ErrorKind::PermissionDenied, "{error}");
    }
}
