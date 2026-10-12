//! Public manager observations driven by the existing supervision watchdog.
//! These signals grant no runtime or profile authority and start no worker.

use super::{ApplicationError, ErrorCode, Result, failure};
use serde::Serialize;
use std::sync::Mutex;
use tauri::ipc::Channel;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ManagerState {
    Unsupported,
    Starting,
    Ready,
    Recovering,
    Waiting,
    Stopping,
    Stopped,
    Failed,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagerStatus {
    pub state: ManagerState,
    pub failure: Option<ApplicationError>,
}

impl ManagerStatus {
    fn state(state: ManagerState) -> Self {
        Self {
            state,
            failure: None,
        }
    }

    fn same(&self, other: &Self) -> bool {
        self.state == other.state
            && match (&self.failure, &other.failure) {
                (None, None) => true,
                (Some(left), Some(right)) => {
                    left.code == right.code
                        && left.operation == right.operation
                        && left.io_kind == right.io_kind
                        && left.os_code == right.os_code
                }
                _ => false,
            }
    }
}

#[derive(Clone, Serialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Signal {
    ManagerState {
        revision: u64,
        status: ManagerStatus,
    },
    ManagerObservationFailed {
        revision: u64,
        error: ApplicationError,
    },
}

struct Listener {
    channel: Channel<Signal>,
    revision: u64,
    previous: Option<Result<ManagerStatus>>,
}

struct Store {
    current: ManagerStatus,
    ready_before: bool,
    closed: bool,
    listener: Option<Listener>,
}

pub(super) struct Observer(Mutex<Store>);

impl Observer {
    pub(super) fn new(supported: bool) -> Self {
        Self(Mutex::new(Store {
            current: ManagerStatus::state(if supported {
                ManagerState::Starting
            } else {
                ManagerState::Unsupported
            }),
            ready_before: false,
            closed: false,
            listener: None,
        }))
    }

    pub(super) fn status(&self) -> Result<ManagerStatus> {
        Ok(self
            .0
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?
            .current
            .clone())
    }

    pub(super) fn subscribe(&self, channel: Channel<Signal>) -> Result<u32> {
        let mut store = self
            .0
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        if store.closed {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        let id = channel.id();
        store.listener = Some(Listener {
            channel,
            revision: 0,
            previous: None,
        });
        let current = store.current.clone();
        store.send(Ok(current));
        Ok(id)
    }

    pub(super) fn unsubscribe(&self, subscription: u32) -> Result<()> {
        let mut store = self
            .0
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        if store
            .listener
            .as_ref()
            .is_some_and(|held| held.channel.id() == subscription)
        {
            store.listener = None;
        }
        Ok(())
    }

    pub(super) fn observe(&self, observed: ManagerState) -> Result<()> {
        let mut store = self
            .0
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        if store.closed {
            return Ok(());
        }
        let state = match observed {
            ManagerState::Ready => {
                store.ready_before = true;
                ManagerState::Ready
            }
            ManagerState::Starting | ManagerState::Waiting if store.ready_before => {
                ManagerState::Recovering
            }
            state => state,
        };
        store.set(ManagerStatus::state(state));
        Ok(())
    }

    pub(super) fn set_state(&self, state: ManagerState) -> Result<()> {
        let mut store = self
            .0
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        if store.closed {
            store.current = ManagerStatus::state(state);
        } else {
            store.set(ManagerStatus::state(state));
        }
        Ok(())
    }

    pub(super) fn failed(&self, error: ApplicationError) {
        if let Ok(mut store) = self.0.lock() {
            let status = ManagerStatus {
                state: ManagerState::Failed,
                failure: Some(error),
            };
            if store.closed {
                store.current = status;
            } else {
                store.set(status);
            }
        }
    }

    pub(super) fn observation_failed(&self, error: ApplicationError) {
        // Poison prevents coherent state reads, but the existing listener can
        // still receive the safe failure before the application exits.
        let mut store = self.0.lock().unwrap_or_else(|error| error.into_inner());
        if !store.closed {
            store.send(Err(error));
        }
    }

    pub(super) fn close(&self) {
        let mut store = self.0.lock().unwrap_or_else(|error| error.into_inner());
        store.closed = true;
        store.listener = None;
    }
}

impl Store {
    fn set(&mut self, status: ManagerStatus) {
        self.current = status.clone();
        self.send(Ok(status));
    }

