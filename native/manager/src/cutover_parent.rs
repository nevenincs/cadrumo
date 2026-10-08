//! Old-manager cutover ownership: the start claim is retained, never transferred.
use crate::{
    cutover::{Accepted, Designation, Handshake},
    cutover_windows::{self, RuntimeWitness},
    ipc::{self, Outcome, Request, Response},
    session::claim::StartClaim,
};
use cadrumo_application::installation::Selection;
use std::{
    io,
    os::windows::process::CommandExt,
    path::PathBuf,
    process::{Child, Command, Stdio},
    time::{Duration, Instant},
};

pub enum Progress {
    Waiting,
    Committed,
    RollbackReady,
}

pub struct Parent {
    selected: Selection,
    root: PathBuf,
    claim: Option<StartClaim>,
    child: Child,
    child_created: Option<u64>,
    server: Option<ipc::windows::Server>,
    handshake: Handshake,
    runtime: Option<RuntimeWitness>,
    cleanup: Vec<RuntimeWitness>,
    ready: bool,
    rollback: bool,
    deadline: Instant,
}
impl Parent {
    /// The caller already owns the start claim and confirmed the old runtime's
    /// idle stop. Its public endpoint and session lock have been released.
    pub fn launch(
        selected: Selection,
        root: PathBuf,
        previous: &str,
        claim: &mut Option<StartClaim>,
    ) -> io::Result<Self> {
        if claim.is_none() {
            return Err(io::ErrorKind::PermissionDenied.into());
        }
        let designation = Designation {
            parent_pid: std::process::id(),
            parent_version: previous.into(),
            nonce: cutover_windows::nonce()?,
        };
        let server =
            ipc::windows::Server::bind_cutover(&designation.endpoint(), &selected.manager)?;
        let child = Command::new(&selected.manager)
            .args(["--cutover", &designation.argument()])
            .env_clear()
            .envs(cadrumo_platform::storage::strict_host_environment(
                std::env::vars_os(),
            ))
            .current_dir(&selected.package)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x0800_0000)
            .spawn()?;
        // No launch exemption can be issued before this held direct child is observed.
        let child_created = crate::supervision::process::open_process(child.id())
            .ok()
            .map(|observed| observed.identity.created);
        let handshake = Handshake::new(child.id(), designation.nonce)?;
        Ok(Self {
            selected,
            root,
            claim: claim.take(),
            child,
            child_created,
            server: child_created.map(|_| server),
            handshake,
            runtime: None,
            cleanup: Vec::new(),
            ready: false,
            rollback: child_created.is_none(),
            deadline: Instant::now() + Duration::from_secs(240),
        })
    }
    pub fn version(&self) -> String {
        self.selected.version.map(|part| part.to_string()).join(".")
    }
    pub fn take_claim(&mut self) -> Option<StartClaim> {
        self.claim.take()
    }
    pub fn abort(&mut self) {
        self.rollback = true;
        self.server = None;
    }

    pub fn poll(&mut self) -> io::Result<Progress> {
        if !self.rollback {
            let mut server = self
                .server
                .take()
                .ok_or_else(|| io::Error::from(io::ErrorKind::BrokenPipe))?;
            let polled = server.poll_authenticated(|peer, request| self.handle(peer, request));
            self.server = Some(server);
            if self.ready && self.child.try_wait()?.is_none() {
                return Ok(Progress::Committed);
            }
            if polled.is_err()
                || self.child.try_wait()?.is_some()
                || Instant::now() >= self.deadline
            {
                self.rollback = true;
                if self.child.try_wait()?.is_none() {
                    self.child.kill()?;
                }
            }
        }
        if self.rollback {
            self.settle_rollback()
        } else {
            Ok(Progress::Waiting)
        }
    }
    fn handle(&mut self, peer: u32, request: Request) -> Response {
        let Request::SuccessorReady {
            runtime_pid,
            report: Some(report),
            ..
        } = request
        else {
            return Response {
                schema: 1,
                outcome: Outcome::DesignationRequired,
            };
        };
        if !matches!(self.child.try_wait(), Ok(None)) {
            return Response {
                schema: 1,
                outcome: Outcome::Unavailable,
            };
        }
        let runtime = &mut self.runtime;
        let parent = self.child.id();
        let Some(created) = self.child_created else {
            return Response {
                schema: 1,
                outcome: Outcome::DesignationRequired,
            };
        };
        let selected = &self.selected;
        let root = &self.root;
        let accepted = self
            .handshake
            .accept(peer, runtime_pid, &report, |pid, ready| {
                if !ready {
                    *runtime = Some(RuntimeWitness::hold(parent, created, pid, selected)?);
                    Ok(())
                } else {
                    let held = runtime
                        .as_mut()
                        .ok_or_else(|| io::Error::from(io::ErrorKind::PermissionDenied))?;
                    if held.pid() != pid {
                        return Err(io::ErrorKind::PermissionDenied.into());
                    }
                    held.ready(root, selected)
                }
            });
        let outcome = match accepted {
            Ok(Accepted::Claim) => Outcome::DesignationAccepted,
            Ok(Accepted::Launched) => Outcome::SuccessorObserved,
            Ok(Accepted::Ready) => Outcome::SuccessorReady,
            Ok(Accepted::Acknowledged) => {
                self.ready = true;
                Outcome::SuccessorReady
            }
            Err(_) => Outcome::DesignationRequired,
        };
        Response { schema: 1, outcome }
    }
    fn settle_rollback(&mut self) -> io::Result<Progress> {
        if self.child.try_wait()?.is_none() {
            self.child.kill()?;
            return Ok(Progress::Waiting);
        }
        // Admission never ran when native observation failed. Retain Child and
        // the start claim until its exit is confirmed, without a blocking wait.
        let Some(created) = self.child_created else {
            return Ok(Progress::RollbackReady);
        };
        if let Some(runtime) = self.runtime.take() {
            self.cleanup.push(runtime);
        }
        // The successor may die between CreateProcess and its launched report.
        // After confirmed exit it cannot create further children; retaining Child
        // prevents its PID being reused while the native parent relation is checked.
        for pid in cutover_windows::children(self.child.id())? {
            if self.cleanup.iter().any(|held| held.pid() == pid) {
                continue;
            }
            let opened = match crate::supervision::process::open_process(pid) {
                Ok(opened) => opened,
                Err(crate::supervision::process::InspectError::NotRunning) => continue,
                Err(_) => return Err(io::ErrorKind::PermissionDenied.into()),
            };
            if crate::ipc::windows::same_image(
                &opened.identity.image,
                &crate::supervision::launch::runtime_image(&self.selected.package),
            ) {
                if self.cleanup.len() >= 32 {
                    return Err(io::Error::other("manager_cutover_child_limit"));
                }
                self.cleanup.push(RuntimeWitness::hold(
                    self.child.id(),
                    created,
                    pid,
                    &self.selected,
                )?);
            }
        }
        let mut settled = true;
        for runtime in &mut self.cleanup {
            runtime.terminate()?;
            settled &= runtime.ended()?;
        }
        if !settled {
            return Ok(Progress::Waiting);
        }
        Ok(Progress::RollbackReady)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unobserved_child_cleanup_retains_claim_until_confirmed_exit() {
        let root = std::env::temp_dir().join(format!(
            "manager-cutover-parent-{}-{}",
            std::process::id(),
            cutover_windows::nonce().unwrap()
        ));
        crate::custody::ensure_local_directory(&root).unwrap();
        let claim = StartClaim::take(&root, Duration::ZERO).unwrap().unwrap();
        let image = PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32/cmd.exe");
        let child = Command::new(image)
            .args(["/D", "/Q", "/C", "pause"])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x0800_0000)
            .spawn()
            .unwrap();
        let mut parent = Parent {
            selected: Selection {
                entrypoint: root.join("manager.exe"),
                package: root.clone(),
                manager: root.join("manager.exe"),
                version: [2, 0, 0],
                lease: None,
                registration: None,
            },
            root: root.clone(),
            claim: Some(claim),
            handshake: Handshake::new(child.id(), cutover_windows::nonce().unwrap()).unwrap(),
            child,
            child_created: None,
            server: None,
            runtime: None,
            cleanup: Vec::new(),
            ready: false,
            rollback: true,
            deadline: Instant::now() + Duration::from_secs(10),
        };
        assert!(StartClaim::take(&root, Duration::ZERO).unwrap().is_none());
        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            let began = Instant::now();
            let progress = parent.poll().unwrap();
            assert!(began.elapsed() < Duration::from_secs(1));
            assert!(StartClaim::take(&root, Duration::ZERO).unwrap().is_none());
            if matches!(progress, Progress::RollbackReady) {
                break;
            }
            assert!(Instant::now() < deadline);
            std::thread::sleep(Duration::from_millis(5));
        }
        assert!(parent.child.try_wait().unwrap().is_some());
        drop(parent.take_claim());
        assert!(StartClaim::take(&root, Duration::ZERO).unwrap().is_some());
        drop(parent);
        std::fs::remove_dir_all(root).unwrap();
    }
}
