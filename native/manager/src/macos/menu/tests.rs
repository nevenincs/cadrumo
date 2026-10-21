use super::*;
use std::{
    cell::{Cell, RefCell},
    rc::Rc,
};

struct Observed {
    available: Cell<Availability>,
    fail: Cell<bool>,
    unavailable: Cell<bool>,
    mismatch: Cell<bool>,
    calls: RefCell<Vec<&'static str>>,
}
struct Fixture(Rc<Observed>);
impl Effects for Fixture {
    fn availability(&self) -> io::Result<Availability> {
        self.0.calls.borrow_mut().push("availability");
        if self.0.unavailable.get() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        Ok(self.0.available.get())
    }
    fn open_application(&mut self) -> io::Result<()> {
        self.0.calls.borrow_mut().push("application");
        Ok(())
    }
    fn open_logs(&mut self) -> io::Result<()> {
        self.0.calls.borrow_mut().push("logs");
        Ok(())
    }
    fn change_sign_in(&mut self, enabled: bool) -> io::Result<Preferences> {
        self.0.calls.borrow_mut().push("sign-in");
        if self.0.fail.get() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let mut preferences = Preferences::default();
        preferences.start_at_sign_in = if self.0.mismatch.get() {
            !enabled
        } else {
            enabled
        };
        Ok(preferences)
    }
}
fn fixture() -> (Controller, Rc<Observed>) {
    let observed = Rc::new(Observed {
        available: Cell::new(Availability {
            application: true,
            sign_in: true,
            cutover_unsettled: false,
        }),
        fail: Cell::new(false),
        unavailable: Cell::new(false),
        mismatch: Cell::new(false),
        calls: RefCell::new(Vec::new()),
    });
    let controller = Controller::new(
        Strings::current().unwrap(),
        Preferences::default(),
        Box::new(Fixture(Rc::clone(&observed))),
    );
    (controller, observed)
}

#[test]
fn construction_has_no_effect_and_projection_uses_canonical_warnings() {
    let (mut controller, observed) = fixture();
    assert!(observed.calls.borrow().is_empty());
    let rows = controller.rows("running", false);
    assert!(rows[0].action.is_none() && !rows[0].enabled);
    let restart = rows
        .iter()
        .find(|row| row.action == Some(Action::Restart))
        .unwrap();
    assert_eq!(
        restart.warning.as_deref(),
        Some(controller.strings.get("restart_warning"))
    );
    let quit = rows
        .iter()
        .find(|row| row.action == Some(Action::Quit))
        .unwrap();
    assert_eq!(
        quit.warning.as_deref(),
        Some(controller.strings.get("quit_warning"))
    );
    assert_eq!(*observed.calls.borrow(), ["availability"]);
    let rows = controller.rows("unavailable", false);
    assert!(
        rows.iter()
            .any(|row| row.action == Some(Action::Retry) && row.warning.is_none())
    );
    assert!(!rows.iter().any(|row| row.action == Some(Action::Restart)));
}

#[test]
fn stale_confirmation_cannot_restart_during_cutover_or_shutdown() {
    let (mut controller, observed) = fixture();
    assert!(
        controller
            .rows("running", false)
            .iter()
            .any(|row| row.action == Some(Action::Restart) && row.enabled)
    );
    let mut available = observed.available.get();
    available.cutover_unsettled = true;
    observed.available.set(available);
    for action in [Action::Restart, Action::Retry, Action::Quit, Action::SignIn] {
        assert_eq!(
            controller
                .select(action, "running", false)
                .unwrap_err()
                .kind(),
            io::ErrorKind::WouldBlock
        );
    }
    observed.calls.borrow_mut().clear();
    assert_eq!(
        controller
            .select(Action::Quit, "running", true)
            .unwrap_err()
            .kind(),
        io::ErrorKind::WouldBlock
    );
    assert!(observed.calls.borrow().is_empty());
    assert!(
        controller
            .rows("stopping", true)
            .iter()
            .all(|row| !row.enabled)
    );
}

