//! Who starts, owns and observes the runtime of one storage root across sessions.
//!
//! - *Owner:* the manager that launched the runtime, or adopted it in its own session
//!   through the supervision core. Only the owner, or its cutover successor, signals it.
//! - *Observer:* a manager in another session of the same user. It holds a process handle
//!   on the runtime and can learn only that it ended; it never signals it.
//! - *Takeover:* when no runtime runs, a manager starts one only if its session is active,
//!   the Quit marker is absent, and it holds the per-user start claim. Under the claim it
//!   looks for a runtime and reads the marker again, so a runtime another manager started
//!   meanwhile is observed rather than started twice, and a Quit recorded meanwhile holds.
//!   The caller keeps the returned [`StartPermit`] until the runtime it launched is ready
//!   or its launch failed, so other managers see "starting elsewhere" until then.
//!
//! Quit suppresses automatic starts until the same user signs in again or starts the
//! runtime by hand: [`StartKind::SignIn`] clears a marker of the same user, and
//! [`StartKind::Manual`] or [`Ownership::start_manually`] clears any marker.

use super::ManagerSession;
use super::claim::StartClaim;
use super::quit::{QuitMarker, QuitState, clear_quit, read_quit_marker, record_quit};
use crate::supervision::boot_record::{BootRecord, read_boot_record};
use crate::supervision::process::{
    InspectError, ProcessIdentity, RuntimeProcess, current_session, open_process,
};
use crate::supervision::supervisor::SessionActivity;
use std::fmt;
use std::io;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// How this manager process was started.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StartKind {
    /// The sign-in registration started it at a new logon of the user.
    SignIn,
    /// The user started it by hand.
    Manual,
}

/// A runtime in another session, watched through a process handle and never signalled.
pub trait ObservedRuntime: Send + fmt::Debug {
    fn pid(&self) -> u32;
    /// Whether the runtime has ended; one that can no longer be queried has ended.
    fn has_ended(&mut self) -> bool;
}

/// What runs for the storage root right now.
#[derive(Debug)]
pub enum Located {
    /// No runtime that a boot record and a matching live process confirm.
    Nothing,
    /// The runtime runs in this manager's session.
    OwnSession { pid: u32 },
    /// The runtime runs in another session of this user.
    OtherSession(Box<dyn ObservedRuntime>),
}

/// Finds the runtime of the storage root.
pub trait RuntimeLocator: Send {
    fn locate(&mut self) -> Located;
}

/// The right to start the runtime now. Dropping it releases the start claim.
#[derive(Debug)]
pub struct StartPermit {
    _claim: StartClaim,
    storage_root: PathBuf,
}

impl StartPermit {
    pub(crate) fn from_claim(claim: StartClaim) -> Self {
        Self {
            storage_root: claim.storage_root().to_path_buf(),
            _claim: claim,
        }
    }
    pub fn storage_root(&self) -> &Path {
        &self.storage_root
    }

    /// Recheck mutable start conditions after a delay, while still holding the claim.
    pub fn refusal(&self, activity: &dyn SessionActivity) -> Option<WaitReason> {
        if !activity.is_active() {
            return Some(WaitReason::Inactive);
        }
        match read_quit_marker(&self.storage_root) {
            QuitState::Present(_) => Some(WaitReason::Quit),
            QuitState::Unreadable => Some(WaitReason::QuitUnreadable),
            QuitState::Absent => None,
        }
    }
}

/// Reserve a restart before its backoff begins. A returned permit remains held through
/// the delay and launch, until readiness or abandonment. Recheck ownership after taking
/// the claim: another session may have won the interval since the old process exited.
pub fn reserve_restart(
    storage_root: &Path,
    activity: &dyn SessionActivity,
    locator: &mut dyn RuntimeLocator,
) -> Role {
    if !activity.is_active() {
        return Role::Wait(WaitReason::Inactive);
    }
    let claim = match StartClaim::take(storage_root, Duration::ZERO) {
        Ok(Some(claim)) => claim,
        Ok(None) => return Role::Wait(WaitReason::StartingElsewhere),
        Err(error) => return Role::Wait(WaitReason::ClaimUnavailable(error.kind())),
    };
    if !activity.is_active() {
        return Role::Wait(WaitReason::Inactive);
    }
    match read_quit_marker(storage_root) {
        QuitState::Present(_) => return Role::Wait(WaitReason::Quit),
        QuitState::Unreadable => return Role::Wait(WaitReason::QuitUnreadable),
        QuitState::Absent => {}
    }
    match locator.locate() {
        Located::Nothing => Role::Start(StartPermit {
            _claim: claim,
            storage_root: storage_root.to_path_buf(),
        }),
        Located::OwnSession { pid } => Role::OwnSession { pid },
        Located::OtherSession(observed) => Role::Observe(observed),
    }
}

