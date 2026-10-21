//! AppKit adapter for the real manager lifetime owner. No entry point calls this
//! module yet: native installation, cutover and interactive acceptance are gates.
#![allow(unsafe_code)]

use super::State;
use crate::{
    background::Background,
    ipc,
    lifecycle::ManagerLifecycle,
    macos::ipc::Server,
    macos::menu::{Action, Controller, appkit::StatusMenu},
    session::instance::SessionLock,
};
use objc2::rc::Retained;
use objc2::runtime::ProtocolObject;
use objc2::{DefinedClass, MainThreadOnly, define_class, msg_send, sel};
use objc2_app_kit::{
    NSApplication, NSApplicationDelegate, NSApplicationTerminateReply, NSEventTrackingRunLoopMode,
    NSModalPanelRunLoopMode, NSWorkspace, NSWorkspaceSessionDidBecomeActiveNotification,
    NSWorkspaceSessionDidResignActiveNotification, NSWorkspaceWillPowerOffNotification,
};
use objc2_foundation::{
    MainThreadMarker, NSDefaultRunLoopMode, NSNotification, NSObject, NSObjectProtocol, NSRunLoop,
    NSTimer,
};
use std::{
    cell::{Cell, RefCell},
    io,
    sync::{
        Arc,
        atomic::{AtomicU8, Ordering},
    },
    time::Duration,
};

const END_SESSION: u8 = 1;
const ACTIVITY_CHANGED: u8 = 2;

/// Custody is supplied by native admission, never manufactured by the event loop.
/// This host cannot enroll upgrades until a real native coordinator is integrated.
#[must_use = "a live manager host owns supervisor and native session custody"]
pub struct Host {
    background: Background,
    _session: SessionLock,
    ipc: Server,
    state: State,
    menu: Controller,
}

#[must_use = "recover and retain the host; an event-loop error is not settlement"]
pub struct RetainedFailure {
    pub host: Host,
    pub error: io::Error,
}

impl Host {
    pub fn new(
        background: Background,
        session: SessionLock,
        ipc: Server,
        menu: Controller,
    ) -> Self {
        Self {
            background,
            _session: session,
            ipc,
            state: State::default(),
            menu,
        }
    }

    fn session_end(&mut self) {
        if self.state.session_end() {
            ManagerLifecycle::begin_session_end(&mut self.background);
        }
    }

    /// Explicit user intent only. OS termination must never record this marker.
    pub fn user_quit(&mut self) -> io::Result<()> {
        if self.state.user_quit()
            && let Err(error) = self.background.quit()
        {
            self.state.failed = true;
            ManagerLifecycle::begin_session_end(&mut self.background);
            return Err(error);
        }
        Ok(())
    }

    fn poll(&mut self) {
        let background = &mut self.background;
        let ending = self.state.ending.is_some();
        if self
            .ipc
            .poll(|_, request| {
                ipc::respond(request, || {
                    if ending {
                        return Err(io::ErrorKind::WouldBlock.into());
                    }
                    background.retry()
                })
            })
            .is_err()
        {
            self.state.failed = true;
            self.session_end();
        }
        if self.background.poll().is_err() {
            self.state.failed = true;
            self.session_end();
        }
    }

    fn can_finish(&self) -> bool {
        self.state.can_finish(
            self.background.session_end_settled(),
            self.background.quit_completed(),
        )
    }

    fn menu_action(&mut self, action: Action) {
        let result = self.menu.select(
            action,
            self.background.status(),
            self.state.ending.is_some(),
        );
        let result = result.and_then(|action| match action {
            Some(Action::Restart) => self.background.restart(),
            Some(Action::Retry) => self.background.retry(),
            Some(Action::Quit) => self.user_quit(),
            None => Ok(()),
            _ => Err(io::ErrorKind::InvalidData.into()),
        });
        if result.is_err() {
            self.menu.rejected();
        }
    }

