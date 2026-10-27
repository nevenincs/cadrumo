//! What diagnostics keep when the window is told only a code. The window words
//! `unavailable` as "Cadrumo's services aren't answering" and every host failure as
//! "Setup couldn't be reached", whatever lay behind them, so the cause of each is
//! recorded here as one diagnostics failure with a stable `reason`.
//!
//! A command the person asked for always records: each is news to them. The observer
//! repeats its read on every cue, so a read records only when its cause differs from the
//! last failed read's, and a read or command that gets through ends that run.
use super::wire::Stop;
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, Cause},
};
use std::sync::{Arc, Mutex};

/// The check that failed and the chain behind it, which is all a cause is compared by.
#[derive(Clone, Debug, PartialEq)]
struct Reported {
    reason: Option<String>,
    causes: Vec<Cause>,
}

impl Reported {
    fn of(error: &ApplicationError) -> Self {
        Self {
            reason: error.reason.as_deref().map(str::to_owned),
            causes: error.causes.clone(),
        }
    }
}

pub struct Reports {
    diagnostics: Arc<Diagnostics>,
    /// The cause of the last failure recorded, while nothing has got through since.
    last: Mutex<Option<Reported>>,
}

impl Reports {
    pub fn new(diagnostics: Arc<Diagnostics>) -> Self {
        Self {
            diagnostics,
            last: Mutex::new(None),
        }
    }

    /// Records the failure behind the answer to a command, if it has one.
    pub fn command(&self, stop: &Stop) {
        if let Some(error) = stop.cause() {
            self.error(error);
        }
    }

    /// Records the failure behind a read unless the last failed read had the same cause.
    pub fn read(&self, stop: &Stop) {
        if let Some(error) = stop.cause() {
            self.read_error(error);
        }
    }

    /// As [`Reports::read`], for a failure that is not a stop.
    pub fn read_error(&self, error: &ApplicationError) {
        let reported = Reported::of(error);
        let mut last = self.last.lock().unwrap_or_else(|e| e.into_inner());
        if last.as_ref() == Some(&reported) {
            return;
        }
        *last = Some(reported);
        drop(last);
        self.diagnostics.failure(error.clone());
    }

    /// Records a failure of the host itself, which no command or read answers.
    pub fn error(&self, error: &ApplicationError) {
        *self.last.lock().unwrap_or_else(|e| e.into_inner()) = Some(Reported::of(error));
        self.diagnostics.failure(error.clone());
    }

    /// A read or command got through: the next failure is news again.
    pub fn recovered(&self) {
        *self.last.lock().unwrap_or_else(|e| e.into_inner()) = None;
    }
}

#[cfg(test)]
#[path = "reports_tests.rs"]
mod tests;
