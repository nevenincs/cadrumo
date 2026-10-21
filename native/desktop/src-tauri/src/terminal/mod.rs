//! Live PTY sessions, at most one per kind, streamed over one channel each.
mod console;
mod credit;
mod frame;
mod ipc;
mod session;

use crate::{app::Commands, environment::Launch};
use cadrumo_application::{
    error::application::{ApplicationError, ErrorCode, Result},
    process::status::ProcessRole,
};
use serde::Deserialize;
use session::{Program, SETTLE_TIMEOUT, Session, Sink, failure};
use std::{
    ffi::OsString,
    sync::{
        Arc, Mutex, MutexGuard,
        atomic::{AtomicU64, Ordering},
    },
    time::Instant,
};
use tauri::{Manager, Runtime, plugin::TauriPlugin, webview::PageLoadEvent};

pub fn plugin<R: Runtime>(_launch: &Launch) -> TauriPlugin<R> {
    tauri::plugin::Builder::new("cadrumo-terminal")
        .on_page_load(|webview, payload| {
            if let Some(state) = webview.try_state::<Arc<TerminalState>>() {
                state.page_load(payload.event());
            }
        })
        .build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    ipc::commands()
}

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Console,
    Python,
    Tui,
    AeatSetup,
}

impl Kind {
    #[cfg(test)]
    const ALL: [Self; 4] = [Self::Console, Self::Python, Self::Tui, Self::AeatSetup];

    fn slot(self) -> usize {
        self as usize
    }
}

impl Program {
    fn for_aeat_setup(launch: &Launch, profile: &str) -> Result<Self> {
        if !crate::shell::agent_access::wire::is_uuid(profile)
            || profile != profile.to_ascii_lowercase()
            || profile == "00000000-0000-0000-0000-000000000000"
        {
            return Err(failure(ErrorCode::InvalidArguments));
        }
        let mut program = Self::for_kind(launch, Kind::Tui)?;
        program.arguments.extend([
            OsString::from("--aeat-auth-profile"),
            OsString::from(profile),
        ]);
        Ok(program)
    }

    /// All terminal kinds share the pinned environment, bundled command path
    /// and taxonomy-owned operator workspace.
    fn for_kind(launch: &Launch, kind: Kind) -> Result<Self> {
        let interpreter = launch.child.executable().to_owned();
        let environment =
            console::with_package_first(launch.child.environment().clone(), &interpreter)?;
        console::validate_workspace(&launch.console_workspace, &launch.working_directory)?;
        Ok(match kind {
            Kind::AeatSetup => return Err(failure(ErrorCode::InvalidArguments)),
            Kind::Console => {
                let (executable, arguments) = console::shell(&environment)?;
                Self {
                    executable,
                    arguments,
                    directory: launch.console_workspace.clone(),
                    environment,
                    role: ProcessRole::Console,
                }
            }
            Kind::Python => Self {
                executable: interpreter,
                arguments: Vec::new(),
                directory: launch.console_workspace.clone(),
                environment,
                role: ProcessRole::Repl,
            },
            Kind::Tui => Self {
                executable: interpreter,
                arguments: ["-I", "-m", "cadrumo_runtime.host.frontend.tui"]
                    .into_iter()
                    .map(OsString::from)
                    .collect(),
                directory: launch.console_workspace.clone(),
                environment,
                role: ProcessRole::Tui,
            },
        })
    }
}

/// What the registry needs from a session to replace and settle it.
pub trait Settle {
    fn live(&self) -> bool;
    fn request_stop(&mut self);
    fn await_stop(&mut self, deadline: Instant) -> Result<()>;
    /// Settles without waiting when every worker has already ended.
    fn settle_ended(&mut self) -> bool;
}

impl Settle for Session {
    fn live(&self) -> bool {
        Session::live(self)
    }
    fn request_stop(&mut self) {
        Session::request_stop(self);
    }
    fn await_stop(&mut self, deadline: Instant) -> Result<()> {
        Session::await_stop(self, deadline)
    }
    fn settle_ended(&mut self) -> bool {
        Session::settle_ended(self)
    }
}

struct Entry<S> {
    id: u64,
    session: S,
}

