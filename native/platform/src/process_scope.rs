//! A process scope on Linux and macOS: a process group that ends with its owner, however
//! the owner ends.
//!
//! Neither system has the kill-on-close job Windows contains processes with. A scope is a
//! guardian: a shell process, started by the owner in a new process group of its own,
//! that only waits for its standard input to end and then kills its whole group, itself
//! included. The owner holds the only writing end of that input, so it ends when the owner
//! drops the scope, exits, crashes or is killed, because the kernel closes the descriptors
//! of a process that ends. A process the owner creates into the scope's group (see
//! [`ProcessScope::join`]) joins it before any of its code runs, and what that process
//! starts stays in the group unless it moves itself out.
//!
//! The group's id is the guardian's process id, which stays reserved for as long as the
//! guardian lives, so the kill can never reach a group that reused the id.
//!
//! Limits: a descendant that leaves the group (`setsid`, `setpgid`) is not reached, and
//! nothing is contained once the guardian itself has been killed. On macOS a process
//! another thread starts at the instant the scope's pipe is created may inherit its
//! writing end before it is marked close-on-exec, which delays the scope's end until that
//! process ends; Linux creates the pipe close-on-exec atomically.

use std::{
    fs, io,
    os::unix::{fs::MetadataExt, process::CommandExt},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{Mutex, OnceLock},
    thread,
    time::{Duration, Instant},
};

const SHELL: &str = "/bin/sh";

/// Ignores the terminal's signals, waits for the end of its input, then kills its group.
/// It reads nothing it acts on, writes nothing and starts no process.
const GUARDIAN: &str = "trap '' HUP INT QUIT TSTP TTIN TTOU\n\
                        while IFS= read -r _; do :; done\n\
                        kill -s KILL 0\n";

/// One process group whose members end when the scope is dropped or its owner ends.
#[derive(Debug)]
pub struct ProcessScope {
    group: i32,
    lifeline: Mutex<Option<ChildStdin>>,
    guardian: Mutex<Child>,
}

impl ProcessScope {
    /// Starts the guardian of a new, empty group.
    pub fn new() -> io::Result<Self> {
        trusted_system_file(SHELL)?;
        let mut guardian = Command::new(SHELL)
            .args(["-c", GUARDIAN])
            .env_clear()
            .current_dir("/")
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .process_group(0)
            .spawn()?;
        let lifeline = guardian.stdin.take();
        let group = i32::try_from(guardian.id());
        let (Some(lifeline), Ok(group)) = (lifeline, group) else {
            let _ = guardian.kill();
            let _ = guardian.wait();
            return Err(io::ErrorKind::InvalidData.into());
        };
        Ok(Self {
            group,
            lifeline: Mutex::new(Some(lifeline)),
            guardian: Mutex::new(guardian),
        })
    }

    /// The scope's process group id.
    pub fn group(&self) -> i32 {
        self.group
    }

    /// Creates `command`'s process in the scope's group; refused once the guardian has
    /// ended, so nothing starts in a group no guardian keeps.
    pub fn join(&self, command: &mut Command) -> io::Result<()> {
        if !matches!(self.guardian().try_wait(), Ok(None)) {
            return Err(io::ErrorKind::BrokenPipe.into());
        }
        command.process_group(self.group);
        Ok(())
    }

    /// Ends every process in the scope now and returns once none is left, within
    /// `bound`. The scope admits no member afterwards.
    ///
    /// The guardian kills the group and itself; this waits for it, then until no
    /// process of the group still runs. A member that left the group is not waited for,
    /// and one the kernel has not finished ending past `bound` is reported as a timeout.
    /// Where the kernel still counts an exited member until its parent reaps it, the
    /// caller's own unreaped child keeps the group from settling.
    pub fn terminate(&self, bound: Duration) -> io::Result<()> {
        let deadline = Instant::now() + bound;
        drop(
            self.lifeline
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .take(),
        );
        self.guardian().wait()?;
        loop {
            // SAFETY: signal 0 only probes for a process of the group and delivers nothing.
            if unsafe { libc::killpg(self.group, 0) } != 0 {
                let error = io::Error::last_os_error();
                return match error.raw_os_error() {
                    Some(libc::ESRCH) => Ok(()),
                    // Darwin refuses the probe once every member left has exited and
                    // only awaits reaping by its parent.
                    #[cfg(target_os = "macos")]
                    Some(libc::EPERM) => Ok(()),
                    _ => Err(error),
                };
            }
            if Instant::now() >= deadline {
                return Err(io::ErrorKind::TimedOut.into());
            }
            thread::sleep(Duration::from_millis(10));
        }
    }

    fn guardian(&self) -> std::sync::MutexGuard<'_, Child> {
        self.guardian
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }
}

impl Drop for ProcessScope {
    /// Ends every process left in the group and waits for the guardian to have done so.
    fn drop(&mut self) {
        drop(
            self.lifeline
                .lock()
                .unwrap_or_else(|poisoned| poisoned.into_inner())
                .take(),
        );
        let _ = self.guardian().wait();
    }
}

static CURRENT: OnceLock<ProcessScope> = OnceLock::new();

/// Gives this process a scope for its children for the rest of its life, so a child
/// created into it ends with this process however it ends. A second call keeps the first
/// scope.
pub fn contain_current() -> io::Result<&'static ProcessScope> {
    if let Some(scope) = CURRENT.get() {
        return Ok(scope);
    }
    let scope = ProcessScope::new()?;
    // A scope that lost a race to be set is dropped, which ends its empty group.
    Ok(CURRENT.get_or_init(|| scope))
}

/// The scope [`contain_current`] gave this process, when it has one.
pub fn current() -> Option<&'static ProcessScope> {
    CURRENT.get()
}

