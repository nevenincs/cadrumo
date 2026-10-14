//! The desktop establishes verified supervision using the shared manager core.

use crate::environment::Launch;
use cadrumo_application::{
    child::ChildConfiguration,
    component::Cancellation,
    diagnostics::{Diagnostics, EventKind, HostOutcome, HostStage},
    error::application::{ApplicationError, ErrorCode, Operation, Result},
    installation::{DiscoveryContract, RegistrationHints, Selection},
    process::status::{ProcessPhase, ProcessRole},
};
use serde::{Deserialize, Serialize};
use std::{
    path::{Path, PathBuf},
    process::Stdio,
    sync::{
        Arc, Mutex,
        atomic::{AtomicBool, AtomicU64, Ordering},
    },
    time::Duration,
};
use tauri::State;
use tokio::io::AsyncReadExt;

mod observation;
pub use observation::{ManagerState, ManagerStatus};

const DISPATCH: &str = include_str!("python/manager_dispatch.py");
const DEADLINE: Duration = Duration::from_secs(60);

async fn wait_for_readiness(ready: impl std::future::Future<Output = Result<()>>) -> Result<()> {
    #[cfg(windows)]
    let bound =
        cadrumo_manager::supervision::supervisor::SupervisorConfig::default().readiness_ceiling;
    #[cfg(not(windows))]
    let bound = Duration::from_secs(90);
    tokio::time::timeout(bound, ready)
        .await
        .map_err(|_| failure(ErrorCode::TimedOut))?
}

#[derive(Clone, Copy, Debug, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum StartOutcome {
    Dispatched,
    Unsupported,
}

#[derive(Clone, Copy, Debug, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InstallScope {
    User,
    Machine,
}

struct Attempt {
    outcome: Result<StartOutcome>,
    retry: bool,
}

pub struct ManagerStart {
    package_root: Result<Option<PathBuf>>,
    child: ChildConfiguration,
    storage_root: PathBuf,
    diagnostics: Arc<Diagnostics>,
    attempt: Arc<tokio::sync::Mutex<Option<Attempt>>>,
    generation: AtomicU64,
    closed: Arc<AtomicBool>,
    cancellation: Arc<Cancellation>,
    spawn_fence: Arc<Mutex<()>>,
    closing: tokio::sync::Notify,
    observation: observation::Observer,
    #[cfg(windows)]
    host: Mutex<Option<cadrumo_manager::desktop_host::DesktopHost>>,
}

impl ManagerStart {
    pub fn new(launch: &Launch) -> Self {
        Self {
            package_root: managed(launch)
                .map(|managed| managed.then(|| launch.package_root.clone())),
            child: launch.child.clone(),
            storage_root: launch.working_directory.clone(),
            diagnostics: launch.diagnostics.clone(),
            attempt: Arc::new(tokio::sync::Mutex::new(None)),
            generation: AtomicU64::new(0),
            closed: Arc::new(AtomicBool::new(false)),
            cancellation: Arc::new(Cancellation::default()),
            spawn_fence: Arc::new(Mutex::new(())),
            closing: tokio::sync::Notify::new(),
            observation: observation::Observer::new(cfg!(windows)),
            #[cfg(windows)]
            host: Mutex::new(None),
        }
    }

    /// Concurrent callers share the initial attempt; retries are explicit.
    pub async fn start(self: &Arc<Self>, retry: bool) -> Result<StartOutcome> {
        self.start_with(retry, move |owner| async move {
            owner.dispatch(retry, true).await
        })
        .await
    }

    /// Health uses the same supervised fallback without installing or registering.
    pub async fn start_existing(self: &Arc<Self>) -> Result<StartOutcome> {
        self.start_with(false, move |owner| async move {
            owner.dispatch(false, false).await
        })
        .await
    }