    fn send(&mut self, current: Result<ManagerStatus>) {
        let Some(held) = self.listener.as_mut() else {
            return;
        };
        let unchanged = match (&held.previous, &current) {
            (Some(Ok(left)), Ok(right)) => left.same(right),
            (Some(Err(left)), Err(right)) => {
                left.code == right.code && left.operation == right.operation
            }
            _ => false,
        };
        if unchanged {
            return;
        }
        held.revision = held.revision.saturating_add(1);
        let signal = match &current {
            Ok(status) => Signal::ManagerState {
                revision: held.revision,
                status: status.clone(),
            },
            Err(error) => Signal::ManagerObservationFailed {
                revision: held.revision,
                error: error.clone(),
            },
        };
        if held.channel.send(signal).is_err() {
            self.listener = None;
        } else {
            held.previous = Some(current);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use tauri::ipc::InvokeResponseBody;

    fn channel(frames: Arc<Mutex<Vec<serde_json::Value>>>) -> Channel<Signal> {
        Channel::new(move |body| {
            let InvokeResponseBody::Json(body) = body else {
                panic!("expected JSON manager state");
            };
            frames
                .lock()
                .unwrap()
                .push(serde_json::from_str(&body).unwrap());
            Ok(())
        })
    }

    #[test]
    fn initial_state_coalesces_and_recovery_requires_previous_verified_readiness() {
        let observer = Observer::new(true);
        let frames = Arc::new(Mutex::new(Vec::new()));
        observer.subscribe(channel(frames.clone())).unwrap();
        observer.observe(ManagerState::Starting).unwrap();
        observer.observe(ManagerState::Waiting).unwrap();
        observer.observe(ManagerState::Ready).unwrap();
        observer.observe(ManagerState::Starting).unwrap();
        observer.observe(ManagerState::Waiting).unwrap();
        observer.observe(ManagerState::Ready).unwrap();
        observer.failed(failure(ErrorCode::ManagerUnavailable));
        observer.failed(failure(ErrorCode::ManagerUnavailable));
        let frames = frames.lock().unwrap();
        assert_eq!(frames.len(), 6);
        let states: Vec<_> = frames
            .iter()
            .map(|frame| frame["status"]["state"].as_str().unwrap())
            .collect();
        assert_eq!(
            states,
            [
                "starting",
                "waiting",
                "ready",
                "recovering",
                "ready",
                "failed"
            ]
        );
        for (index, frame) in frames.iter().enumerate() {
            assert_eq!(frame["kind"], "manager-state");
            assert_eq!(frame["revision"], index + 1);
            assert_eq!(frame["status"].as_object().unwrap().len(), 2);
        }
        assert_eq!(
            frames[5]["status"]["failure"]["code"],
            "manager_unavailable"
        );
        assert_eq!(frames[5]["status"]["failure"]["operation"], "manager");
        assert!(frames[5]["status"]["failure"].get("cause").is_none());
    }

    #[test]
    fn replacement_has_initial_state_and_stale_unsubscribe_cannot_detach_it() {
        let observer = Observer::new(true);
        let first_frames = Arc::new(Mutex::new(Vec::new()));
        let replacement_frames = Arc::new(Mutex::new(Vec::new()));
        let first = observer.subscribe(channel(first_frames.clone())).unwrap();
        observer.observe(ManagerState::Ready).unwrap();
        let replacement = observer
            .subscribe(channel(replacement_frames.clone()))
            .unwrap();
        observer.unsubscribe(first).unwrap();
        observer.observe(ManagerState::Starting).unwrap();
        assert_eq!(first_frames.lock().unwrap().len(), 2);
        let frames = replacement_frames.lock().unwrap();
        assert_eq!(frames.len(), 2);
        assert_eq!(frames[0]["revision"], 1);
        assert_eq!(frames[0]["status"]["state"], "ready");
        assert_eq!(frames[1]["status"]["state"], "recovering");
        drop(frames);
        observer.unsubscribe(replacement).unwrap();
        observer.observe(ManagerState::Ready).unwrap();
        assert_eq!(replacement_frames.lock().unwrap().len(), 2);
    }

    #[test]
    fn closed_receiver_is_detached_and_host_close_fences_all_subscriptions() {
        let observer = Observer::new(true);
        observer
            .subscribe(Channel::new(|_| {
                Err(std::io::Error::from(std::io::ErrorKind::BrokenPipe).into())
            }))
            .unwrap();
        assert!(observer.0.lock().unwrap().listener.is_none());
        let frames = Arc::new(Mutex::new(Vec::new()));
        observer.subscribe(channel(frames.clone())).unwrap();
        observer.set_state(ManagerState::Stopping).unwrap();
        observer.close();
        observer.observe(ManagerState::Ready).unwrap();
        observer.set_state(ManagerState::Stopped).unwrap();
        assert_eq!(observer.status().unwrap().state, ManagerState::Stopped);
        assert_eq!(frames.lock().unwrap().len(), 2);
        assert_eq!(
            observer.subscribe(channel(frames)).unwrap_err().code,
            ErrorCode::SessionUnavailable
        );
    }

    #[test]
    fn unsupported_and_observation_failure_are_public_and_coalesced() {
        let observer = Observer::new(false);
        let frames = Arc::new(Mutex::new(Vec::new()));
        observer.subscribe(channel(frames.clone())).unwrap();
        observer.observation_failed(failure(ErrorCode::LockPoisoned));
        observer.observation_failed(failure(ErrorCode::LockPoisoned));
        let frames = frames.lock().unwrap();
        assert_eq!(frames.len(), 2);
        assert_eq!(frames[0]["status"]["state"], "unsupported");
        assert_eq!(frames[1]["kind"], "manager-observation-failed");
        assert_eq!(frames[1]["error"]["code"], "lock_poisoned");
        assert_eq!(frames[1]["revision"], 2);
    }
}
