//! The Logs view: Python records tailed from `cadrumo.log` and its rotations,
//! merged with desktop-host diagnostics events, delivered in paced batches.
//!
//! Records are read, never written: nothing here creates, truncates, rotates
//! or deletes a log file, and nothing is persisted. Terminal bytes and
//! captured child output never become records.
mod format;
mod host;
mod record;
mod tail;
#[cfg(test)]
mod tests;

use crate::{app::Commands, environment::Launch};
use cadrumo_application::{
    diagnostics::Diagnostics,
    error::application::{ApplicationError, ErrorCode, Operation, Result},
};
use record::{Aggregate, LogBatch, LogSourceState, SourceKind};
use serde::Serialize;
use std::{
    path::PathBuf,
    sync::{Arc, Mutex, Weak},
    time::{Duration, Instant},
};
use tauri::{Manager, Runtime, State, ipc::Channel, plugin::TauriPlugin, webview::PageLoadEvent};

/// How often the files and the diagnostics events are polled.
const TICK: Duration = Duration::from_millis(100);

struct Inner {
    tail: tail::Tail,
    host: host::HostEvents,
    diagnostics: Arc<Diagnostics>,
    aggregate: Aggregate,
    polled: bool,
}

impl Inner {
    fn poll(&mut self, now: Instant) {
        for entry in self.host.poll(&self.diagnostics) {
            self.aggregate.push(entry);
        }
        let (entries, state) = self.tail.poll(now);
        for entry in entries {
            self.aggregate.push(entry);
        }
        self.aggregate.state = state;
        self.polled = true;
    }
}

pub struct LogHub {
    inner: Mutex<Inner>,
}

impl LogHub {
    pub fn new(log_file: PathBuf, log_format: &str, diagnostics: Arc<Diagnostics>) -> Self {
        let state = LogSourceState {
            kind: SourceKind::Missing,
            detail: log_file.display().to_string(),
            failure: None,
        };
        Self {
            inner: Mutex::new(Inner {
                tail: tail::Tail::new(log_file, log_format),
                host: host::HostEvents::default(),
                diagnostics,
                aggregate: Aggregate::new(state),
                polled: false,
            }),
        }
    }

    fn lock(&self) -> std::sync::MutexGuard<'_, Inner> {
        self.inner.lock().unwrap_or_else(|e| e.into_inner())
    }

    pub fn tick(&self, now: Instant) {
        let mut inner = self.lock();
        inner.poll(now);
        inner.aggregate.deliver(now);
    }

    /// Polls first when nothing was polled yet, so the returned state is real.
    fn subscribe(&self, sink: record::Sink) -> Subscribed {
        let mut inner = self.lock();
        if !inner.polled {
            inner.poll(Instant::now());
        }
        Subscribed {
            subscription: inner.aggregate.subscribe(sink),
            state: inner.aggregate.state.clone(),
        }
    }

    fn unsubscribe(&self, subscription: u64) -> Result<()> {
        if self.lock().aggregate.unsubscribe(subscription) {
            Ok(())
        } else {
            Err(ApplicationError::new(
                ErrorCode::InvalidArguments,
                Operation::Logging,
            ))
        }
    }

    /// Polls until the hub is dropped.
    fn run(hub: Weak<Self>) {
        loop {
            std::thread::sleep(TICK);
            match hub.upgrade() {
                Some(hub) => hub.tick(Instant::now()),
                None => return,
            }
        }
    }
}

#[derive(Serialize)]
struct Subscribed {
    subscription: u64,
    state: LogSourceState,
}

#[tauri::command]
fn logs_subscribe(hub: State<'_, Arc<LogHub>>, records: Channel<LogBatch>) -> Subscribed {
    hub.subscribe(Box::new(move |batch| records.send(batch).is_ok()))
}

#[tauri::command]
fn logs_unsubscribe(hub: State<'_, Arc<LogHub>>, subscription: u64) -> Result<()> {
    hub.unsubscribe(subscription)
}

pub fn plugin<R: Runtime>(launch: &Launch) -> TauriPlugin<R> {
    let hub = Arc::new(LogHub::new(
        launch.log_file.clone(),
        &launch.log_format,
        launch.diagnostics.clone(),
    ));
    tauri::plugin::Builder::new("cadrumo-logs")
        .setup(move |app, _| {
            let poller = Arc::downgrade(&hub);
            app.manage(hub);
            std::thread::Builder::new()
                .name("cadrumo-logs".into())
                .spawn(move || LogHub::run(poller))?;
            Ok(())
        })
        // A shell document that loads again starts its own subscriptions;
        // the previous document's channels have no receiver.
        .on_page_load(|webview, payload| {
            if payload.event() == PageLoadEvent::Started
                && let Some(hub) = webview.try_state::<Arc<LogHub>>()
            {
                hub.lock().aggregate.clear_subscriptions();
            }
        })
        .build()
}

pub fn commands<R: Runtime>() -> Commands<R> {
    crate::app::commands![logs_subscribe, logs_unsubscribe]
}