    /// GUI startup and headless package acceptance use the same verified gate.
    pub async fn ensure_ready(
        self: &Arc<Self>,
        sign_in: &Arc<crate::shell::sign_in::SignIn>,
    ) -> Result<()> {
        wait_for_readiness(async {
            if self.start_existing().await? != StartOutcome::Dispatched {
                return Err(failure(ErrorCode::ManagerUnavailable));
            }
            loop {
                if !self.supervision_status()? {
                    tokio::time::sleep(Duration::from_millis(500)).await;
                    continue;
                }
                let status = sign_in.read_status().await?;
                if status.runtime_ready() && self.supervision_status()? {
                    self.diagnostics
                        .host_outcome(HostStage::Manager, HostOutcome::Ready);
                    return Ok(());
                }
                if status.runtime_available && status.refusal.is_some() {
                    return Err(failure(ErrorCode::ReadFailed));
                }
                tokio::time::sleep(Duration::from_millis(500)).await;
            }
        })
        .await
    }

    /// An explicit scope never shares a different caller's installation decision.
    pub async fn install(self: &Arc<Self>, scope: InstallScope) -> Result<StartOutcome> {
        let previous = self.attempt.clone().lock_owned().await;
        if self.closed.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        let owner = self.clone();
        let diagnostic_scope = match scope {
            InstallScope::User => cadrumo_application::diagnostics::service::InstallationScope::User,
            InstallScope::Machine => cadrumo_application::diagnostics::service::InstallationScope::Machine,
        };
        self.diagnostics.service(None, cadrumo_application::diagnostics::service::ServiceFact::ManagerInstallationStarted { scope: diagnostic_scope });
        tokio::spawn(async move {
            owner
                .complete_attempt(previous, false, async {
                    owner.stop_owned().await?;
                    let target = match owner.install_target(scope).await {
                        Ok(target) => target,
                        Err(error) => {
                            // Failed/cancelled optional installation restores GUI ownership.
                            let _ = owner.dispatch(false, false).await;
                            return Err(error);
                        }
                    };
                    drop(target);
                    owner.diagnostics.service(None, cadrumo_application::diagnostics::service::ServiceFact::ManagerInstallationCompleted { scope: diagnostic_scope });
                    owner.dispatch(false, false).await
                })
                .await
        })
        .await
        .map_err(|_| failure(ErrorCode::Panic))?
    }

    async fn start_with<F, Work>(self: &Arc<Self>, retry: bool, work: F) -> Result<StartOutcome>
    where
        F: FnOnce(Arc<Self>) -> Work + Send + 'static,
        Work: std::future::Future<Output = Result<StartOutcome>> + Send + 'static,
    {
        if self.closed.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        let observed = self.generation.load(Ordering::Acquire);
        let previous = self.attempt.clone().lock_owned().await;
        if self.closed.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        if let Some(attempt) = previous.as_ref()
            && (!retry || (attempt.retry && observed != self.generation.load(Ordering::Acquire)))
        {
            return attempt.outcome.clone();
        }
        let owner = self.clone();
        // The host owns settlement even if an IPC caller abandons its answer.
        tokio::spawn(async move {
            owner
                .complete_attempt(previous, retry, work(owner.clone()))
                .await
        })
        .await
        .map_err(|_| failure(ErrorCode::Panic))?
    }

    async fn complete_attempt(
        &self,
        mut previous: tokio::sync::OwnedMutexGuard<Option<Attempt>>,
        retry: bool,
        work: impl std::future::Future<Output = Result<StartOutcome>>,
    ) -> Result<StartOutcome> {
        self.diagnostics
            .host_event(EventKind::StageStarted, HostStage::Manager);
        if let Err(error) = self.observation.observe(ManagerState::Starting) {
            self.observation.observation_failed(error);
        }
        let outcome = work.await;
        match &outcome {
            Ok(StartOutcome::Dispatched) => self
                .diagnostics
                .host_outcome(HostStage::Manager, HostOutcome::Dispatched),
            Ok(StartOutcome::Unsupported) => self
                .diagnostics
                .host_outcome(HostStage::Manager, HostOutcome::Unavailable),
            Err(error) => self
                .diagnostics
                .host_failure(HostStage::Manager, error.clone()),
        }
        match &outcome {
            Ok(StartOutcome::Unsupported) => {
                if let Err(error) = self.observation.set_state(ManagerState::Unsupported) {
                    self.observation.observation_failed(error);
                }
            }
            Err(error) => self.report_failure(error.clone()),
            Ok(StartOutcome::Dispatched) => {}
        }
        *previous = Some(Attempt {
            outcome: outcome.clone(),
            retry,
        });
        self.generation.fetch_add(1, Ordering::Release);
        outcome
    }

