//! The Logs view: Python records and manager diagnostics from the current
//! desktop launch, merged with desktop-host events in paced batches.
//!
//! The feed never changes source files. Explicit exports write a new file in
//! Downloads. Terminal bytes and captured child output never become records.
//!
//! One poller thread owns the tail and does every file and directory read,
//! and only while a subscription exists. The commands and the page-load hook
//! take a lock that is never held across file I/O or a delivery.
mod format;
mod host;
mod manager;
mod record;
mod severity;
mod tail;
#[cfg(test)]
mod tests;
mod timestamp;

use crate::{app::Commands, environment::Launch, shell::channel::Deliveries};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
pub use format::Level;
use record::{Aggregate, LogBatch, LogSourceState, LogSourceStates, Prepared, Sink, SourceKind};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{Arc, Condvar, Mutex, MutexGuard},
    time::{Duration, Instant},
};
use tauri::{
    Manager, Runtime, State, Webview, ipc::Channel, plugin::TauriPlugin, webview::PageLoadEvent,
};

/// How often the files and the diagnostics events are polled while a
/// subscription exists.
const TICK: Duration = Duration::from_millis(100);

struct Inner {
    aggregate: Aggregate,
    /// A poll completed since the hub last went idle, so `aggregate.states`
    /// describes the files.
    polled: bool,
    /// The ring and the tail were cleared for the current idle period.
    resting: bool,
    /// The hub is gone; the poller stops.
    closed: bool,
}

/// What the commands and the poller share.
struct Shared {
    inner: Mutex<Inner>,
    /// Signalled when a subscription starts or the hub closes.
    wake: Condvar,
}

impl Shared {
    fn lock(&self) -> MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|e| e.into_inner())
    }
}

/// The commands' side of the log aggregation.
pub struct LogHub {
    shared: Arc<Shared>,
    file: PathBuf,
    manager_file: PathBuf,
    refusal: Option<ApplicationError>,
    diagnostics: Arc<Diagnostics>,
}

/// The poller's side: the tail and the host events, read on its own thread.
pub struct Poller {
    /// Fixed for the launch, including when the page reloads or the reader rests.
    since_ms: Option<u64>,
    shared: Arc<Shared>,
    tail: tail::Tail,
    manager_tail: tail::Tail,
    host: host::HostEvents,
    diagnostics: Arc<Diagnostics>,
}

impl LogHub {
    pub fn new(
        log_file: PathBuf,
        manager_log_file: PathBuf,
        log_format: &str,
        diagnostics: Arc<Diagnostics>,
    ) -> (Self, Poller) {
        let tail = tail::Tail::new(log_file.clone(), log_format);
        let manager_tail = tail::Tail::manager(manager_log_file.clone());
        let state = LogSourceState {
            kind: SourceKind::Missing,
            detail: log_file.display().to_string(),
            failure: None,
            rejected: 0,
        };
        let shared = Arc::new(Shared {
            inner: Mutex::new(Inner {
                aggregate: Aggregate::new(LogSourceStates {
                    host: host::source(&diagnostics),
                    python: state,
                    manager: LogSourceState {
                        kind: SourceKind::Missing,
                        detail: manager_log_file.display().to_string(),
                        failure: None,
                        rejected: 0,
                    },
                }),
                polled: false,
                resting: true,
                closed: false,
            }),
            wake: Condvar::new(),
        });
        let hub = Self {
            shared: shared.clone(),
            file: log_file,
            manager_file: manager_log_file,
            refusal: tail.refusal(),
            diagnostics: diagnostics.clone(),
        };
        let poller = Poller {
            since_ms: Some(diagnostics.started_ms()),
            shared,
            tail,
            manager_tail,
            host: host::HostEvents::default(),
            diagnostics,
        };
        (hub, poller)
    }

    /// Starts a subscription and wakes the poller. The returned state is the
    /// last poll's, or before any poll a probe of the files; the first batch
    /// always carries the polled state.
    fn subscribe(&self, sink: Sink) -> Subscribed {
        let (subscription, polled) = {
            let mut inner = self.shared.lock();
            let subscription = inner.aggregate.subscribe(sink);
            self.shared.wake.notify_all();
            (
                subscription,
                inner.polled.then(|| inner.aggregate.states.clone()),
            )
        };
        let states = polled.unwrap_or_else(|| LogSourceStates {
            host: host::source(&self.diagnostics),
            python: match &self.refusal {
                Some(refusal) => LogSourceState {
                    kind: SourceKind::Unreadable,
                    detail: self.file.display().to_string(),
                    failure: Some(refusal.clone()),
                    rejected: 0,
                },
                None => tail::probe(&self.file),
            },
            manager: tail::probe(&self.manager_file),
        });
        Subscribed {
            subscription,
            states,
        }
    }

