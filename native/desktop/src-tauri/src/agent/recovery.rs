//! The person's session while the runtime keeps it suspended after the
//! profile's worker was lost.
//!
//! A lost worker takes the key with it, so the runtime suspends every session
//! of the profile for a window instead of ending them: a suspended session
//! grants nothing, and only the connection that held it can bring it back, by
//! presenting a proof again. This window holds the person's session on its own
//! connection, so it is the one to do that: [`rebind`] presents the stored
//! sign-in once per loss and, when that is refused, leaves the password to the
//! person. What the account shows of it is [`Custody`].
//!
//! The service the person admits and the other frontends never present a
//! proof: the runtime restores a service when its parent returns.

#[cfg(windows)]
pub(crate) mod rebind;

use cadrumo_application::error::application::{ApplicationError, Cause};
use serde::Serialize;
use std::{future::Future, sync::Arc};
use tokio::sync::watch;

/// The code a held session answers a request with while the runtime keeps it
/// suspended: the request was refused, the session is still held.
pub(crate) const RECOVERING: &str = "recovering";

/// Whether `error` is a request the held session refused only because the
/// runtime keeps it suspended: the person is not signed out.
pub(crate) fn is_recovering(error: &ApplicationError) -> bool {
    error.causes.iter().any(
        |cause| matches!(cause, Cause::Child(refusal) if refusal.code.as_deref() == Some(RECOVERING)),
    )
}

/// What the window shows of a session that waits for a fresh proof.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Reconnecting {
    /// The stored sign-in did not bring the session back: only the password can.
    pub password_required: bool,
}

/// The session a window holds, as far as the account shows it, shared by the
/// connection that reads it and the account that reports it.
#[derive(Clone, Debug)]
pub struct Custody {
    /// The session that waits and what the window shows of it.
    waiting: Arc<watch::Sender<Option<(String, Reconnecting)>>>,
}

impl Default for Custody {
    fn default() -> Self {
        Self {
            waiting: Arc::new(watch::Sender::new(None)),
        }
    }
}

impl Custody {
    /// What the window shows now: a session waiting for a fresh proof, or nothing.
    pub fn reconnecting(&self) -> Option<Reconnecting> {
        self.waiting.borrow().as_ref().map(|(_, shown)| *shown)
    }

    /// Resolves at the next change after this call. Create it before reading,
    /// so a change arriving meanwhile is not missed.
    pub fn changed(&self) -> impl Future<Output = ()> + Send + 'static {
        let mut receiver = self.waiting.subscribe();
        async move {
            if receiver.changed().await.is_err() {
                // The window is going away; nothing will change any more.
                std::future::pending::<()>().await;
            }
        }
    }

    /// Says what `session` shows. A session that does not wait any more
    /// clears only its own mark, never the one of the session that replaced it.
    #[cfg(any(windows, test))]
    fn show(&self, session: &str, shown: Option<Reconnecting>) {
        self.waiting.send_if_modified(|held| {
            let next = match (shown, held.as_ref()) {
                (Some(shown), _) => Some((session.to_owned(), shown)),
                (None, Some((owner, _))) if owner == session => None,
                (None, _) => return false,
            };
            if *held == next {
                return false;
            }
            *held = next;
            true
        });
    }

    /// The session returned or ended: it shows nothing more.
    #[cfg(windows)]
    pub(crate) fn clear(&self, session: &str) {
        self.show(session, None);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use cadrumo_application::error::application::{ChildRefusal, ErrorCode, Operation};
    use serde_json::json;

    const SHOWN: Reconnecting = Reconnecting {
        password_required: false,
    };

    #[test]
    fn a_session_clears_only_its_own_mark() {
        let custody = Custody::default();
        custody.show("old", Some(SHOWN));
        custody.show("new", Some(SHOWN));
        custody.show("old", None);
        assert_eq!(custody.reconnecting(), Some(SHOWN));
        custody.show("new", None);
        assert_eq!(custody.reconnecting(), None);
    }

    #[tokio::test]
    async fn a_change_is_awaited_only_when_it_changes_what_is_shown() {
        let custody = Custody::default();
        let first = custody.changed();
        custody.show("session", Some(SHOWN));
        first.await;
        let again = custody.changed();
        // The same mark again is no change; a password now required is.
        custody.show("session", Some(SHOWN));
        let password = Reconnecting {
            password_required: true,
        };
        custody.show("session", Some(password));
        again.await;
        assert_eq!(custody.reconnecting(), Some(password));
    }

    #[test]
    fn a_reconnecting_mark_is_worded_for_the_window_in_camel_case() {
        let password = Reconnecting {
            password_required: true,
        };
        assert_eq!(
            serde_json::to_value(password).unwrap(),
            json!({"passwordRequired": true})
        );
    }

    #[test]
    fn a_refused_request_is_recovering_only_for_the_code_the_held_session_answers() {
        let refused = |code: &str| {
            ApplicationError::new(ErrorCode::ReadFailed, Operation::Cli)
                .with_reason("person_request_refused")
                .caused_by(ChildRefusal::answered(&json!({"code": code})))
        };
        assert!(is_recovering(&refused(RECOVERING)));
        assert!(!is_recovering(&refused("inactive")));
        assert!(!is_recovering(&ApplicationError::new(
            ErrorCode::ReadFailed,
            Operation::Cli
        )));
    }
}