    /// Fence requests, cancel verification and join its actual worker before host exit.
    /// Blocking OS calls themselves cannot be forcibly interrupted.
    /// No manager or runtime process handle is owned or stopped here.
    pub async fn close(&self) {
        if let Err(error) = self.close_checked().await {
            self.diagnostics.host_failure(HostStage::Shutdown, error);
        }
    }

    pub async fn close_checked(&self) -> Result<()> {
        if let Err(error) = self.observation.set_state(ManagerState::Stopping) {
            self.observation.observation_failed(error);
        }
        self.observation.close();
        {
            let _fence = self
                .spawn_fence
                .lock()
                .unwrap_or_else(|error| error.into_inner());
            self.closed.store(true, Ordering::Release);
            self.cancellation.cancel();
        }
        self.closing.notify_waiters();
        let _settled = self.attempt.lock().await;
        let result = self.stop_owned().await;
        match &result {
            Ok(()) => {
                let _ = self.observation.set_state(ManagerState::Stopped);
            }
            Err(error) => self.report_failure(error.clone()),
        }
        self.observation.close();
        result
    }

    /// Wait for this host's actual supervisor worker and owned runtime settlement.
    pub async fn stop_owned(&self) -> Result<()> {
        #[cfg(windows)]
        {
            let host = self
                .host
                .lock()
                .map_err(|_| failure(ErrorCode::Panic))?
                .take();
            if let Some(host) = host {
                tokio::task::spawn_blocking(move || host.close())
                    .await
                    .map_err(|_| failure(ErrorCode::Panic))?
                    .map_err(|error| failure(ErrorCode::CleanupFailed).caused_by(error))?;
            }
        }
        Ok(())
    }

    pub fn supervision_status(&self) -> Result<bool> {
        #[cfg(windows)]
        {
            let host = self.host.lock().map_err(|_| {
                let error = failure(ErrorCode::LockPoisoned);
                self.observation.observation_failed(error.clone());
                error
            })?;
            let status = host
                .as_ref()
                .map(cadrumo_manager::desktop_host::DesktopHost::status);
            if status.is_none() {
                let previous = self
                    .observation
                    .status()
                    .inspect_err(|error| self.observation.observation_failed(error.clone()))?;
                if let Some(error) = previous.failure {
                    return Err(error);
                }
            }
            if status == Some(cadrumo_manager::ipc::Outcome::Unavailable) {
                let error = failure(ErrorCode::ManagerUnavailable);
                self.report_failure(error.clone());
                return Err(error);
            }
            use cadrumo_manager::ipc::Outcome;
            self.observation
                .observe(match status {
                    Some(Outcome::Running) => ManagerState::Ready,
                    Some(Outcome::Stopping) => ManagerState::Stopping,
                    Some(Outcome::Starting) | None => ManagerState::Starting,
                    _ => ManagerState::Waiting,
                })
                .inspect_err(|error| self.observation.observation_failed(error.clone()))?;
            Ok(status == Some(cadrumo_manager::ipc::Outcome::Running))
        }
        #[cfg(not(windows))]
        Ok(false)
    }

    pub fn read_status(&self) -> Result<ManagerStatus> {
        if !self.is_closed() {
            // Terminal manager failure is a status; observer failure remains an error.
            if let Err(error) = self.supervision_status()
                && error.code == ErrorCode::LockPoisoned
            {
                return Err(error);
            }
        }
        self.observation.status()
    }