/// Why a manager neither starts nor observes the runtime.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WaitReason {
    /// The user quit; automatic starts stay suppressed.
    Quit,
    /// Something occupies the Quit marker's location but it is no valid marker, so
    /// automatic starts stay suppressed until a manual start replaces it.
    QuitUnreadable,
    /// This manager's session is not active, for example disconnected.
    Inactive,
    /// Another manager holds the start claim and is starting the runtime.
    StartingElsewhere,
    /// The start claim could not be taken.
    ClaimUnavailable(io::ErrorKind),
}

/// What this manager does about the runtime now.
#[derive(Debug)]
pub enum Role {
    /// Launch the runtime and keep the permit until it is ready or the launch failed.
    Start(StartPermit),
    /// The runtime runs in this session; the supervision core adopts or keeps it.
    OwnSession { pid: u32 },
    /// The runtime runs in another session; decide again once it has ended.
    Observe(Box<dyn ObservedRuntime>),
    /// Do nothing until the reason changes, then decide again.
    Wait(WaitReason),
}

/// The ownership decisions of one manager for one storage root.
pub struct Ownership {
    storage_root: PathBuf,
    me: ManagerSession,
    activity: Box<dyn SessionActivity>,
    locator: Box<dyn RuntimeLocator>,
}

impl Ownership {
    pub fn new(
        storage_root: PathBuf,
        me: ManagerSession,
        activity: Box<dyn SessionActivity>,
        locator: Box<dyn RuntimeLocator>,
    ) -> Self {
        Self {
            storage_root,
            me,
            activity,
            locator,
        }
    }

    /// Apply how this manager started to the Quit marker, then decide.
    ///
    /// A sign-in clears a marker the same user left; a marker of another user or one that
    /// cannot be read stays. A manual start clears any marker.
    pub fn begin(&mut self, start: StartKind) -> io::Result<Role> {
        match start {
            StartKind::Manual => self.start_manually(),
            StartKind::SignIn => {
                if let QuitState::Present(marker) = read_quit_marker(&self.storage_root)
                    && marker.user == self.me.user
                {
                    clear_quit(&self.storage_root)?;
                }
                Ok(self.reassess())
            }
        }
    }

    /// The user asked for the runtime: clear any Quit marker, then decide.
    pub fn start_manually(&mut self) -> io::Result<Role> {
        clear_quit(&self.storage_root)?;
        Ok(self.reassess())
    }

    /// Record that the user quit, before the owner stops the runtime.
    ///
    /// Managers that see the runtime end afterwards find the marker and do not restart it.
    pub fn record_quit(&self) -> io::Result<()> {
        let set_at_ms = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(io::Error::other)?
            .as_millis();
        let marker = QuitMarker {
            user: self.me.user.clone(),
            session: self.me.session.clone(),
            set_at_ms: u64::try_from(set_at_ms).map_err(io::Error::other)?,
        };
        record_quit(&self.storage_root, &marker)
    }

    /// Decide what to do now: at start, after an observed or owned runtime ended, or
    /// when a waiting reason may have changed.
    pub fn reassess(&mut self) -> Role {
        if let Some(role) = self.running() {
            return role;
        }
        if !self.activity.is_active() {
            return Role::Wait(WaitReason::Inactive);
        }
        if let Some(reason) = self.suppressed() {
            return Role::Wait(reason);
        }
        let claim = match StartClaim::take(&self.storage_root, Duration::ZERO) {
            Ok(Some(claim)) => claim,
            Ok(None) => return Role::Wait(WaitReason::StartingElsewhere),
            Err(error) => return Role::Wait(WaitReason::ClaimUnavailable(error.kind())),
        };
        // Another manager may have started a runtime, or the user quit, between the first
        // reads and the claim; the claim is released before either is reported.
        if let Some(role) = self.running() {
            drop(claim);
            return role;
        }
        if let Some(reason) = self.suppressed() {
            drop(claim);
            return Role::Wait(reason);
        }
        Role::Start(StartPermit {
            _claim: claim,
            storage_root: self.storage_root.clone(),
        })
    }

    fn running(&mut self) -> Option<Role> {
        match self.locator.locate() {
            Located::Nothing => None,
            Located::OwnSession { pid } => Some(Role::OwnSession { pid }),
            Located::OtherSession(observed) => Some(Role::Observe(observed)),
        }
    }

