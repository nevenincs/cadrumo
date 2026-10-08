//! Menu policy for the inactive Darwin host. Native installation effects must
//! be supplied by their real owner before executable composition is possible.

use crate::{preferences::Preferences, strings::Strings};
use std::io;

#[cfg(target_os = "macos")]
pub mod appkit;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Action {
    Restart,
    Retry,
    OpenApplication,
    OpenLogs,
    SignIn,
    Quit,
}

#[derive(Clone, Copy)]
pub struct Availability {
    pub application: bool,
    pub sign_in: bool,
    pub cutover_unsettled: bool,
}

/// Required native ports. Construction does not call them. No production
/// implementation is provided until native installation/cutover composition exists.
pub trait Effects {
    fn availability(&self) -> io::Result<Availability>;
    fn open_application(&mut self) -> io::Result<()>;
    fn open_logs(&mut self) -> io::Result<()>;
    /// Return the canonical record only after the native owner has successfully
    /// committed the requested per-user preference. Never claim registration
    /// from a menu toggle or write installer-owned state from this adapter.
    fn change_sign_in(&mut self, enabled: bool) -> io::Result<Preferences>;
}

#[derive(PartialEq, Eq)]
pub struct Row {
    pub label: String,
    pub action: Option<Action>,
    pub enabled: bool,
    pub checked: bool,
    pub warning: Option<String>,
}

pub struct Controller {
    strings: Strings,
    preferences: Preferences,
    effects: Box<dyn Effects>,
    failed: bool,
}

fn remedy(status: &str) -> Action {
    if matches!(status, "unavailable" | "update_failed") {
        Action::Retry
    } else {
        Action::Restart
    }
}

fn permitted(action: Action, status: &str, ending: bool, available: Availability) -> bool {
    if ending {
        return false;
    }
    match action {
        Action::Restart | Action::Retry => action == remedy(status) && !available.cutover_unsettled,
        Action::Quit | Action::SignIn if available.cutover_unsettled => false,
        Action::SignIn => available.sign_in,
        Action::OpenApplication => available.application,
        Action::OpenLogs | Action::Quit => true,
    }
}

impl Controller {
    pub fn new(strings: Strings, preferences: Preferences, effects: Box<dyn Effects>) -> Self {
        Self {
            strings,
            preferences,
            effects,
            failed: false,
        }
    }

    /// The status comes from Background's protocol/ownership state, never from
    /// merely observing a live PID. Missing native availability disables actions.
    pub fn rows(&mut self, status: &str, ending: bool) -> Vec<Row> {
        let available = self
            .effects
            .availability()
            .inspect_err(|_| self.failed = true)
            .ok();
        let mut rows = vec![Row {
            label: self.strings.get(status).to_owned(),
            action: None,
            enabled: false,
            checked: false,
            warning: None,
        }];
        if self.failed {
            rows.push(Row {
                label: self.strings.get("action_failed").to_owned(),
                action: None,
                enabled: false,
                checked: false,
                warning: None,
            });
        }
        for (action, key, warning) in [
            (
                remedy(status),
                if remedy(status) == Action::Retry {
                    "retry"
                } else {
                    "restart"
                },
                (remedy(status) == Action::Restart).then_some("restart_warning"),
            ),
            (Action::OpenApplication, "open_application", None),
            (Action::OpenLogs, "open_logs", None),
            (Action::SignIn, "start_at_sign_in", None),
            (Action::Quit, "quit", Some("quit_warning")),
        ] {
            rows.push(Row {
                label: self.strings.get(key).to_owned(),
                action: Some(action),
                enabled: available.is_some_and(|value| permitted(action, status, ending, value)),
                checked: action == Action::SignIn && self.preferences.start_at_sign_in,
                warning: warning.map(|key| self.strings.get(key).to_owned()),
            });
        }
        rows
    }

    pub fn rejected(&mut self) {
        self.failed = true;
    }

    /// Revalidate at execution, after the user selected the confirmation item.
    /// Runtime controls are returned to the real lifecycle owner, never executed
    /// by a substitute supervisor in this model.
    pub fn select(
        &mut self,
        action: Action,
        status: &str,
        ending: bool,
    ) -> io::Result<Option<Action>> {
        let result = self.perform(action, status, ending);
        self.failed = result.is_err();
        result
    }

    fn perform(
        &mut self,
        action: Action,
        status: &str,
        ending: bool,
    ) -> io::Result<Option<Action>> {
        if ending || !permitted(action, status, ending, self.effects.availability()?) {
            return Err(io::ErrorKind::WouldBlock.into());
        }
        match action {
            Action::OpenApplication => self.effects.open_application()?,
            Action::OpenLogs => self.effects.open_logs()?,
            Action::SignIn => {
                let requested = !self.preferences.start_at_sign_in;
                let committed = self.effects.change_sign_in(requested)?;
                if committed.start_at_sign_in != requested {
                    return Err(io::ErrorKind::InvalidData.into());
                }
                self.preferences = committed;
            }
            action => return Ok(Some(action)),
        }
        Ok(None)
    }
}

/// One main-thread pending selection. Closing admission discards queued intent;
/// overload and shutdown are explicit rejection, never an unbounded backlog.
#[cfg(any(target_os = "macos", test))]
#[derive(Default)]
struct Queue {
    pending: std::cell::Cell<Option<Action>>,
    accepting: std::cell::Cell<bool>,
    rejected: std::cell::Cell<bool>,
}
#[cfg(any(target_os = "macos", test))]
impl Queue {
    fn admit(&self, accepting: bool) {
        self.accepting.set(accepting);
        if !accepting && self.pending.take().is_some() {
            self.rejected.set(true);
        }
    }
    fn push(&self, action: Action) {
        if !self.accepting.get() || self.pending.get().is_some() {
            self.rejected.set(true);
        } else {
            self.pending.set(Some(action));
        }
    }
}

#[cfg(test)]
mod tests;