    pub fn report_failure(&self, error: ApplicationError) {
        if error.code == ErrorCode::LockPoisoned {
            self.observation.observation_failed(error);
        } else {
            self.observation.failed(error);
        }
    }

    pub fn is_closed(&self) -> bool {
        self.closed.load(Ordering::Acquire)
    }

    async fn dispatch(&self, retry: bool, _provision: bool) -> Result<StartOutcome> {
        if !cfg!(windows) {
            return Ok(StartOutcome::Unsupported);
        }
        let Some(package_root) = self.package_root.as_ref().map_err(Clone::clone)? else {
            return Err(failure(ErrorCode::ManagerUnavailable));
        };
        let package_root = package_root.clone();
        #[cfg(windows)]
        let default_root = cadrumo_manager::supervision::environment::ManagedLocations::for_host(
            &std::env::current_exe()
                .map_err(|error| failure(ErrorCode::EnvironmentFailed).caused_by(error))?,
            &package_root,
            &self.storage_root,
        )
        .map_err(|error| failure(ErrorCode::EnvironmentFailed).caused_by(error))?
        .is_default_root();
        #[cfg(not(windows))]
        let default_root = false;
        #[cfg(windows)]
        if retry {
            let finished = self
                .host
                .lock()
                .map_err(|_| failure(ErrorCode::Panic))?
                .as_ref()
                .is_some_and(cadrumo_manager::desktop_host::DesktopHost::finished);
            if finished {
                // A failed worker has already drained its owned runtime. Retain
                // its failure evidence, then allow an explicit retry to re-admit.
                if let Err(error) = self.stop_owned().await {
                    self.diagnostics.host_failure(HostStage::Manager, error);
                }
                cadrumo_manager::failed_versions::FailedVersions::retry(&self.storage_root)
                    .map_err(|error| failure(ErrorCode::ManagerUnavailable).caused_by(error))?;
            }
        }
        // Recheck package bytes on every actual attempt, off the GUI/runtime thread.
        let manager = self
            .activate_installed(default_root, package_root.clone(), retry)
            .await?;
        #[cfg(windows)]
        {
            let mut host = self.host.lock().map_err(|_| failure(ErrorCode::Panic))?;
            if let Some(host) = host.as_ref() {
                if retry {
                    host.retry()
                        .map_err(|error| failure(ErrorCode::ManagerUnavailable).caused_by(error))?;
                }
            } else {
                *host = Some(
                    cadrumo_manager::desktop_host::DesktopHost::start(
                        &package_root,
                        &self.storage_root,
                        manager,
                        self.diagnostics.clone(),
                    )
                    .map_err(|error| failure(ErrorCode::ManagerUnavailable).caused_by(error))?,
                );
            }
        }
        Ok(StartOutcome::Dispatched)
    }

    async fn activate_installed(
        &self,
        default_root: bool,
        discovery_package: PathBuf,
        retry: bool,
    ) -> Result<Option<PathBuf>> {
        if !default_root {
            // A selected isolated root has its own supervisor claim and endpoint.
            // Never activate a catalogue manager against the real user's root.
            return Ok(None);
        }
        let selected = self
            .resolve_with(move |cancellation| target(&discovery_package, &cancellation))
            .await;
        Ok(match selected {
            Ok(target) => {
                let manager = target.manager.clone();
                // Dispatch is only an activation attempt; embedded arbitration
                // verifies the manager endpoint and takes over when it is absent.
                if let Err(error) = self.dispatch_target(target, retry).await {
                    self.diagnostics.host_failure(HostStage::Manager, error);
                }
                Some(manager)
            }
            Err(_) => None,
        })
    }