    /// Register signals only here, in executable composition, never on import or
    /// in tests. The caller must own the application's main-thread event loop.
    /// AppKit normally terminates the process; an unexpected return carries all
    /// native custody back to the caller rather than dropping a live supervisor.
    /// Tokio's installed signal disposition remains process-wide after a return.
    pub fn run(self, mtm: MainThreadMarker) -> RetainedFailure {
        let menu = match StatusMenu::new(mtm) {
            Ok(menu) => menu,
            Err(error) => return RetainedFailure { host: self, error },
        };
        let runtime = match tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
        {
            Ok(runtime) => runtime,
            Err(error) => return RetainedFailure { host: self, error },
        };
        let signal = {
            let _entered = runtime.enter();
            tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
        };
        let signal = match signal {
            Ok(signal) => signal,
            Err(error) => return RetainedFailure { host: self, error },
        };
        let flags = Arc::new(AtomicU8::new(0));
        let observer = Observer::new(Arc::clone(&flags));
        let delegate = Delegate::new(
            mtm,
            Driver {
                host: self,
                runtime,
                signal,
                flags,
                menu,
            },
        );
        let application = NSApplication::sharedApplication(mtm);
        let center = NSWorkspace::sharedWorkspace().notificationCenter();
        // SAFETY: Each selector has the documented single NSNotification argument.
        // Observer contains only atomic state and may receive notifications on any
        // posting thread; it never touches the main-thread owner or AppKit there.
        unsafe {
            center.addObserver_selector_name_object(
                &observer,
                sel!(powerOff:),
                Some(NSWorkspaceWillPowerOffNotification),
                None,
            );
            center.addObserver_selector_name_object(
                &observer,
                sel!(activity:),
                Some(NSWorkspaceSessionDidBecomeActiveNotification),
                None,
            );
            center.addObserver_selector_name_object(
                &observer,
                sel!(activity:),
                Some(NSWorkspaceSessionDidResignActiveNotification),
                None,
            );
        }
        application.setDelegate(Some(ProtocolObject::from_ref(&*delegate)));
        // SAFETY: The retained main-thread delegate has the matching timer selector;
        // it outlives both registrations, which are invalidated before extraction.
        let timer = unsafe {
            NSTimer::timerWithTimeInterval_target_selector_userInfo_repeats(
                0.05,
                &delegate,
                sel!(tick:),
                None,
                true,
            )
        };
        let run_loop = NSRunLoop::currentRunLoop();
        // SAFETY: These are Apple's exported run-loop modes. Deferred termination
        // and an open status menu must not suspend supervision/IPC polling.
        unsafe {
            run_loop.addTimer_forMode(&timer, NSDefaultRunLoopMode);
            run_loop.addTimer_forMode(&timer, NSModalPanelRunLoopMode);
            run_loop.addTimer_forMode(&timer, NSEventTrackingRunLoopMode);
        }
        application.run();
        // SAFETY: Both objects are still strongly retained on this thread.
        unsafe {
            timer.invalidate();
            center.removeObserver(&observer);
        }
        application.setDelegate(None);
        let driver = delegate
            .ivars()
            .driver
            .borrow_mut()
            .take()
            .expect("owned driver");
        RetainedFailure {
            host: driver.host,
            error: io::Error::other("manager_appkit_loop_returned"),
        }
    }
}

struct Driver {
    host: Host,
    runtime: tokio::runtime::Runtime,
    signal: tokio::signal::unix::Signal,
    flags: Arc<AtomicU8>,
    menu: StatusMenu,
}
impl Driver {
    fn poll(&mut self) {
        let signal = self.runtime.block_on(async {
            tokio::time::timeout(Duration::from_millis(1), self.signal.recv()).await
        });
        let flags = self.flags.swap(0, Ordering::AcqRel);
        if matches!(signal, Ok(Some(()))) || flags & END_SESSION != 0 {
            self.host.session_end();
        }
        if matches!(signal, Ok(None)) {
            self.host.state.failed = true;
            self.host.session_end();
        }
        // Activity notifications are observation hints only. The supervisor's
        // native Activity collaborator rechecks authority; switching never ends it.
        self.host.poll();
        if let Some(action) = self.menu.take_action() {
            self.host.menu_action(action);
        }
        if self.menu.take_rejection() {
            self.host.menu.rejected();
        }
        let ending = self.host.state.ending.is_some();
        let rows = self.host.menu.rows(self.host.background.status(), ending);
        self.menu.update(rows, !ending);
    }
}