/// At most one addressable session per kind. A stopped session that misses
/// its settlement bound stays owned as lingering, without holding its kind
/// against a new session, until a later settlement succeeds.
pub struct Registry<S> {
    next: u64,
    closed: bool,
    slots: [Option<Entry<S>>; 4],
    lingering: Vec<S>,
}

impl<S> Default for Registry<S> {
    fn default() -> Self {
        Self {
            next: 0,
            closed: false,
            slots: [None, None, None, None],
            lingering: Vec::new(),
        }
    }
}

impl<S: Settle> Registry<S> {
    /// Starts `kind`, replacing a session that exited or was stopped. A live
    /// session of the same kind is refused. A replaced session that cannot
    /// settle in time lingers, so its kind can start again.
    pub fn open(&mut self, kind: Kind, start: impl FnOnce() -> Result<S>) -> Result<u64> {
        if self.closed {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        self.lingering.retain_mut(|session| !session.settle_ended());
        let slot = &mut self.slots[kind.slot()];
        if slot.as_ref().is_some_and(|entry| entry.session.live()) {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        if let Some(mut entry) = slot.take() {
            entry.session.request_stop();
            // The session records its own settlement failure.
            if entry
                .session
                .await_stop(Instant::now() + SETTLE_TIMEOUT)
                .is_err()
            {
                self.lingering.push(entry.session);
            }
        }
        let session = start()?;
        self.next += 1;
        self.slots[kind.slot()] = Some(Entry {
            id: self.next,
            session,
        });
        Ok(self.next)
    }

    /// The current session `id`; a replaced or closed id is unavailable.
    pub fn session(&mut self, id: u64) -> Result<&mut S> {
        self.slots
            .iter_mut()
            .flatten()
            .find(|entry| entry.id == id)
            .map(|entry| &mut entry.session)
            .ok_or_else(|| failure(ErrorCode::SessionUnavailable))
    }

    /// Settles session `id` and forgets its id; it lingers if settlement fails.
    pub fn close(&mut self, id: u64) -> Result<()> {
        let slot = self
            .slots
            .iter_mut()
            .find(|slot| slot.as_ref().is_some_and(|entry| entry.id == id))
            .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?;
        let Some(mut entry) = slot.take() else {
            return Ok(());
        };
        entry.session.request_stop();
        let settled = entry.session.await_stop(Instant::now() + SETTLE_TIMEOUT);
        if settled.is_err() {
            self.lingering.push(entry.session);
        }
        settled
    }

    /// Settles every kind and every lingering session under one shared
    /// deadline. Each is attempted even when another fails; failed sessions
    /// linger and their failures are returned, kinds first in kind order.
    pub fn close_all(&mut self) -> Vec<ApplicationError> {
        let mut sessions: Vec<S> = self
            .slots
            .iter_mut()
            .filter_map(|slot| slot.take().map(|entry| entry.session))
            .collect();
        sessions.append(&mut self.lingering);
        // A retry kills again, as the first request did.
        for session in &mut sessions {
            session.request_stop();
        }
        let deadline = Instant::now() + SETTLE_TIMEOUT;
        let mut failures = Vec::new();
        for mut session in sessions {
            if let Err(error) = session.await_stop(deadline) {
                failures.push(error);
                self.lingering.push(session);
            }
        }
        failures
    }

    /// Permanently refuse new children under the same lock used for opening.
    pub fn shutdown(&mut self) -> Vec<ApplicationError> {
        self.closed = true;
        self.close_all()
    }

    #[cfg(test)]
    fn occupied(&self) -> Vec<Kind> {
        Kind::ALL
            .into_iter()
            .filter(|kind| self.slots[kind.slot()].is_some())
            .collect()
    }

    #[cfg(test)]
    fn lingering(&self) -> usize {
        self.lingering.len()
    }
}

/// Counts top-frame documents: a new document starting to load ends the
/// previous one, whose channels nothing receives any more.
#[derive(Default)]
pub struct Documents(AtomicU64);

impl Documents {
    pub fn current(&self) -> u64 {
        self.0.load(Ordering::SeqCst)
    }

    fn replace(&self) {
        self.0.fetch_add(1, Ordering::SeqCst);
    }

    fn still(&self, document: u64) -> Result<()> {
        if self.current() == document {
            Ok(())
        } else {
            Err(failure(ErrorCode::SessionUnavailable))
        }
    }
}

/// Opens `kind` on behalf of `document`, the document current when the
/// request arrived. A request from a document that has since been replaced
/// is refused, and a session started while its document was being replaced
/// is settled before the refusal: nothing could receive its frames, and it
/// would otherwise hold its kind against the new document.
fn open_for<S: Settle>(
    registry: &Mutex<Registry<S>>,
    documents: &Documents,
    document: u64,
    kind: Kind,
    start: impl FnOnce() -> Result<S>,
) -> Result<u64> {
    let lock = || {
        registry
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))
    };
    let id = {
        let mut registry = lock()?;
        documents.still(document)?;
        registry.open(kind, start)?
    };
    if let Err(refused) = documents.still(document) {
        // The replacing document's own settlement may have closed it already.
        return match lock()?.close(id) {
            Err(error) if error.code != ErrorCode::SessionUnavailable => Err(error),
            _ => Err(refused),
        };
    }
    Ok(id)
}

