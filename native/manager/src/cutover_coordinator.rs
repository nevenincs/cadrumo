//! Poll-driven Windows upgrade orchestration. Inventory work runs off the UI thread.
use crate::{
    cutover_parent::{Parent, Progress},
    failed_versions::FailedVersions,
    ipc::windows::Server,
    session::{
        claim::StartClaim,
        instance::{SessionLock, claim_session},
    },
};
use cadrumo_application::{component::Cancellation, installation::Selection};
use std::{
    io,
    path::Path,
    sync::{
        Arc,
        mpsc::{self, Receiver},
    },
    time::{Duration, Instant},
};

pub trait Runtime {
    fn root(&self) -> Option<&Path> {
        None
    }
    fn can_cutover(&self) -> bool {
        false
    }
    fn stopping(&self) -> bool {
        false
    }
    fn resume_session(&mut self) {}
    fn begin_cutover(&mut self) -> io::Result<Option<StartClaim>> {
        Ok(None)
    }
    fn idle_stopped(&self) -> bool {
        false
    }
    fn retry_idle(&self) {}
    fn abandon_cutover(&mut self) {}
    fn rollback(&mut self, _claim: StartClaim) {}
}
impl Runtime for crate::background::Background {
    fn root(&self) -> Option<&Path> {
        Some(self.storage_root())
    }
    fn can_cutover(&self) -> bool {
        self.can_cutover()
    }
    fn stopping(&self) -> bool {
        self.stopping()
    }
    fn resume_session(&mut self) {
        self.cancel_session_end();
    }
    fn begin_cutover(&mut self) -> io::Result<Option<StartClaim>> {
        self.begin_cutover()
    }
    fn idle_stopped(&self) -> bool {
        self.idle_stopped()
    }
    fn retry_idle(&self) {
        self.retry_idle();
    }
    fn abandon_cutover(&mut self) {
        self.abandon_cutover();
    }
    fn rollback(&mut self, claim: StartClaim) {
        self.rollback(claim);
    }
}

