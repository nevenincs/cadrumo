//! Who may run the local AI server and who may change its program, across processes.
//!
//! One supervisor runs the server on the installation's fixed address, and any engine may
//! replace or remove the program it runs from. Two operating-system locks under the
//! activity folder keep them apart, and the kernel releases each when its holder ends:
//!
//! - `local_ai.server.lock` is held by the supervisor for a server's whole life, from
//!   before it starts until after it has ended, and by an engine for as long as it
//!   changes the program. Holding it is the only way to do either, so a server never
//!   runs from files that are being replaced or removed.
//! - `local_ai.program.lock` is held by an engine while it changes the program. It is
//!   the engine's request: the supervisor never waits for it, but finds it held when it
//!   next looks, stops its server and releases the server lock, which is what the engine
//!   waits for. While the request stands the supervisor starts nothing.
//!
//! The engine takes the request first and the server lock second; the supervisor takes
//! the server lock and then looks for a request, giving the lock back when it finds one.
//! Neither ever waits while holding a lock the other needs, so neither can block the
//! other for longer than the supervisor takes to notice and stop its server. Lock files
//! stay in place, because unlinking one would let two holders lock two files.

use crate::{component::WriterLock, error::Error, filesystem};
use std::{
    fs::{self, File, TryLockError},
    path::{Path, PathBuf},
    sync::{Arc, Mutex, mpsc},
    time::Duration,
};

const SERVER_LOCK: &str = "local_ai.server.lock";
const PROGRAM_LOCK: &str = "local_ai.program.lock";

/// The longest an engine waits for the supervisor to stop its server before reporting
/// the program busy.
pub const PROGRAM_CHANGE_BUDGET: Duration = Duration::from_secs(60);

/// The two lock files, in the installation's activity folder.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Leases {
    root: PathBuf,
}

/// The supervisor's right to run a server; it ends when dropped.
pub struct ServerLease {
    _server: WriterLock,
}

/// An engine's right to replace or remove the program; no server runs while it lives.
pub struct ProgramChange {
    _server: WriterLock,
    _program: WriterLock,
}

impl std::fmt::Debug for ServerLease {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("ServerLease")
    }
}

impl std::fmt::Debug for ProgramChange {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("ProgramChange")
    }
}

impl Leases {
    /// The lock files under `activity`, the owner-resolved activity folder.
    pub fn new(activity: PathBuf) -> Result<Self, Error> {
        filesystem::absolute_root(&activity)?;
        Ok(Self { root: activity })
    }

    fn file(&self, name: &str) -> Result<File, Error> {
        filesystem::refuse_links(&self.root)?;
        fs::create_dir_all(&self.root)?;
        let path = self.root.join(name);
        filesystem::refuse_links(&path)?;
        Ok(File::options()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)?)
    }

    /// The supervisor's attempt to run a server, never waiting: `None` while an engine
    /// changes the program or asks to.
    pub fn try_serve(&self) -> Result<Option<ServerLease>, Error> {
        let server = self.file(SERVER_LOCK)?;
        match server.try_lock() {
            Ok(()) => {}
            Err(TryLockError::WouldBlock) => return Ok(None),
            Err(TryLockError::Error(error)) => return Err(error.into()),
        }
        let lease = ServerLease {
            _server: WriterLock(server),
        };
        if self.change_requested()? {
            return Ok(None);
        }
        Ok(Some(lease))
    }

    /// Whether an engine holds the program lock: it changes the program now, or waits to.
    pub fn change_requested(&self) -> Result<bool, Error> {
        let program = self.file(PROGRAM_LOCK)?;
        match program.try_lock_shared() {
            Ok(()) => {
                program.unlock()?;
                Ok(false)
            }
            Err(TryLockError::WouldBlock) => Ok(true),
            Err(TryLockError::Error(error)) => Err(error.into()),
        }
    }

    /// An engine's right to change the program: the request without waiting, `Busy` when
    /// another engine holds it, then the server lock once the supervisor has stopped its
    /// server. `requested` runs once the request stands and before the wait. A
    /// supervisor that has not given the lock up within `budget` leaves the program
    /// `Busy`; the request is withdrawn and the lock, if it arrives later, released.
    pub fn change_program(
        &self,
        budget: Duration,
        requested: &mut dyn FnMut(),
    ) -> Result<ProgramChange, Error> {
        let program = self.file(PROGRAM_LOCK)?;
        program.try_lock().map_err(|error| match error {
            TryLockError::WouldBlock => Error::Busy,
            TryLockError::Error(error) => Error::Io(error),
        })?;
        let program = WriterLock(program);
        let server = self.file(SERVER_LOCK)?;
        match server.try_lock() {
            Ok(()) => {
                return Ok(ProgramChange {
                    _server: WriterLock(server),
                    _program: program,
                });
            }
            Err(TryLockError::WouldBlock) => {}
            Err(TryLockError::Error(error)) => return Err(error.into()),
        }
        requested();
        let server = wait_for_lock(server, budget)?;
        Ok(ProgramChange {
            _server: server,
            _program: program,
        })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }
}