    fn suppressed(&self) -> Option<WaitReason> {
        match read_quit_marker(&self.storage_root) {
            QuitState::Absent => None,
            QuitState::Present(_) => Some(WaitReason::Quit),
            QuitState::Unreadable => Some(WaitReason::QuitUnreadable),
        }
    }
}

/// A runtime process held open by handle; it can only report that it ended.
#[derive(Debug)]
pub struct HandleObserver {
    // Private, so nothing reaches the process's terminate.
    process: RuntimeProcess,
}

impl HandleObserver {
    /// Hold a handle on the live process `pid` to watch for its end.
    pub fn open(pid: u32) -> Result<Self, InspectError> {
        open_process(pid).map(|opened| Self {
            process: RuntimeProcess::Adopted(opened),
        })
    }
}

impl ObservedRuntime for HandleObserver {
    fn pid(&self) -> u32 {
        self.process.pid()
    }

    fn has_ended(&mut self) -> bool {
        self.process.try_exit().is_ok_and(|exit| exit.is_some())
    }
}

/// Where a live process stands relative to its boot record and this manager.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Placement {
    /// The process is not the boot the record names: the record is stale.
    NotTheRecordedRuntime,
    OwnSession,
    OtherSession,
    /// Either session could not be read.
    SessionUnknown,
}

/// Place the live process `identity` against `record` and this manager's session.
pub fn place(
    record: &BootRecord,
    identity: &ProcessIdentity,
    own_session: Option<String>,
) -> Placement {
    if record.pid != identity.pid || record.process_created != identity.created {
        return Placement::NotTheRecordedRuntime;
    }
    match (identity.session.as_ref(), own_session.as_ref()) {
        (Some(runtime), Some(own)) if runtime == own => Placement::OwnSession,
        (Some(_), Some(_)) => Placement::OtherSession,
        _ => Placement::SessionUnknown,
    }
}

/// Locates the runtime through its boot record and the live process it names.
///
/// A missing, stale or unreadable record, or a process whose session cannot be read, is
/// reported as nothing running: a start then meets the runtime's own endpoint ownership,
/// which refuses a second runtime, and the supervision core reports an owner it cannot
/// adopt as foreign.
#[derive(Debug)]
pub struct BootRecordLocator {
    storage_root: PathBuf,
}

impl BootRecordLocator {
    pub fn new(storage_root: &Path) -> Self {
        Self {
            storage_root: storage_root.to_path_buf(),
        }
    }
}

impl RuntimeLocator for BootRecordLocator {
    fn locate(&mut self) -> Located {
        let Ok(record) = read_boot_record(&self.storage_root) else {
            return Located::Nothing;
        };
        let Ok(opened) = open_process(record.pid) else {
            return Located::Nothing;
        };
        match place(&record, &opened.identity, current_session()) {
            Placement::OwnSession => Located::OwnSession { pid: record.pid },
            Placement::OtherSession => Located::OtherSession(Box::new(HandleObserver {
                process: RuntimeProcess::Adopted(opened),
            })),
            Placement::NotTheRecordedRuntime | Placement::SessionUnknown => Located::Nothing,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::supervision::protocol::Admission;

    fn record() -> BootRecord {
        BootRecord {
            boot_id: "0f8fad5b-d9cb-469f-a165-70867728950e".into(),
            pid: 40,
            process_created: 7,
            version: "1.2.3".into(),
            package_directory: None,
            admission: Admission::Native,
        }
    }

    fn identity(session: Option<String>) -> ProcessIdentity {
        ProcessIdentity {
            pid: 40,
            created: 7,
            image: PathBuf::from("runtime"),
            fully_elevated: Some(false),
            session,
        }
    }

    #[test]
    fn a_runtime_is_placed_by_its_recorded_identity_and_session() {
        assert_eq!(
            place(&record(), &identity(Some("1".into())), Some("1".into())),
            Placement::OwnSession
        );
        assert_eq!(
            place(&record(), &identity(Some("2".into())), Some("1".into())),
            Placement::OtherSession
        );
        assert_eq!(
            place(&record(), &identity(None), Some("1".into())),
            Placement::SessionUnknown
        );
        assert_eq!(
            place(&record(), &identity(Some("1".into())), None),
            Placement::SessionUnknown
        );
        let reused = ProcessIdentity {
            created: 8,
            ..identity(Some("1".into()))
        };
        assert_eq!(
            place(&record(), &reused, Some("1".into())),
            Placement::NotTheRecordedRuntime
        );
    }
}
