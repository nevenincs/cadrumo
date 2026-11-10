//! Coordinate Windows handle inheritance across application process creators.
//!
//! CreatePseudoConsole temporarily duplicates its pipe ends as inheritable.
//! A simultaneous std::process spawn can inherit them, keeping a closed
//! terminal's reader alive until that unrelated process exits. Rust's internal
//! spawn lock cannot coordinate with ConPTY. Both use this outer lock.
//!
//! Process creation is synchronous and cannot be cancelled: on a host that scans each
//! new program, one creation can take seconds, and a scan that hangs holds this lock for
//! as long as it hangs. [`spawn_within`] bounds how long a caller waits for its process.

use std::{
    io,
    process::{Child, Command},
    sync::{Arc, Condvar, Mutex, PoisonError},
    thread,
    time::Duration,
};

/// The longest a caller waits for one process to be created, its wait for the creation
/// step included. It is no budget of the program's, whose own budget starts once its
/// process exists. It only ends a wait for a creation that never finishes, so it leaves
/// room for a queue of creations that each take seconds on a host that scans every new
/// program.
pub const SPAWN_BUDGET: Duration = Duration::from_secs(120);

/// Run only the creation step here, including any temporary inheritable
/// handles. Release before waiting for output, readiness, or process exit.
/// Never nest calls. Other platforms need no Windows inheritance exclusion.
pub fn run<T>(create: impl FnOnce() -> T) -> T {
    #[cfg(windows)]
    let _guard = {
        static CREATION: std::sync::Mutex<()> = std::sync::Mutex::new(());
        CREATION.lock().unwrap_or_else(|error| error.into_inner())
    };
    create()
}

/// Why [`spawn_within`] returned no process.
#[derive(Debug)]
pub enum CreationFailure {
    /// The process could not be created, or no thread could be started to create it.
    Failed(io::Error),
    /// No process existed within the budget. Nothing created later is left running.
    TimedOut { budget: Duration },
}

/// Creates `command`'s process through [`run`] on a thread of its own and waits at most
/// `budget` for it. A process created after the wait has ended is killed and reaped on
/// that thread, which also closes its handles, so a creation that outlasts its caller
/// leaves nothing running. The caller never holds the creation step while it waits.
pub fn spawn_within(budget: Duration, mut command: Command) -> Result<Child, CreationFailure> {
    // The wait for the creation step counts against the budget: a creation that hangs
    // holds the step for good, so a wait that began only once the step was taken would
    // be unbounded again behind it.
    within(budget, move || run(|| command.spawn()), end)
}

/// Ends a process its caller no longer waits for: killed, then reaped. A process that
/// has already ended is only reaped.
fn end(mut child: Child) {
    let _ = child.kill();
    let _ = child.wait();
}

/// What the creating thread has handed over, or that its caller has stopped waiting.
enum Slot<T> {
    Waiting,
    Created(io::Result<T>),
    Abandoned,
}

/// Runs `create` on a thread of its own and waits at most `budget` for what it returns.
/// When the wait ends first, the thread hands what it creates later to `abandon`
/// instead of to the caller.
fn within<T: Send + 'static>(
    budget: Duration,
    create: impl FnOnce() -> io::Result<T> + Send + 'static,
    abandon: impl FnOnce(T) + Send + 'static,
) -> Result<T, CreationFailure> {
    let shared = Arc::new((Mutex::new(Slot::Waiting), Condvar::new()));
    let creating = Arc::clone(&shared);
    thread::Builder::new()
        .name("cadrumo-process-creation".into())
        .spawn(move || {
            let created = create();
            let (slot, handed) = &*creating;
            let mut slot = slot.lock().unwrap_or_else(PoisonError::into_inner);
            if matches!(*slot, Slot::Abandoned) {
                drop(slot);
                if let Ok(late) = created {
                    abandon(late);
                }
            } else {
                *slot = Slot::Created(created);
                handed.notify_one();
            }
        })
        .map_err(CreationFailure::Failed)?;
    let (slot, handed) = &*shared;
    let (mut slot, _) = handed
        .wait_timeout_while(
            slot.lock().unwrap_or_else(PoisonError::into_inner),
            budget,
            |slot| matches!(slot, Slot::Waiting),
        )
        .unwrap_or_else(PoisonError::into_inner);
    // Under the slot's lock the creating thread either has handed its value over or will
    // find the wait abandoned, so no value falls between the two.
    match std::mem::replace(&mut *slot, Slot::Abandoned) {
        Slot::Created(created) => created.map_err(CreationFailure::Failed),
        Slot::Waiting | Slot::Abandoned => Err(CreationFailure::TimedOut { budget }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{process::Stdio, sync::mpsc};

    /// Long enough that only a creation that never returns could exceed it.
    const GENEROUS: Duration = Duration::from_secs(60);

    #[test]
    fn a_creation_within_the_budget_is_handed_to_the_caller_and_never_abandoned() {
        let (abandoned, ended) = mpsc::channel();
        let created = within(
            GENEROUS,
            || Ok(7_u32),
            move |late| {
                let _ = abandoned.send(late);
            },
        );
        assert_eq!(created.unwrap(), 7);
        // The thread drops the abandoning step unused once it has handed the value over.
        assert_eq!(
            ended.recv_timeout(GENEROUS),
            Err(mpsc::RecvTimeoutError::Disconnected)
        );
    }

    #[test]
    fn a_refused_creation_reports_the_system_error() {
        let created = within(
            GENEROUS,
            || Err::<u32, _>(io::ErrorKind::PermissionDenied.into()),
            |_| {},
        );
        assert!(matches!(
            created,
            Err(CreationFailure::Failed(error)) if error.kind() == io::ErrorKind::PermissionDenied
        ));
    }

    #[test]
    fn a_creation_past_the_budget_times_out_and_what_it_creates_later_is_abandoned() {
        let (release, released) = mpsc::channel::<()>();
        let (abandoned, ended) = mpsc::channel();
        let budget = Duration::from_millis(20);
        let created = within(
            budget,
            move || {
                // Returns only once the caller has stopped waiting.
                let _ = released.recv();
                Ok(9_u32)
            },
            move |late| {
                let _ = abandoned.send(late);
            },
        );
        assert!(matches!(
            created,
            Err(CreationFailure::TimedOut { budget: reported }) if reported == budget
        ));
        release.send(()).unwrap();
        assert_eq!(ended.recv_timeout(GENEROUS), Ok(9));
    }

    #[test]
    fn a_process_created_within_the_budget_runs_for_its_caller() {
        let mut command = Command::new(std::env::current_exe().unwrap());
        command
            .args(["--list", "--exact", "no-such-test"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        let mut child = spawn_within(GENEROUS, command).unwrap();
        assert!(child.wait().unwrap().success());
    }
}