/// Waits for `file`'s lock on a thread of its own, so the wait is the kernel's and the
/// caller's bound still holds. A lock that arrives after the bound is released at once.
fn wait_for_lock(file: File, budget: Duration) -> Result<WriterLock, Error> {
    let (sender, receiver) = mpsc::channel::<std::io::Result<WriterLock>>();
    let waiting = Arc::new(Mutex::new(Some(sender)));
    let handoff = Arc::clone(&waiting);
    std::thread::Builder::new()
        .name("cadrumo-local-ai-lease".into())
        .spawn(move || {
            let result = file.lock().map(|()| WriterLock(file));
            let sender = handoff
                .lock()
                .unwrap_or_else(|error| error.into_inner())
                .take();
            // Without a waiting caller the lock, if taken, is released as it drops here.
            if let Some(sender) = sender {
                let _ = sender.send(result);
            }
        })?;
    match receiver.recv_timeout(budget) {
        Ok(result) => Ok(result?),
        Err(_) => {
            drop(
                waiting
                    .lock()
                    .unwrap_or_else(|error| error.into_inner())
                    .take(),
            );
            // The waiter may have handed the lock over before the withdrawal.
            match receiver.try_recv() {
                Ok(result) => Ok(result?),
                Err(_) => Err(Error::Busy),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn leases() -> (tempfile::TempDir, Leases) {
        let directory = tempfile::tempdir().unwrap();
        let leases = Leases::new(directory.path().join("activity")).unwrap();
        (directory, leases)
    }

    #[test]
    fn one_server_at_a_time_and_none_while_the_program_changes() {
        let (_directory, leases) = leases();
        let lease = leases
            .try_serve()
            .unwrap()
            .expect("nothing holds the lease");
        assert!(leases.try_serve().unwrap().is_none(), "a second server");
        assert!(!leases.change_requested().unwrap());
        drop(lease);

        let change = leases
            .change_program(PROGRAM_CHANGE_BUDGET, &mut || {
                panic!("no server runs, so nothing is waited for")
            })
            .unwrap();
        assert!(leases.change_requested().unwrap());
        assert!(leases.try_serve().unwrap().is_none());
        assert!(matches!(
            leases.change_program(PROGRAM_CHANGE_BUDGET, &mut || {}),
            Err(Error::Busy)
        ));
        drop(change);
        assert!(!leases.change_requested().unwrap());
        assert!(leases.try_serve().unwrap().is_some());
    }

    #[test]
    fn a_change_waits_for_the_running_server_to_end_and_the_supervisor_sees_the_request() {
        let (_directory, leases) = leases();
        let lease = leases.try_serve().unwrap().unwrap();
        let (requested, request_seen) = mpsc::channel();
        let engine = {
            let leases = leases.clone();
            std::thread::spawn(move || {
                leases
                    .change_program(PROGRAM_CHANGE_BUDGET, &mut || {
                        requested.send(()).unwrap();
                    })
                    .unwrap()
            })
        };
        request_seen.recv().unwrap();
        assert!(leases.change_requested().unwrap());
        assert!(
            !engine.is_finished(),
            "the engine holds no change while the server runs"
        );
        drop(lease);
        let change = engine.join().unwrap();
        assert!(leases.try_serve().unwrap().is_none());
        drop(change);
        assert!(leases.try_serve().unwrap().is_some());
    }

    #[test]
    fn a_supervisor_that_never_yields_leaves_the_program_busy_and_withdraws_the_request() {
        let (_directory, leases) = leases();
        let lease = leases.try_serve().unwrap().unwrap();
        assert!(matches!(
            leases.change_program(Duration::ZERO, &mut || {}),
            Err(Error::Busy)
        ));
        assert!(!leases.change_requested().unwrap(), "the request stood");
        drop(lease);
        // The abandoned waiter takes the lock and releases it at once, or never took it.
        let (taken, released) = mpsc::channel();
        let engine = {
            let leases = leases.clone();
            std::thread::spawn(move || {
                let change = leases.change_program(PROGRAM_CHANGE_BUDGET, &mut || {});
                taken.send(()).unwrap();
                change
            })
        };
        released.recv().unwrap();
        assert!(engine.join().unwrap().is_ok());
    }
}