    fn unsubscribe(&self, subscription: u64) -> Result<()> {
        if self.shared.lock().aggregate.unsubscribe(subscription) {
            Ok(())
        } else {
            Err(ApplicationError::new(
                ErrorCode::InvalidArguments,
                Operation::Logging,
            ))
        }
    }

    fn clear_subscriptions(&self) {
        self.shared.lock().aggregate.clear_subscriptions();
    }
}

impl Drop for LogHub {
    fn drop(&mut self) {
        self.shared.lock().closed = true;
        self.shared.wake.notify_all();
    }
}

impl Poller {
    /// Polls while a subscription exists and waits without polling while none
    /// does, until the hub is dropped.
    pub fn run(mut self) {
        while self.ready() {
            self.tick(Instant::now());
            std::thread::sleep(TICK);
        }
    }

    /// Waits until a subscription exists; false once the hub is gone.
    fn ready(&mut self) -> bool {
        let shared = self.shared.clone();
        let mut inner = shared.lock();
        loop {
            if inner.closed {
                return false;
            }
            if !inner.aggregate.idle() {
                return true;
            }
            self.rest(&mut inner);
            inner = shared.wake.wait(inner).unwrap_or_else(|e| e.into_inner());
        }
    }

    /// Clears the ring and the tail once per idle period. Files can rotate
    /// away while nothing polls, so the next subscription's backlog is read
    /// again from the end of the files rather than resumed from old offsets.
    fn rest(&mut self, inner: &mut Inner) {
        if !inner.resting {
            inner.resting = true;
            inner.polled = false;
            inner.aggregate.clear_records();
            self.tail.reset();
            self.manager_tail.reset();
            self.host = host::HostEvents::default();
        }
    }

    /// Reads new records without the lock, then numbers them and picks the
    /// due batches under it, then sends the batches without it.
    pub fn tick(&mut self, now: Instant) {
        let shared = self.shared.clone();
        {
            let mut inner = shared.lock();
            if inner.aggregate.idle() {
                self.rest(&mut inner);
                return;
            }
            inner.resting = false;
        }
        let mut prepared: Vec<Prepared> = self
            .host
            .poll(&self.diagnostics)
            .into_iter()
            .map(Prepared::new)
            .collect();
        let (entries, python) = self.tail.poll(now);
        prepared.extend(
            entries
                .into_iter()
                .filter(|entry| {
                    self.since_ms
                        .is_none_or(|since| entry.timestamp_ms.is_some_and(|time| time >= since))
                })
                .map(Prepared::new),
        );
        let (entries, manager) = self.manager_tail.poll(now);
        prepared.extend(
            entries
                .into_iter()
                .filter(|entry| {
                    self.since_ms
                        .is_none_or(|since| entry.timestamp_ms.is_some_and(|time| time >= since))
                })
                .map(Prepared::new),
        );
        let deliveries = {
            let mut inner = shared.lock();
            for record in prepared {
                inner.aggregate.push(record);
            }
            inner.aggregate.lost(std::mem::take(&mut self.host.dropped));
            inner.aggregate.states = LogSourceStates {
                python,
                manager,
                host: host::source(&self.diagnostics),
            };
            inner.polled = true;
            inner.aggregate.deliver(now)
        };
        let refused = record::send(deliveries);
        if !refused.is_empty() {
            shared.lock().aggregate.end(&refused);
        }
    }
}

#[derive(Serialize)]
struct Subscribed {
    subscription: u64,
    states: LogSourceStates,
}

/// A subscription's sink. It ends the subscription when the channel refuses
/// a batch or the shell reports that a frame of this channel could not be
/// delivered to the webview.
fn channel_sink<R: Runtime>(webview: Webview<R>, records: Channel<LogBatch>) -> Sink {
    let callback = records.id();
    Arc::new(move |batch| {
        records.send(batch).is_ok()
            && !webview
                .try_state::<Deliveries>()
                .is_some_and(|deliveries| deliveries.failed(webview.label(), callback))
    })
}

/// Runs off the main thread; the probe of the files runs on a blocking
/// worker.
#[tauri::command]
async fn logs_subscribe<R: Runtime>(
    webview: Webview<R>,
    hub: State<'_, Arc<LogHub>>,
    records: Channel<LogBatch>,
) -> Result<Subscribed> {
    let hub = hub.inner().clone();
    let sink = channel_sink(webview, records);
    tauri::async_runtime::spawn_blocking(move || hub.subscribe(sink))
        .await
        .map_err(|e| ApplicationError::new(ErrorCode::Panic, Operation::Logging).caused_by(e))
}