/// Refuses a program the guardian would run unless root owns it and only root may change
/// it.
fn trusted_system_file(path: &str) -> io::Result<()> {
    let metadata = fs::metadata(path)?;
    if !metadata.is_file() || metadata.uid() != 0 || metadata.mode() & 0o022 != 0 {
        return Err(io::ErrorKind::PermissionDenied.into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{BufRead, BufReader, Read},
        os::unix::process::ExitStatusExt,
    };

    /// A member that never ends by itself: it stops itself again whenever it is resumed
    /// and ignores the hangup an orphaned group is sent, so only a kill ends it. The first
    /// one starts a second; each says which it is on its standard output.
    const UNENDING: &str = "trap '' HUP\n\
                            if [ \"$1\" = member ]; then /bin/sh -c \"$0\" \"$0\" descendant & fi\n\
                            echo \"$1\"\n\
                            while :; do kill -s STOP $$; done\n";

    fn member(stdout: Stdio) -> Command {
        let mut command = Command::new(SHELL);
        command
            .args(["-c", UNENDING, UNENDING, "member"])
            .stdin(Stdio::null())
            .stdout(stdout)
            .stderr(Stdio::null());
        command
    }

    fn both_running(stdout: &mut impl BufRead) {
        let mut seen = String::new();
        while !(seen.contains("member\n") && seen.contains("descendant\n")) {
            let mut line = String::new();
            assert_ne!(
                stdout.read_line(&mut line).unwrap(),
                0,
                "the members ended before they ran: {seen}"
            );
            seen.push_str(&line);
        }
    }

    /// Returns once every process holding `stdout` has ended.
    fn every_holder_ended(stdout: &mut impl BufRead) {
        let mut rest = Vec::new();
        stdout.read_to_end(&mut rest).unwrap();
    }

    #[test]
    fn a_dropped_scope_ends_its_members_and_what_they_started() {
        let scope = ProcessScope::new().unwrap();
        assert_ne!(scope.group(), 0);
        let (reader, writer) = io::pipe().unwrap();
        let mut command = member(writer.into());
        scope.join(&mut command).unwrap();
        let mut started = command.spawn().unwrap();
        drop(command);
        let mut stdout = BufReader::new(reader);
        both_running(&mut stdout);
        drop(scope);
        every_holder_ended(&mut stdout);
        assert_eq!(started.wait().unwrap().signal(), Some(9));
    }

    #[test]
    fn a_terminated_scope_is_empty_when_terminate_returns_and_admits_no_member() {
        let scope = ProcessScope::new().unwrap();
        let (reader, writer) = io::pipe().unwrap();
        let mut command = member(writer.into());
        scope.join(&mut command).unwrap();
        let mut started = command.spawn().unwrap();
        drop(command);
        let mut stdout = BufReader::new(reader);
        both_running(&mut stdout);
        scope.terminate(Duration::from_secs(10)).unwrap();
        // Nothing of the group runs any more: its output has no writer left.
        every_holder_ended(&mut stdout);
        assert_eq!(started.wait().unwrap().signal(), Some(9));
        // Once reaped, by this test and by whoever adopted the descendant, the group
        // is gone altogether.
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            // SAFETY: a probe of the scope's group, which delivers nothing.
            assert_eq!(unsafe { libc::killpg(scope.group(), 0) }, -1);
            let probe = io::Error::last_os_error().raw_os_error();
            if probe == Some(libc::ESRCH) {
                break;
            }
            assert!(Instant::now() < deadline, "{probe:?}");
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(
            scope.join(&mut member(Stdio::null())).unwrap_err().kind(),
            io::ErrorKind::BrokenPipe
        );
    }

    #[test]
    fn a_scope_whose_guardian_ended_admits_no_member() {
        let scope = ProcessScope::new().unwrap();
        let mut guardian = scope.guardian();
        guardian.kill().unwrap();
        guardian.wait().unwrap();
        drop(guardian);
        let mut command = member(Stdio::null());
        assert_eq!(
            scope.join(&mut command).unwrap_err().kind(),
            io::ErrorKind::BrokenPipe
        );
    }

    const OWNER_HELPER: &str = "CADRUMO_PLATFORM_SCOPE_OWNER";

    /// The child-process mode: a process that contains itself, starts a member into its
    /// scope, and holds it until its standard input closes, then exits.
    #[test]
    fn scope_owner_helper() {
        if std::env::var_os(OWNER_HELPER).is_none() {
            return;
        }
        let scope = contain_current().unwrap();
        assert_eq!(current().map(ProcessScope::group), Some(scope.group()));
        assert_eq!(contain_current().unwrap().group(), scope.group());
        let mut command = member(Stdio::inherit());
        scope.join(&mut command).unwrap();
        let _member = command.spawn().unwrap();
        let mut sink = Vec::new();
        let _ = io::stdin().read_to_end(&mut sink);
        std::process::exit(0);
    }

    fn owner() -> Child {
        Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "process_scope::tests::scope_owner_helper",
                "--nocapture",
                "--test-threads=1",
            ])
            .env(OWNER_HELPER, "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .unwrap()
    }

    #[test]
    fn members_end_when_their_owner_is_killed() {
        let mut owner = owner();
        let mut stdout = BufReader::new(owner.stdout.take().unwrap());
        both_running(&mut stdout);
        owner.kill().unwrap();
        owner.wait().unwrap();
        every_holder_ended(&mut stdout);
    }

    #[test]
    fn members_end_when_their_owner_exits() {
        let mut owner = owner();
        let mut stdout = BufReader::new(owner.stdout.take().unwrap());
        both_running(&mut stdout);
        drop(owner.stdin.take());
        assert!(owner.wait().unwrap().success());
        every_holder_ended(&mut stdout);
    }
}