pub struct Coordinator {
    current: Selection,
    next: Instant,
    query: Option<Receiver<io::Result<Option<Selection>>>>,
    cancellation: Arc<Cancellation>,
    candidate: Option<Selection>,
    claim: Option<StartClaim>,
    parent: Option<Parent>,
    recovering: Option<String>,
    deadline: Instant,
    idle_retry: Instant,
    notice: Option<&'static str>,
    announced: Option<[u32; 3]>,
    cancelled: bool,
    resume_requested: bool,
}
impl Coordinator {
    pub fn new(current: Selection) -> Self {
        Self {
            current,
            next: Instant::now(),
            query: None,
            cancellation: Arc::new(Cancellation::default()),
            candidate: None,
            claim: None,
            parent: None,
            recovering: None,
            deadline: Instant::now(),
            idle_retry: Instant::now(),
            notice: None,
            announced: None,
            cancelled: false,
            resume_requested: false,
        }
    }
    pub fn take_notice(&mut self) -> Option<&'static str> {
        self.notice.take()
    }
    pub fn cancel(&mut self) {
        self.cancelled = true;
        self.resume_requested = false;
        self.cancellation.cancel();
        if let Some(parent) = &mut self.parent {
            parent.abort();
        }
    }
    pub fn resume(&mut self) {
        self.resume_requested = true;
    }
    pub fn unsettled(&self) -> bool {
        self.parent.is_some() || self.claim.is_some()
    }
    pub fn poll(
        &mut self,
        runtime: &mut dyn Runtime,
        session: &mut Option<SessionLock>,
        ipc: &mut Option<Server>,
    ) -> io::Result<bool> {
        if runtime.stopping() && !self.cancelled {
            self.cancel();
        }
        if self.cancelled {
            if let Some(parent) = &mut self.parent {
                match parent.poll()? {
                    Progress::RollbackReady => self.parent = None,
                    Progress::Waiting => return Ok(false),
                    Progress::Committed => return Err(io::ErrorKind::InvalidData.into()),
                }
            }
            if self.resume_requested {
                if session.is_none() {
                    *session = claim_session(crate::identity::MANAGER_ID, Duration::ZERO)?;
                    if session.is_none() {
                        return Ok(false);
                    }
                }
                if ipc.is_none() {
                    *ipc = Some(Server::bind_installed(&self.current.package)?);
                }
            }
            self.claim = None;
            self.recovering = None;
            self.candidate = None;
            runtime.abandon_cutover();
            if self.resume_requested {
                runtime.resume_session();
                self.resume_requested = false;
                self.cancelled = false;
                self.cancellation = Arc::new(Cancellation::default());
                self.next = Instant::now() + Duration::from_secs(60);
            }
            return Ok(false);
        }
        if let Some(release) = &self.recovering {
            let root = runtime
                .root()
                .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?;
            let previous = self.current.version.map(|part| part.to_string()).join(".");
            FailedVersions::record(root, release, &previous)?;
            if session.is_none() {
                *session = claim_session(crate::identity::MANAGER_ID, Duration::ZERO)?;
            }
            if session.is_none() {
                return Ok(false);
            }
            if ipc.is_none() {
                *ipc = Some(Server::bind_installed(&self.current.package)?);
            }
            runtime.rollback(
                self.claim
                    .take()
                    .ok_or_else(|| io::Error::from(io::ErrorKind::PermissionDenied))?,
            );
            self.recovering = None;
            self.candidate = None;
            self.notice = Some("update_failed_notice");
            return Ok(false);
        }
        if let Some(parent) = &mut self.parent {
            match parent.poll()? {
                Progress::Committed => return Ok(true),
                Progress::Waiting => return Ok(false),
                Progress::RollbackReady => {
                    let root = runtime
                        .root()
                        .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?;
                    let previous = self.current.version.map(|part| part.to_string()).join(".");
                    FailedVersions::record(root, &parent.version(), &previous)?;
                    if session.is_none() {
                        *session = claim_session(crate::identity::MANAGER_ID, Duration::ZERO)?;
                        if session.is_none() {
                            return Ok(false);
                        }
                    }
                    if ipc.is_none() {
                        *ipc = Some(Server::bind_installed(&self.current.package)?);
                    }
                    let claim = parent
                        .take_claim()
                        .ok_or_else(|| io::Error::from(io::ErrorKind::PermissionDenied))?;
                    runtime.rollback(claim);
                    self.parent = None;
                    self.notice = Some("update_failed_notice");
                    return Ok(false);
                }
            }
        }
        if self.claim.is_some() {
            if runtime.idle_stopped() {
                ipc.take();
                session.take();
                let selected = self
                    .candidate
                    .take()
                    .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?;
                let release = selected.version.map(|part| part.to_string()).join(".");
                let previous = self.current.version.map(|part| part.to_string()).join(".");
                let root = runtime
                    .root()
                    .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?
                    .to_path_buf();
                self.recovering = Some(release.clone());
                match Parent::launch(selected, root.clone(), &previous, &mut self.claim) {
                    Ok(parent) => {
                        self.parent = Some(parent);
                        self.recovering = None;
                    }
                    Err(error) => {
                        // No child was authorized. Keep the claim while restoring our
                        // ordinary session endpoint and the previously running version.
                        FailedVersions::record(&root, &release, &previous)?;
                        *session = claim_session(crate::identity::MANAGER_ID, Duration::ZERO)?;
                        if session.is_none() {
                            return Err(error);
                        }
                        *ipc = Some(Server::bind_installed(&self.current.package)?);
                        runtime.rollback(
                            self.claim
                                .take()
                                .ok_or_else(|| io::Error::from(io::ErrorKind::PermissionDenied))?,
                        );
                        self.recovering = None;
                        self.notice = Some("update_failed_notice");
                    }
                }
                return Ok(false);
            }
            if Instant::now() >= self.deadline {
                runtime.abandon_cutover();
                self.claim = None;
                self.candidate = None;
                self.notice = Some("update_deferred");
                self.next = Instant::now() + Duration::from_secs(60);
            } else if Instant::now() >= self.idle_retry {
                runtime.retry_idle();
                self.idle_retry = Instant::now() + Duration::from_secs(5);
            }
            return Ok(false);
        }
        if let Some(candidate) = &self.candidate {
            let root = runtime
                .root()
                .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidData))?;
            let release = candidate.version.map(|part| part.to_string()).join(".");
            if FailedVersions::read(root)?.contains(&release) {
                self.candidate = None;
                return Ok(false);
            }
            if runtime.can_cutover() && self.announced != Some(candidate.version) {
                self.announced = Some(candidate.version);
                self.notice = Some("update_pending");
                return Ok(false);
            }
            if runtime.can_cutover()
                && let Some(claim) = runtime.begin_cutover()?
            {
                self.claim = Some(claim);
                self.deadline = Instant::now() + Duration::from_secs(600);
                self.idle_retry = Instant::now() + Duration::from_secs(5);
            }
            return Ok(false);
        }
        if let Some(query) = &self.query {
            match query.try_recv() {
                Ok(result) => {
                    self.query = None;
                    self.next = Instant::now() + Duration::from_secs(30);
                    self.candidate = result?;
                }
                Err(mpsc::TryRecvError::Disconnected) => {
                    self.query = None;
                    self.next = Instant::now() + Duration::from_secs(30);
                }
                Err(mpsc::TryRecvError::Empty) => {}
            }
        }
        if self.query.is_none() && self.candidate.is_none() && Instant::now() >= self.next {
            let selected = self.current.clone();
            let cancellation = self.cancellation.clone();
            let (send, receive) = mpsc::sync_channel(1);
            std::thread::Builder::new()
                .name("manager-version-discovery".into())
                .spawn(move || {
                    let _ = send.send(crate::installation::newer(&selected, &cancellation));
                })?;
            self.query = Some(receive);
        }
        Ok(false)
    }
}
impl Drop for Coordinator {
    fn drop(&mut self) {
        self.cancellation.cancel();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    struct Busy {
        root: std::path::PathBuf,
        abandoned: bool,
    }
    impl Runtime for Busy {
        fn root(&self) -> Option<&Path> {
            Some(&self.root)
        }
        fn abandon_cutover(&mut self) {
            self.abandoned = true;
        }
    }
    #[test]
    fn busy_deferral_and_cancel_release_only_the_reservation_without_launch() {
        let root = std::env::temp_dir().join(format!(
            "manager-cutover-coordinator-{}-{}",
            std::process::id(),
            crate::cutover_windows::nonce().unwrap()
        ));
        crate::custody::ensure_local_directory(&root).unwrap();
        let current = Selection {
            entrypoint: root.join("manager.exe"),
            package: root.clone(),
            manager: root.join("manager.exe"),
            version: [1, 0, 0],
            lease: None,
            registration: None,
        };
        let mut coordinator = Coordinator::new(current);
        let mut runtime = Busy {
            root: root.clone(),
            abandoned: false,
        };
        coordinator.claim = StartClaim::take(&root, Duration::ZERO).unwrap();
        coordinator.deadline = Instant::now() + Duration::from_secs(10);
        assert!(
            !coordinator
                .poll(&mut runtime, &mut None, &mut None)
                .unwrap()
        );
        assert!(coordinator.unsettled());
        assert!(StartClaim::take(&root, Duration::ZERO).unwrap().is_none());
        coordinator.deadline = Instant::now();
        assert!(
            !coordinator
                .poll(&mut runtime, &mut None, &mut None)
                .unwrap()
        );
        assert!(runtime.abandoned);
        assert!(!coordinator.unsettled());
        assert_eq!(coordinator.take_notice(), Some("update_deferred"));
        coordinator.claim = StartClaim::take(&root, Duration::ZERO).unwrap();
        coordinator.cancel();
        assert!(coordinator.unsettled());
        assert!(
            !coordinator
                .poll(&mut runtime, &mut None, &mut None)
                .unwrap()
        );
        assert!(!coordinator.unsettled());
        assert!(StartClaim::take(&root, Duration::ZERO).unwrap().is_some());
        drop(coordinator);
        std::fs::remove_dir_all(root).unwrap();
    }
}