struct DelegateIvars {
    driver: RefCell<Option<Driver>>,
    terminate_requested: Cell<bool>,
}
define_class!(
    // SAFETY: NSObject has no extra subclass requirements; no custom Drop.
    #[unsafe(super = NSObject)]
    #[thread_kind = MainThreadOnly]
    #[ivars = DelegateIvars]
    #[name = "CadrumoManagerLifecycleDelegate"]
    struct Delegate;
    // SAFETY: NSObjectProtocol has no additional requirements.
    unsafe impl NSObjectProtocol for Delegate {}
    // SAFETY: The delegate is main-thread-only and uses the exact SDK signatures.
    unsafe impl NSApplicationDelegate for Delegate {
        #[unsafe(method(applicationShouldTerminate:))]
        fn should_terminate(&self, _application: &NSApplication) -> NSApplicationTerminateReply {
            self.ivars().terminate_requested.set(true);
            if let Ok(mut driver) = self.ivars().driver.try_borrow_mut()
                && let Some(driver) = driver.as_mut()
            {
                if driver.host.state.ending.is_none() { driver.host.session_end(); }
                driver.host.state.deferred = true;
            }
            NSApplicationTerminateReply::TerminateLater
        }
    }
    impl Delegate {
        #[unsafe(method(tick:))]
        fn tick(&self, _timer: &NSTimer) {
            let action = {
                let Ok(mut driver) = self.ivars().driver.try_borrow_mut() else { return; };
                let Some(driver) = driver.as_mut() else { return; };
                if self.ivars().terminate_requested.get() {
                    if driver.host.state.ending.is_none() { driver.host.session_end(); }
                    driver.host.state.deferred = true;
                }
                driver.poll();
                if !driver.host.can_finish() { return; }
                driver.host.state.deferred
            };
            let application = NSApplication::sharedApplication(self.mtm());
            // No RefCell borrow crosses either potentially reentrant AppKit call.
            if action {
                application.replyToApplicationShouldTerminate(true);
            } else {
                application.terminate(None);
            }
        }
    }
);
impl Delegate {
    fn new(mtm: MainThreadMarker, driver: Driver) -> Retained<Self> {
        let this = Self::alloc(mtm).set_ivars(DelegateIvars {
            driver: RefCell::new(Some(driver)),
            terminate_requested: Cell::new(false),
        });
        // SAFETY: NSObject init has this signature and no extra invariants.
        unsafe { msg_send![super(this), init] }
    }
}

define_class!(
    // SAFETY: NSObject has no extra subclass requirements; the only ivar is atomic.
    #[unsafe(super = NSObject)]
    #[ivars = Arc<AtomicU8>]
    #[name = "CadrumoManagerWorkspaceObserver"]
    struct Observer;
    // SAFETY: NSObjectProtocol has no additional requirements.
    unsafe impl NSObjectProtocol for Observer {}
    impl Observer {
        #[unsafe(method(powerOff:))]
        fn power_off(&self, _notification: &NSNotification) {
            self.ivars().fetch_or(END_SESSION, Ordering::Release);
        }
        #[unsafe(method(activity:))]
        fn activity(&self, _notification: &NSNotification) {
            self.ivars().fetch_or(ACTIVITY_CHANGED, Ordering::Release);
        }
    }
);
impl Observer {
    fn new(flags: Arc<AtomicU8>) -> Retained<Self> {
        use objc2::AnyThread;
        let this = Self::alloc().set_ivars(flags);
        // SAFETY: NSObject init has this signature and no extra invariants.
        unsafe { msg_send![super(this), init] }
    }
}