#[test]
fn stale_remedy_is_refused_and_controls_return_to_real_lifecycle_owner() {
    let (mut controller, _) = fixture();
    assert!(
        controller
            .select(Action::Restart, "unavailable", false)
            .is_err()
    );
    assert!(controller.select(Action::Retry, "running", false).is_err());
    assert_eq!(
        controller
            .select(Action::Retry, "update_failed", false)
            .unwrap(),
        Some(Action::Retry)
    );
    assert_eq!(
        controller
            .select(Action::Restart, "running", false)
            .unwrap(),
        Some(Action::Restart)
    );
    assert_eq!(
        controller.select(Action::Quit, "running", false).unwrap(),
        Some(Action::Quit)
    );
}

#[test]
fn native_effect_failure_preserves_preference_and_success_updates_checkmark() {
    let (mut controller, observed) = fixture();
    observed.fail.set(true);
    assert!(controller.select(Action::SignIn, "running", false).is_err());
    assert!(controller.preferences.start_at_sign_in);
    assert!(controller.failed);
    observed.fail.set(false);
    assert_eq!(
        controller.select(Action::SignIn, "running", false).unwrap(),
        None
    );
    assert!(!controller.preferences.start_at_sign_in);
    assert!(!controller.failed);
    assert!(
        controller
            .rows("running", false)
            .iter()
            .any(|row| row.action == Some(Action::SignIn) && !row.checked)
    );
}

#[test]
fn unavailable_native_actions_never_call_effects() {
    let (mut controller, observed) = fixture();
    let mut available = observed.available.get();
    available.application = false;
    available.sign_in = false;
    observed.available.set(available);
    assert!(
        controller
            .select(Action::OpenApplication, "running", false)
            .is_err()
    );
    assert!(controller.select(Action::SignIn, "running", false).is_err());
    assert!(
        observed
            .calls
            .borrow()
            .iter()
            .all(|call| *call == "availability")
    );
    assert_eq!(
        controller
            .select(Action::OpenLogs, "running", false)
            .unwrap(),
        None
    );
    assert_eq!(observed.calls.borrow().last(), Some(&"logs"));
}

#[test]
fn queue_is_bounded_and_closing_admission_discards_pending_intent() {
    let queue = Queue::default();
    queue.push(Action::Quit);
    assert!(queue.pending.get().is_none());
    assert!(queue.rejected.replace(false));
    queue.admit(true);
    queue.push(Action::Restart);
    queue.push(Action::Quit);
    assert_eq!(queue.pending.get(), Some(Action::Restart));
    assert!(queue.rejected.replace(false));
    queue.admit(false);
    assert!(queue.pending.get().is_none());
    assert!(queue.rejected.replace(false));
    queue.admit(true);
    queue.push(Action::OpenLogs);
    assert_eq!(queue.pending.take(), Some(Action::OpenLogs));
    assert!(queue.pending.get().is_none());
}

#[test]
fn unavailable_observation_disables_every_action_and_never_runs_effects() {
    let (mut controller, observed) = fixture();
    observed.unavailable.set(true);
    assert!(
        controller
            .rows("running", false)
            .iter()
            .all(|row| !row.enabled)
    );
    assert!(controller.failed);
    for action in [
        Action::Restart,
        Action::Retry,
        Action::OpenApplication,
        Action::OpenLogs,
        Action::SignIn,
        Action::Quit,
    ] {
        assert_eq!(
            controller
                .select(action, "running", false)
                .unwrap_err()
                .kind(),
            io::ErrorKind::PermissionDenied
        );
    }
    assert!(
        observed
            .calls
            .borrow()
            .iter()
            .all(|call| *call == "availability")
    );
}

#[test]
fn mismatched_committed_preference_refuses_without_replacing_the_old_record() {
    let (mut controller, observed) = fixture();
    observed.mismatch.set(true);
    assert_eq!(
        controller
            .select(Action::SignIn, "running", false)
            .unwrap_err()
            .kind(),
        io::ErrorKind::InvalidData
    );
    assert!(controller.preferences.start_at_sign_in);
    assert!(controller.failed);
}
