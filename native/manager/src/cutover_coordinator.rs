//! Poll-driven Windows upgrade orchestration. Inventory work runs off the UI thread.
use crate::{
    cutover_parent::{Parent, Progress},
    failed_versions::FailedVersions,
    ipc::windows::Server,
    lifecycle::CutoverRuntime,
    session::{
        claim::StartClaim,
        instance::{SessionLock, claim_session},
    },
};
use cadrumo_application::{component::Cancellation, installation::Selection};
use std::{
    io,
    sync::{
        Arc,
        mpsc::{self, Receiver},
    },
    time::{Duration, Instant},
};

// Pacing: a cutover child's progress and a refused session claim publish no
// notification to this thread.
const ACTIVE_PACE: Duration = Duration::from_millis(250);
// Pacing: a pending candidate waits for cutover eligibility, which includes a
// blocked runtime's process exit and a contended start claim.
const CANDIDATE_PACE: Duration = Duration::from_secs(1);

// Pacing: a deferred or resumed update looks for the same candidate again
// after this delay, since nothing it waits on publishes a change.
const REDISCOVERY_DELAY: Duration = Duration::from_secs(60);

pub struct Coordinator {
    current: Selection,
    /// The root-scoped session lock and IPC name this manager retakes after a cutover.
    manager_id: String,
    /// When discovery is next due without a change to the versions directory.
    next: Option<Instant>,
    /// The versions directory and everything published below it.
    versions: crate::change_watch::ChangeWatch,
    versions_changed: bool,
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
    notify: crate::wake::Slot,
}
impl Coordinator {
    pub fn new(current: Selection, manager_id: String) -> Self {
        let mut versions = crate::change_watch::ChangeWatch::default();
        if let Some(directory) = versions_directory(&current) {
            versions.directory(directory, true);
        }
        Self {
            current,
            manager_id,
            next: Some(Instant::now()),
            versions,
            versions_changed: false,
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
            notify: crate::wake::Slot::default(),
        }
    }
    /// Signal `notify` when a version discovery query finishes.
    pub fn notify_with(&self, notify: crate::wake::Notify) {
        self.notify.install(notify);
    }
    /// When the next poll is due. A discovery query in flight notifies instead,
    /// and so does a version published while none is.
    pub fn readiness<'a>(
        &'a self,
        runtime: &dyn CutoverRuntime,
        into: &mut crate::wake::windows::Readiness<'a>,
    ) {
        // Every poll takes these changes first, so a signaled one never repeats.
        self.versions.readiness(into);
        if runtime.stopping() && !self.cancelled {
            into.now();
            return;
        }
        if self.cancelled {
            // Without a child or a resumption, one poll releases the rest.
            if self.parent.is_some() || self.resume_requested {
                into.after(ACTIVE_PACE);
            } else if self.claim.is_some() || self.recovering.is_some() || self.candidate.is_some()
            {
                into.now();
            }
            return;
        }
        if self.recovering.is_some() || self.parent.is_some() {
            into.after(ACTIVE_PACE);
        } else if self.claim.is_some() {
            into.at(self.deadline);
            into.at(self.idle_retry);
        } else if self.candidate.is_some() {
            into.after(CANDIDATE_PACE);
        } else if self.query.is_none()
            && let Some(next) = self.next
        {
            into.at(next);
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
        runtime: &mut dyn CutoverRuntime,
        session: &mut Option<SessionLock>,
        ipc: &mut Option<Server>,
    ) -> io::Result<bool> {
        self.versions_changed |= self.versions.take();
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
                    *session = claim_session(&self.manager_id, Duration::ZERO)?;
                    if session.is_none() {
                        return Ok(false);
                    }
                }
                if ipc.is_none() {
                    *ipc = Some(Server::bind_installed(
                        &self.current.package,
                        &self.manager_id,
                    )?);
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
                self.next = Some(Instant::now() + REDISCOVERY_DELAY);
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
                *session = claim_session(&self.manager_id, Duration::ZERO)?;
            }
            if session.is_none() {
                return Ok(false);
            }
            if ipc.is_none() {
                *ipc = Some(Server::bind_installed(
                    &self.current.package,
                    &self.manager_id,
                )?);
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
                        *session = claim_session(&self.manager_id, Duration::ZERO)?;
                        if session.is_none() {
                            return Ok(false);
                        }
                    }
                    if ipc.is_none() {
                        *ipc = Some(Server::bind_installed(
                            &self.current.package,
                            &self.manager_id,
                        )?);
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
                        *session = claim_session(&self.manager_id, Duration::ZERO)?;
                        if session.is_none() {
                            return Err(error);
                        }
                        *ipc = Some(Server::bind_installed(
                            &self.current.package,
                            &self.manager_id,
                        )?);
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
                self.next = Some(Instant::now() + REDISCOVERY_DELAY);
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
                    self.next = None;
                    self.candidate = result?;
                }
                Err(mpsc::TryRecvError::Disconnected) => {
                    self.query = None;
                    self.next = None;
                }
                Err(mpsc::TryRecvError::Empty) => {}
            }
        }
        if self.query.is_none()
            && self.candidate.is_none()
            && (self.versions_changed || self.next.is_some_and(|next| Instant::now() >= next))
        {
            self.versions_changed = false;
            self.next = None;
            let selected = self.current.clone();
            let cancellation = self.cancellation.clone();
            let (send, receive) = mpsc::sync_channel(1);
            let notify = self.notify.clone();
            std::thread::Builder::new()
                .name("manager-version-discovery".into())
                .spawn(move || {
                    // Dropped after the sender, so a woken consumer observes the
                    // result or the disconnection.
                    let _notify = crate::wake::NotifyOnDrop(notify);
                    let send = send;
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

fn versions_directory(current: &Selection) -> Option<std::path::PathBuf> {
    let contract: cadrumo_application::installation::DiscoveryContract =
        serde_json::from_str(crate::contract::INSTALLATION_CONTRACT).ok()?;
    let prefix = current.entrypoint.parent()?;
    Some(contract.layout.installation.versions.under(prefix))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    struct Busy {
        root: std::path::PathBuf,
        abandoned: bool,
    }
    impl CutoverRuntime for Busy {
        fn root(&self) -> Option<&Path> {
            Some(&self.root)
        }
        fn abandon_cutover(&mut self) {
            self.abandoned = true;
        }
    }
    /// Poll once the coordinator's own readiness ends its wait, bounded by `bound`.
    fn poll_when_ready(coordinator: &mut Coordinator, runtime: &mut Busy, bound: Duration) {
        {
            let mut readiness = crate::wake::windows::Readiness::default();
            coordinator.readiness(&*runtime, &mut readiness);
            readiness.after(bound);
            readiness.wait().unwrap();
        }
        assert!(!coordinator.poll(runtime, &mut None, &mut None).unwrap());
    }

    #[test]
    fn a_published_version_starts_discovery_and_nothing_else_does() {
        let root = std::env::temp_dir().join(format!(
            "manager-cutover-discovery-{}-{}",
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
        let versions = versions_directory(&current).unwrap();
        std::fs::create_dir_all(&versions).unwrap();
        let mut coordinator = Coordinator::new(current, "test.cadrumo.coordinator.manager".into());
        let finished = crate::wake::windows::Event::new().unwrap();
        coordinator.notify_with(finished.notifier());
        let mut runtime = Busy {
            root: root.clone(),
            abandoned: false,
        };
        // The first poll discovers once; an empty versions directory names no candidate.
        assert!(
            !coordinator
                .poll(&mut runtime, &mut None, &mut None)
                .unwrap()
        );
        assert!(coordinator.query.is_some());
        while coordinator.query.is_some() {
            poll_when_ready(&mut coordinator, &mut runtime, Duration::from_secs(10));
        }
        assert!(coordinator.candidate.is_none());
        assert_eq!(coordinator.next, None, "no interval discovery is pending");
        // Nothing published: the wait ends only at its own bound, and no discovery starts.
        let started = Instant::now();
        poll_when_ready(&mut coordinator, &mut runtime, Duration::from_millis(500));
        assert!(started.elapsed() >= Duration::from_millis(450));
        assert!(coordinator.query.is_none());
        // A new entry in the versions directory wakes the wait and starts discovery again.
        // Named as no version, so the started discovery again finds no candidate.
        std::fs::create_dir(versions.join("incoming")).unwrap();
        poll_when_ready(&mut coordinator, &mut runtime, Duration::from_secs(10));
        assert!(coordinator.query.is_some());
        while coordinator.query.is_some() {
            poll_when_ready(&mut coordinator, &mut runtime, Duration::from_secs(10));
        }
        drop(coordinator);
        std::fs::remove_dir_all(root).unwrap();
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
        let mut coordinator = Coordinator::new(current, "test.cadrumo.coordinator.manager".into());
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