    async fn install_target(&self, scope: InstallScope) -> Result<Selection> {
        let Some(package) = self.package_root.as_ref().map_err(Clone::clone)? else {
            return Err(installation_failure(ErrorCode::InstallationRefused));
        };
        let package = package.clone();
        let temporary = self
            .child
            .environment()
            .iter()
            .find(|(name, _)| name.to_string_lossy().eq_ignore_ascii_case("TEMP"))
            .map(|(_, value)| PathBuf::from(value))
            .ok_or_else(|| installation_failure(ErrorCode::EnvironmentFailed))?;
        let closed = self.closed.clone();
        let fence = self.spawn_fence.clone();
        self.resolve_with(move |_| install_package(&package, scope, &temporary, &closed, &fence))
            .await
    }

    async fn dispatch_target(&self, target: Selection, retry: bool) -> Result<StartOutcome> {
        if self.closed.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        let outcome = self
            .run_dispatch(self.dispatch_command(&target, retry), DEADLINE)
            .await;
        drop(target);
        outcome
    }

    fn dispatch_command(&self, target: &Selection, retry: bool) -> tokio::process::Command {
        let mut command = tokio::process::Command::from(self.child.command());
        command
            .args(["-I", "-c", DISPATCH])
            .arg(if retry {
                &target.manager
            } else {
                &target.entrypoint
            })
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .kill_on_drop(true);
        if retry {
            command.arg("--retry");
        }
        #[cfg(windows)]
        command.creation_flags(0x0800_0000);
        command
    }

    async fn resolve_with<F, T>(&self, inspect: F) -> Result<T>
    where
        F: FnOnce(Arc<Cancellation>) -> Result<T> + Send + 'static,
        T: Send + 'static,
    {
        if self.closed.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        let cancellation = self.cancellation.clone();
        // The owned attempt awaits this handle fully, even if its IPC caller is
        // dropped. Close cancels first and then waits that same attempt to settle.
        let target = tokio::task::spawn_blocking(move || inspect(cancellation))
            .await
            .map_err(|_| failure(ErrorCode::Panic))??;
        if self.closed.load(Ordering::Acquire) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        Ok(target)
    }

    async fn run_dispatch(
        &self,
        mut command: tokio::process::Command,
        deadline: Duration,
    ) -> Result<StartOutcome> {
        let closing = self.closing.notified();
        tokio::pin!(closing);
        closing.as_mut().enable();
        let spawned = {
            let _fence = self
                .spawn_fence
                .lock()
                .map_err(|_| failure(ErrorCode::Panic))?;
            if self.closed.load(Ordering::Acquire) {
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            command.spawn()
        };
        let mut child = spawned.map_err(|error| {
            let error = failure(ErrorCode::ManagerDispatchFailed).caused_by(error);
            self.diagnostics
                .spawn_failure(ProcessRole::ManagerDispatch, error.clone());
            error
        })?;
        let id = self.diagnostics.start(
            child.id().ok_or_else(|| failure(ErrorCode::SpawnFailed))?,
            ProcessRole::ManagerDispatch,
        );
        let mut recorded_exit = false;
        let read = tokio::time::timeout(deadline, async {
            let mut stdout = child
                .stdout
                .take()
                .ok_or_else(|| failure(ErrorCode::ReadFailed))?
                .take(4097);
            let mut bytes = Vec::new();
            stdout
                .read_to_end(&mut bytes)
                .await
                .map_err(|error| failure(ErrorCode::ReadFailed).caused_by(error))?;
            if bytes.len() > 4096 {
                return Err(failure(ErrorCode::OutputLimit));
            }
            let status = child
                .wait()
                .await
                .map_err(|error| failure(ErrorCode::CleanupFailed).caused_by(error))?;
            self.diagnostics
                .finish(id, status.code(), ProcessPhase::Exited);
            recorded_exit = true;
            decode(&bytes, status.success())
        });
        let result = tokio::select! {
            biased;
            _ = &mut closing => Ok(Err(failure(ErrorCode::SessionUnavailable))),
            result = read => result,
        };
        match result {
            Ok(Ok(outcome)) => Ok(outcome),
            other => {
                let error = match other {
                    Ok(Err(error)) => error,
                    _ => failure(ErrorCode::TimedOut),
                };
                self.diagnostics.failure_for(id, error.clone());
                let cleanup: Result<()> = async {
                    if recorded_exit {
                        return Ok(());
                    }
                    let (status, phase) = match child
                        .try_wait()
                        .map_err(|error| failure(ErrorCode::CleanupFailed).caused_by(error))?
                    {
                        Some(status) => (status, ProcessPhase::Exited),
                        None => {
                            child.kill().await.map_err(|error| {
                                failure(ErrorCode::CleanupFailed).caused_by(error)
                            })?;
                            (
                                child.wait().await.map_err(|error| {
                                    failure(ErrorCode::CleanupFailed).caused_by(error)
                                })?,
                                ProcessPhase::Terminated,
                            )
                        }
                    };
                    self.diagnostics.finish(id, status.code(), phase);
                    Ok(())
                }
                .await;
                if let Err(cleanup_error) = cleanup {
                    self.diagnostics.failure_for(id, cleanup_error);
                }
                Err(error)
            }
        }
    }
}

fn failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Manager)
}

