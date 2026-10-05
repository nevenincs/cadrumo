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
}

impl Kind {
    #[cfg(test)]
    const ALL: [Self; 3] = [Self::Console, Self::Python, Self::Tui];

    fn slot(self) -> usize {
        self as usize
    }
}

impl Program {
    /// The launch of one terminal kind. Every kind receives the same pinned
    /// child environment. Interactive shells start in the user's home and
    /// never inside the storage root, so a relative write cannot land a
    /// plaintext file in custody; the TUI starts in the storage root.
    fn for_kind(launch: &Launch, kind: Kind) -> Result<Self> {
        let environment = launch.child.environment().clone();
        let interpreter = launch.child.executable().to_owned();
        if matches!(kind, Kind::Console | Kind::Python)
            && (!launch.home.is_absolute()
                || !launch.home.is_dir()
                || launch.home.starts_with(&launch.working_directory))
        {
            return Err(failure(ErrorCode::EnvironmentFailed));
        }
        Ok(match kind {
            Kind::Console => {
                let (executable, arguments) = console::shell(&environment)?;
                Self {
                    executable,
                    arguments,
                    directory: launch.home.clone(),
                    environment: console::with_bin_first(
                        environment,
                        &console::package_bin(&interpreter)?,
                    )?,
                    role: ProcessRole::Console,
                }
            }
            Kind::Python => Self {
                executable: interpreter,
                arguments: Vec::new(),
                directory: launch.home.clone(),
                environment,
                role: ProcessRole::Repl,
            },
            Kind::Tui => Self {
                executable: interpreter,
                arguments: ["-m", "cadrumo.entrypoints.tui"]
                    .into_iter()
                    .map(OsString::from)
                    .collect(),
                directory: launch.working_directory.clone(),
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
}

struct Entry<S> {
    id: u64,
    session: S,
}

/// At most one session per kind. A session that failed to settle stays owned
/// in its slot until a later settlement succeeds.
pub struct Registry<S> {
    next: u64,
    slots: [Option<Entry<S>>; 3],
}

impl<S> Default for Registry<S> {
    fn default() -> Self {
        Self {
            next: 0,
            slots: [None, None, None],
        }
    }
}

impl<S: Settle> Registry<S> {
    /// Starts `kind`, replacing a session that exited or was stopped. A live
    /// session of the same kind is refused.
    pub fn open(&mut self, kind: Kind, start: impl FnOnce() -> Result<S>) -> Result<u64> {
        let slot = &mut self.slots[kind.slot()];
        if let Some(entry) = slot {
            if entry.session.live() {
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            entry.session.request_stop();
            entry.session.await_stop(Instant::now() + SETTLE_TIMEOUT)?;
            *slot = None;
        }
        let session = start()?;
        self.next += 1;
        *slot = Some(Entry {
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

    /// Settles session `id` and forgets it; it stays owned if settlement fails.
    pub fn close(&mut self, id: u64) -> Result<()> {
        let slot = self
            .slots
            .iter_mut()
            .find(|slot| slot.as_ref().is_some_and(|entry| entry.id == id))
            .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?;
        if let Some(entry) = slot {
            entry.session.request_stop();
            entry.session.await_stop(Instant::now() + SETTLE_TIMEOUT)?;
        }
        *slot = None;
        Ok(())
    }

    /// Settles every kind under one shared deadline. Every kind is attempted
    /// even when another fails; failed sessions stay owned and their failures
    /// are returned in kind order.
    pub fn close_all(&mut self) -> Vec<ApplicationError> {
        for entry in self.slots.iter_mut().flatten() {
            entry.session.request_stop();
        }
        let deadline = Instant::now() + SETTLE_TIMEOUT;
        let mut failures = Vec::new();
        for slot in &mut self.slots {
            if let Some(entry) = slot {
                match entry.session.await_stop(deadline) {
                    Ok(()) => *slot = None,
                    Err(error) => failures.push(error),
                }
            }
        }
        failures
    }

    #[cfg(test)]
    fn occupied(&self) -> Vec<Kind> {
        Kind::ALL
            .into_iter()
            .filter(|kind| self.slots[kind.slot()].is_some())
            .collect()
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

    pub fn with_session<T>(
        &self,
        id: u64,
        action: impl FnOnce(&mut Session) -> Result<T>,
    ) -> Result<T> {
        action(self.registry()?.session(id)?)
    }

    pub fn close(&self, id: u64) -> Result<()> {
        self.registry()?.close(id)
    }

    /// Settles every session; used on window close, page load and host exit.
    /// Returns the first failure; later ones go to diagnostics directly.
    pub fn stop(&self) -> Result<()> {
        let mut failures = self.registry()?.close_all().into_iter();
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
mod tests;