pub struct TerminalState {
    pub launch: Launch,
    documents: Documents,
    registry: Mutex<Registry<Session>>,
}

impl TerminalState {
    pub fn new(launch: Launch) -> Self {
        Self {
            launch,
            documents: Documents::default(),
            registry: Mutex::new(Registry::default()),
        }
    }

    fn registry(&self) -> Result<MutexGuard<'_, Registry<Session>>> {
        self.registry
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))
    }

    /// The current top-frame document, for [`TerminalState::open`].
    pub fn document(&self) -> u64 {
        self.documents.current()
    }

    pub fn open(&self, kind: Kind, cols: u16, rows: u16, sink: Sink, document: u64) -> Result<u64> {
        let program = Program::for_kind(&self.launch, kind)?;
        open_for(&self.registry, &self.documents, document, kind, || {
            Session::start(program, cols, rows, sink, self.launch.diagnostics.clone())
        })
    }

    /// A separate owned PTY preserves the person's existing workbench.
    pub fn open_aeat_setup(
        &self,
        profile: &str,
        cols: u16,
        rows: u16,
        sink: Sink,
        document: u64,
    ) -> Result<u64> {
        let program = Program::for_aeat_setup(&self.launch, profile)?;
        open_for(
            &self.registry,
            &self.documents,
            document,
            Kind::AeatSetup,
            || Session::start(program, cols, rows, sink, self.launch.diagnostics.clone()),
        )
    }

    pub fn with_session<T>(
        &self,
        id: u64,
        action: impl FnOnce(&mut Session) -> Result<T>,
    ) -> Result<T> {
        let mut registry = self.registry()?;
        let session = registry.session(id)?;
        let outcome = action(session);
        session.record(outcome)
    }

    pub fn close(&self, id: u64) -> Result<()> {
        self.registry()?.close(id)
    }

    /// Settles every session for a page reload, allowing the new page to open.
    /// Returns the first failure; later ones go to diagnostics directly.
    pub fn stop(&self) -> Result<()> {
        self.report_cleanup(self.registry()?.close_all())
    }

    /// Host shutdown permanently closes admission; page reload only settles.
    pub fn shutdown(&self) -> Result<()> {
        self.report_cleanup(self.registry()?.shutdown())
    }

    fn report_cleanup(&self, errors: Vec<ApplicationError>) -> Result<()> {
        let mut failures = errors.into_iter();
        let first = failures.next();
        for error in failures {
            self.launch.diagnostics.failure(error);
        }
        first.map_or(Ok(()), Err)
    }

    /// A new top-frame document cannot reach the previous document's
    /// channels, so its sessions are settled; the shell opens new ones. The
    /// document count moves first, so an open still in flight for the
    /// previous document is refused rather than left without a receiver.
    pub fn page_load(&self, event: PageLoadEvent) {
        if event == PageLoadEvent::Started {
            self.documents.replace();
            if let Err(error) = self.stop() {
                self.launch.diagnostics.failure(error);
            }
        }
    }
}

#[cfg(test)]
pub(crate) mod tests;