fn installation_failure(code: ErrorCode) -> ApplicationError {
    ApplicationError::new(code, Operation::Installation)
}

#[cfg(windows)]
fn install_package(
    package: &Path,
    scope: InstallScope,
    temporary: &Path,
    closed: &AtomicBool,
    fence: &Mutex<()>,
) -> Result<Selection> {
    use cadrumo_installer::{
        admission::Scope,
        runner::bootstrap::{self, Failure},
    };
    if !cadrumo_platform::desktop::available() {
        return Err(installation_failure(ErrorCode::SessionUnavailable));
    }
    let contract: DiscoveryContract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).map_err(
            |error| installation_failure(ErrorCode::InstallationRefused).caused_by(error),
        )?;
    let scope = match scope {
        InstallScope::User => Scope::User,
        InstallScope::Machine => Scope::Machine,
    };
    bootstrap::install(package, &contract, scope, temporary, || {
        let guard = fence.lock().map_err(|_| Failure::NativeFailed)?;
        if closed.load(Ordering::Acquire) {
            return Err(Failure::Cancelled);
        }
        Ok(guard)
    })
    .map_err(|error| {
        installation_failure(match error {
            Failure::KitUnavailable => ErrorCode::InstallationUnavailable,
            Failure::KitRefused => ErrorCode::InstallationRefused,
            Failure::Cancelled => ErrorCode::InstallationCancelled,
            Failure::NativeFailed => ErrorCode::InstallationFailed,
            Failure::PublicationUnconfirmed => ErrorCode::InstallationUnsettled,
        })
    })
}

