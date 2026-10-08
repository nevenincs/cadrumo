//! Inactive native host lifecycle policy. Installed composition remains gated on
//! native version ownership, cutover coordination and graphical acceptance.

#[cfg(target_os = "macos")]
pub mod appkit;

#[cfg(any(target_os = "macos", test))]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Ending {
    Session,
    UserQuit,
}

#[cfg(any(target_os = "macos", test))]
#[derive(Default)]
struct State {
    ending: Option<Ending>,
    deferred: bool,
    failed: bool,
}
#[cfg(any(target_os = "macos", test))]
impl State {
    fn session_end(&mut self) -> bool {
        let changed = self.ending != Some(Ending::Session);
        self.ending = Some(Ending::Session);
        changed
    }
    fn user_quit(&mut self) -> bool {
        if self.ending.is_some() {
            return false;
        }
        self.ending = Some(Ending::UserQuit);
        true
    }
    fn can_finish(&self, session_settled: bool, quit_completed: bool) -> bool {
        !self.failed
            && match self.ending {
                Some(Ending::Session) => session_settled,
                Some(Ending::UserQuit) => quit_completed,
                None => false,
            }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shutdown_is_idempotent_and_overrides_user_quit_without_implying_completion() {
        let mut state = State::default();
        assert!(!state.can_finish(true, true));
        assert!(state.user_quit());
        assert!(!state.can_finish(true, false));
        assert!(state.session_end());
        assert!(!state.session_end());
        assert!(!state.user_quit());
        assert!(!state.can_finish(false, true));
        assert!(state.can_finish(true, false));
    }
    #[test]
    fn failed_cleanup_retains_custody_even_after_a_completion_observation() {
        let mut state = State::default();
        state.session_end();
        state.failed = true;
        state.deferred = true;
        assert!(state.deferred);
        assert!(!state.can_finish(true, true));
    }
}