#[tauri::command]
async fn logs_unsubscribe(hub: State<'_, Arc<LogHub>>, subscription: u64) -> Result<()> {
    hub.unsubscribe(subscription)
}

/// Exports an explicit log selection to a new file; never overwrites an export.
#[tauri::command]
async fn logs_export<R: Runtime>(app: tauri::AppHandle<R>, text: String) -> Result<String> {
    admit_text(&text)?;
    let directory = app.path().download_dir().map_err(|e| {
        ApplicationError::new(ErrorCode::WriteFailed, Operation::Logging).caused_by(e)
    })?;
    tauri::async_runtime::spawn_blocking(move || export(&directory, &text))
        .await
        .map_err(|e| ApplicationError::new(ErrorCode::Panic, Operation::Logging).caused_by(e))?
}

fn admit_text(text: &str) -> Result<()> {
    if text.is_empty() || text.len() > 1024 * 1024 * 1024 {
        return Err(ApplicationError::new(
            ErrorCode::InvalidArguments,
            Operation::Logging,
        ));
    }
    Ok(())
}

/// The host chooses the location; webview callers cannot supply a path.
#[tauri::command]
async fn logs_reveal(hub: State<'_, Arc<LogHub>>) -> Result<()> {
    let file = hub.file.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let directory = file
            .parent()
            .filter(|parent| parent.is_dir())
            .ok_or_else(|| ApplicationError::new(ErrorCode::ReadFailed, Operation::Logging))?;
        opener::open(directory).map_err(|e| {
            ApplicationError::new(ErrorCode::SpawnFailed, Operation::Logging).caused_by(e)
        })
    })
    .await
    .map_err(|e| ApplicationError::new(ErrorCode::Panic, Operation::Logging).caused_by(e))?
}

/// Log selections can exceed the ordinary shell clipboard's one MiB limit.
#[tauri::command]
async fn logs_copy<R: Runtime>(app: tauri::AppHandle<R>, text: String) -> Result<()> {
    admit_text(&text)?;
    tauri::async_runtime::spawn_blocking(move || {
        app.try_state::<tauri_plugin_clipboard_manager::Clipboard<R>>()
            .ok_or_else(|| {
                ApplicationError::new(ErrorCode::DesktopUnavailable, Operation::Logging)
            })?
            .write_text(text)
            .map_err(|e| {
                ApplicationError::new(ErrorCode::WriteFailed, Operation::Logging).caused_by(e)
            })
    })
    .await
    .map_err(|e| ApplicationError::new(ErrorCode::Panic, Operation::Logging).caused_by(e))?
}

fn export(directory: &std::path::Path, text: &str) -> Result<String> {
    use std::io::Write;
    admit_text(text)?;
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let path = directory.join(format!(
        "cadrumo-session-{}-{stamp}.log",
        std::process::id()
    ));
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
        .map_err(|e| {
            ApplicationError::new(ErrorCode::WriteFailed, Operation::Logging).caused_by(e)
        })?;
    if let Err(error) = file
        .write_all(text.as_bytes())
        .and_then(|()| file.sync_all())
    {
        drop(file);
        let _ = std::fs::remove_file(&path);
        return Err(
            ApplicationError::new(ErrorCode::WriteFailed, Operation::Logging).caused_by(error),
        );
    }
    Ok(path.display().to_string())
}

pub fn plugin<R: Runtime>(launch: &Launch) -> TauriPlugin<R> {
    let (hub, poller) = LogHub::new(
        launch.log_file.clone(),
        launch.manager_log_file.clone(),
        &launch.log_format,
        launch.diagnostics.clone(),
    );
    tauri::plugin::Builder::new("cadrumo-logs")
        .setup(move |app, _| {
            app.manage(Arc::new(hub));
            std::thread::Builder::new()
                .name("cadrumo-logs".into())
                .spawn(move || poller.run())?;
            Ok(())
        })
        // A shell document that loads again starts its own subscriptions;
        // the previous document's channels have no receiver.
        .on_page_load(|webview, payload| {
            if payload.event() == PageLoadEvent::Started
                && let Some(hub) = webview.try_state::<Arc<LogHub>>()
            {
                hub.clear_subscriptions();
            }
        })
        .build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![
        logs_subscribe,
        logs_unsubscribe,
        logs_export,
        logs_copy,
        logs_reveal
    ]
}