#[cfg(not(windows))]
fn install_package(
    _: &Path,
    _: InstallScope,
    _: &Path,
    _: &AtomicBool,
    _: &Mutex<()>,
) -> Result<Selection> {
    Err(installation_failure(ErrorCode::UnsupportedPlatform))
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct DispatchReply {
    dispatched: bool,
    os_code: Option<i32>,
}

fn decode(bytes: &[u8], success: bool) -> Result<StartOutcome> {
    let reply: DispatchReply =
        serde_json::from_slice(bytes).map_err(|_| failure(ErrorCode::ManagerDispatchFailed))?;
    if success && reply.dispatched && reply.os_code.is_none() {
        return Ok(StartOutcome::Dispatched);
    }
    let error = failure(ErrorCode::ManagerDispatchFailed);
    Err(match reply.os_code {
        Some(code) => error.caused_by(std::io::Error::from_raw_os_error(code)),
        None => error,
    })
}

fn target(package_root: &Path, cancellation: &Cancellation) -> Result<Selection> {
    let contract: DiscoveryContract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json")))
            .map_err(|error| failure(ErrorCode::PackageUnavailable).caused_by(error))?;
    #[cfg(windows)]
    let native = cadrumo_platform::installation::manager_entry_points(
        &contract.installation_identity.application_id,
    )
    .map_err(|error| failure(ErrorCode::PackageUnavailable).caused_by(error))?;
    #[cfg(windows)]
    let registered = RegistrationHints {
        this_user: native.this_user.as_deref(),
        all_users: native.all_users.as_deref(),
    };
    #[cfg(not(windows))]
    let registered = RegistrationHints::default();
    target_from(package_root, &contract, &registered, cancellation)
}

fn target_from(
    package_root: &Path,
    contract: &DiscoveryContract,
    registered: &RegistrationHints<'_>,
    cancellation: &Cancellation,
) -> Result<Selection> {
    let member = contract
        .manager_member()
        .map_err(|error| failure(ErrorCode::PackageUnavailable).caused_by(error))?;
    contract
        .discover_cancellable(&member.under(package_root), registered, cancellation)
        .map_err(|error| match error {
            cadrumo_application::error::Error::Cancelled => failure(ErrorCode::SessionUnavailable),
            error => failure(ErrorCode::PackageUnavailable).caused_by(error),
        })
}

#[cfg(windows)]
fn managed(launch: &Launch) -> Result<bool> {
    use cadrumo_platform::storage::{self, Mode};
    if storage::authority_override_present(std::env::vars_os()) {
        return Err(failure(ErrorCode::EnvironmentFailed));
    }
    let executable = std::env::current_exe()
        .map_err(|error| failure(ErrorCode::EnvironmentFailed).caused_by(error))?;
    let evidence =
        storage::detect_mode(&executable).map_err(|_| failure(ErrorCode::EnvironmentFailed))?;
    if evidence.mode != Mode::Installed {
        return Ok(false);
    }
    let actual_package = std::fs::canonicalize(&evidence.package)
        .map_err(|error| failure(ErrorCode::PackageUnavailable).caused_by(error))?;
    let selected_package = std::fs::canonicalize(&launch.package_root)
        .map_err(|error| failure(ErrorCode::PackageUnavailable).caused_by(error))?;
    if actual_package != selected_package {
        return Ok(false);
    }
    let resolved = storage::resolve_storage_root(&evidence)
        .map_err(|_| failure(ErrorCode::EnvironmentFailed))?;
    Ok(std::fs::canonicalize(&resolved.root)
        .map_err(|error| failure(ErrorCode::EnvironmentFailed).caused_by(error))?
        == std::fs::canonicalize(&launch.working_directory)
            .map_err(|error| failure(ErrorCode::EnvironmentFailed).caused_by(error))?)
}

#[cfg(not(windows))]
fn managed(_: &Launch) -> Result<bool> {
    Ok(false)
}

pub fn commands<R: tauri::Runtime>() -> crate::app::Commands<R> {
    crate::app::commands![
        manager_start,
        manager_install,
        manager_status,
        manager_subscribe,
        manager_unsubscribe
    ]
}

#[tauri::command]
fn manager_status(state: State<'_, Arc<ManagerStart>>) -> Result<ManagerStatus> {
    state.read_status()
}

#[tauri::command]
fn manager_subscribe(
    state: State<'_, Arc<ManagerStart>>,
    updates: tauri::ipc::Channel<observation::Signal>,
) -> Result<u32> {
    state.read_status()?;
    state.observation.subscribe(updates)
}

#[tauri::command]
fn manager_unsubscribe(state: State<'_, Arc<ManagerStart>>, subscription: u32) -> Result<()> {
    state.observation.unsubscribe(subscription)
}

#[tauri::command]
async fn manager_start(state: State<'_, Arc<ManagerStart>>) -> Result<StartOutcome> {
    state.start(true).await
}

#[tauri::command]
async fn manager_install(
    state: State<'_, Arc<ManagerStart>>,
    scope: InstallScope,
) -> Result<StartOutcome> {
    state.install(scope).await
}

#[cfg(test)]
#[path = "manager/tests.rs"]
mod tests;

#[cfg(all(test, windows))]
#[path = "manager/package_tests.rs"]
mod package_tests;
