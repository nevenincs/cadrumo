//! Lifetime of one admitted manager, independent of the Windows message pump.

use crate::{
    installed::InstalledRuntime,
    session::{
        ManagerSession,
        ownership::{BootRecordLocator, Ownership, StartKind},
    },
    startup::{self, Running, Start},
    supervision::{
        stop::PlatformStopSignal,
        supervisor::{Collaborators, Outcome, Request, SessionActivity, SupervisorConfig},
    },
};
use std::{io, sync::mpsc::TryRecvError, time::Duration};

pub struct Background {
    installed: InstalledRuntime,
    ownership: Ownership,
    activity: fn() -> Box<dyn SessionActivity>,
    running: Option<Running>,
    first: bool,
    suspended: bool,
}

impl Background {
    pub fn new(
        installed: InstalledRuntime,
        session: ManagerSession,
        activity: fn() -> Box<dyn SessionActivity>,
    ) -> Self {
        let ownership = Ownership::new(
            installed.target.storage_root().to_path_buf(),
            session,
            activity(),
            Box::new(BootRecordLocator::new(installed.target.storage_root())),
        );
        Self {
            installed,
            ownership,
            activity,
            running: None,
            first: true,
            suspended: false,
        }
    }

    pub fn poll(&mut self) -> io::Result<()> {
        if let Some(running) = &mut self.running {
            // Events contain only bounded lifecycle facts. They never carry a
            // profile, credential, or raw runtime diagnostic stream.
            for _ in running.events.try_iter() {}
            match running.ended.try_recv() {
                Ok(result) => {
                    running.join()?;
                    self.running = None;
                    match result? {
                        Outcome::Failed { .. } | Outcome::Foreign(_) | Outcome::StoodDown(_) => {
                            return Err(io::Error::other("manager_runtime_unavailable"));
                        }
                        _ => {}
                    }
                }
                Err(TryRecvError::Disconnected) => {
                    return Err(io::Error::other("manager_supervisor_lost"));
                }
                Err(TryRecvError::Empty) => return Ok(()),
            }
        }
        if self.suspended {
            return Ok(());
        }
        let initial = self.first.then_some(StartKind::Manual);
        self.first = false;
        let collaborators = Collaborators {
            session: (self.activity)(),
            probe: Box::new(self.installed.clone()),
            versions: Box::new(self.installed.clone()),
            stop_signal: Box::new(PlatformStopSignal::default()),
        };
        if let Start::Running(running) = startup::start(
            self.installed.target.clone(),
            SupervisorConfig::default(),
            collaborators,
            &mut self.ownership,
            initial,
        )? {
            self.running = Some(running);
        }
        Ok(())
    }

    pub fn session_end(&mut self) {
        self.suspended = true;
        if let Some(running) = &mut self.running {
            running.handle.request(Request::SessionEnd);
            if running
                .ended
                .recv_timeout(Duration::from_millis(3500))
                .is_ok()
            {
                let _ = running.join();
                self.running = None;
            }
        }
    }

    pub fn cancel_session_end(&mut self) {
        // A still-settling supervisor must exit before a fresh one may start.
        self.suspended = false;
    }
}
