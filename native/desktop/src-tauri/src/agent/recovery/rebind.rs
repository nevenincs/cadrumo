//! Presenting the stored sign-in for a session the runtime keeps suspended.
//!
//! The runtime cues the connection that holds a session when it suspends it.
//! The cue is only a reason to read where the session stands: when it is
//! suspended, the stored sign-in is presented once, on that same connection.
//! If it is refused the window only shows that the password is needed, which
//! rebinds on this connection as well. A second automatic presentation within
//! the same loss would only repeat the refusal.

use super::{Custody, Reconnecting};
use cadrumo_application::runtime_client::{
    Admitted, Frontend, ResumeRefusal, SessionExchange, Standing, rebind_receipt, session_standing,
};
use std::{
    path::PathBuf,
    sync::{Arc, Mutex, MutexGuard, Weak},
    time::{Duration, Instant},
};

/// The longest the runtime may take to say where the session stands.
const STANDING: Duration = Duration::from_secs(30);
/// The longest the runtime may take to admit a presented proof.
const REBIND: Duration = Duration::from_secs(120);

/// How the window proves its stored sign-in again on the connection that
/// holds its session.
pub trait Proof: Send + Sync {
    /// Presents the proof for `session` on `exchange`.
    fn present(
        &self,
        exchange: &dyn SessionExchange,
        session: &Admitted,
        deadline: Instant,
    ) -> Result<(), ResumeRefusal>;
}

/// The sign-in the runtime stored for the profile under the storage root.
pub struct StoredReceipt {
    pub storage_root: PathBuf,
}

impl Proof for StoredReceipt {
    fn present(
        &self,
        exchange: &dyn SessionExchange,
        session: &Admitted,
        deadline: Instant,
    ) -> Result<(), ResumeRefusal> {
        rebind_receipt(
            exchange,
            &self.storage_root,
            session,
            Frontend::Desktop,
            deadline,
        )
        .map(|_| ())
    }
}

/// What a session that is held on a connection needs to keep it through a loss.
#[derive(Clone)]
pub struct Recovery {
    pub custody: Custody,
    pub proof: Arc<dyn Proof>,
}

/// What to do about a session the runtime reports suspended.
#[derive(Debug, PartialEq, Eq)]
enum Step {
    /// This is the loss's first sighting: present the stored sign-in.
    Present,
    /// The stored sign-in was presented: wait for the password or the window's end.
    Wait,
    /// The session returned after the report was asked for, so it is out of date.
    Stale,
}

/// One loss from the first time the session was seen suspended to its return.
#[derive(Debug)]
struct Loss {
    presented: bool,
    refused: bool,
}

/// Where the losses of a held session stand: how many times it returned, and
/// the loss under way.
#[derive(Debug, Default)]
struct Losses {
    returns: u64,
    current: Option<Loss>,
}

/// The losses of one held session, one at a time. The connection's reader
/// and the person's own requests both move it.
#[derive(Debug, Default)]
pub(crate) struct Course {
    losses: Mutex<Losses>,
}

impl Course {
    fn held(&self) -> MutexGuard<'_, Losses> {
        self.losses
            .lock()
            .unwrap_or_else(|error| error.into_inner())
    }

    /// How many times the session returned so far, to ask before reading its standing.
    fn returns(&self) -> u64 {
        self.held().returns
    }

    /// The session was seen suspended by a report asked for after `returns`
    /// returns. A report that predates a return says nothing about the present.
    fn suspended(&self, returns: u64) -> Step {
        let mut held = self.held();
        if held.returns != returns {
            return Step::Stale;
        }
        let loss = held.current.get_or_insert(Loss {
            presented: false,
            refused: false,
        });
        if std::mem::replace(&mut loss.presented, true) {
            Step::Wait
        } else {
            Step::Present
        }
    }

    /// The stored sign-in presented after `returns` returns was refused.
    fn refused(&self, returns: u64) {
        let mut held = self.held();
        if held.returns == returns
            && let Some(loss) = held.current.as_mut()
        {
            loss.refused = true;
        }
    }

    /// The session returned or ended: the next suspension is a new loss.
    pub(crate) fn ended(&self) {
        let mut held = self.held();
        held.returns += 1;
        held.current = None;
    }

    fn reconnecting(&self) -> Option<Reconnecting> {
        self.held().current.as_ref().map(|loss| Reconnecting {
            password_required: loss.refused,
        })
    }
}

/// Reads where `admitted` stands on its connection after the runtime cued it,
/// and presents the stored sign-in the first time that is a suspension.
pub(crate) fn follow(
    course: &Course,
    connection: &Weak<dyn SessionExchange>,
    admitted: &Admitted,
    recovery: &Recovery,
) {
    let Some(connection) = connection.upgrade() else {
        return;
    };
    let returns = course.returns();
    match session_standing(connection.as_ref(), admitted, Instant::now() + STANDING) {
        Ok(Standing::Recovering { .. }) => {
            if course.suspended(returns) == Step::Present {
                // Said before the proof is in flight, so the window shows the wait.
                recovery
                    .custody
                    .show(&admitted.session_id, course.reconnecting());
                let presented =
                    recovery
                        .proof
                        .present(connection.as_ref(), admitted, Instant::now() + REBIND);
                match presented {
                    Ok(()) => course.ended(),
                    Err(_) => course.refused(returns),
                }
            }
        }
        Ok(Standing::Held | Standing::Refused(_)) => course.ended(),
        // A lost exchange closed the connection: its end retires the session.
        Err(_) => return,
    }
    recovery
        .custody
        .show(&admitted.session_id, course.reconnecting());
}

#[cfg(test)]
mod tests {
    use super::*;

    const WAITING: Reconnecting = Reconnecting {
        password_required: false,
    };

    #[test]
    fn a_loss_presents_once_and_a_return_makes_the_next_loss_a_new_one() {
        let course = Course::default();
        assert_eq!(course.reconnecting(), None);
        let returns = course.returns();
        assert_eq!(course.suspended(returns), Step::Present);
        // Seen again within the loss: the stored sign-in is not offered twice.
        assert_eq!(course.suspended(returns), Step::Wait);
        assert_eq!(course.suspended(returns), Step::Wait);
        assert_eq!(course.reconnecting(), Some(WAITING));
        course.ended();
        assert_eq!(course.reconnecting(), None);
        assert_eq!(course.suspended(course.returns()), Step::Present);
    }

    #[test]
    fn a_refused_sign_in_asks_for_the_password_until_the_loss_ends() {
        let course = Course::default();
        let returns = course.returns();
        // A refusal before any loss was seen has nothing to belong to.
        course.refused(returns);
        assert_eq!(course.reconnecting(), None);
        assert_eq!(course.suspended(returns), Step::Present);
        course.refused(returns);
        let password = Some(Reconnecting {
            password_required: true,
        });
        assert_eq!(course.reconnecting(), password);
        assert_eq!(course.suspended(returns), Step::Wait);
        assert_eq!(course.reconnecting(), password);
        course.ended();
        assert_eq!(course.suspended(course.returns()), Step::Present);
        assert_eq!(course.reconnecting(), Some(WAITING));
    }

    #[test]
    fn what_was_read_before_a_return_neither_starts_a_loss_nor_refuses_one() {
        let course = Course::default();
        let before = course.returns();
        // The person's password rebound the session while a status was in flight.
        course.ended();
        assert_eq!(course.suspended(before), Step::Stale);
        assert_eq!(course.reconnecting(), None);
        let now = course.returns();
        assert_eq!(course.suspended(now), Step::Present);
        course.ended();
        course.refused(now);
        assert_eq!(course.reconnecting(), None);
    }
}
