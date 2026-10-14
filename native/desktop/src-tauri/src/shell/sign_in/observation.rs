//! Public observations from the same canonical CLI status read as the account menu.
//! One bounded observer per host; it never resumes a receipt or owns a runtime.

use super::{SignIn, wire::SignInStatus};
use cadrumo_application::error::application::{ApplicationError, ErrorCode, Result};
use serde::Serialize;
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};
use tauri::{State, ipc::Channel};
use tokio::task::JoinHandle;

#[derive(Clone, Serialize)]
#[serde(tag = "kind", rename_all = "kebab-case")]
pub enum Signal {
    SignInState {
        revision: u64,
        status: SignInStatus,
    },
    SignInObservationFailed {
        revision: u64,
        error: ApplicationError,
    },
}

struct Listener {
    channel: Channel<Signal>,
    previous: Option<Result<SignInStatus>>,
    revision: u64,
}

#[derive(Default)]
pub(super) struct Observer {
    listener: Mutex<Option<Listener>>,
    worker: Mutex<Option<JoinHandle<()>>>,
    closed: AtomicBool,
    wake: tokio::sync::Notify,
}

impl Observer {
    fn subscribe(&self, owner: Arc<SignIn>, channel: Channel<Signal>) -> Result<u32> {
        let mut worker = self
            .worker
            .lock()
            .map_err(|_| super::failure(ErrorCode::LockPoisoned))?;
        if self.closed.load(Ordering::Acquire) {
            return Err(super::failure(ErrorCode::SessionUnavailable));
        }
        let id = channel.id();
        *self
            .listener
            .lock()
            .map_err(|_| super::failure(ErrorCode::LockPoisoned))? = Some(Listener {
            channel,
            previous: None,
            revision: 0,
        });
        if worker.is_none() {
            *worker = Some(tokio::spawn(async move {
                loop {
                    let observer = &owner.observation;
                    // Register before observing to avoid losing a close notification.
                    let wake = observer.wake.notified();
                    tokio::pin!(wake);
                    wake.as_mut().enable();
                    if observer.closed.load(Ordering::Acquire) {
                        break;
                    }
                    if observer
                        .listener
                        .lock()
                        .unwrap_or_else(|error| error.into_inner())
                        .is_some()
                        && !owner.reads.mutating()
                    {
                        observer.publish(owner.read_status().await);
                    }
                    tokio::select! {
                        _ = &mut wake => {},
                        _ = tokio::time::sleep(std::time::Duration::from_secs(2)) => {},
                    }
                }
            }));
        } else {
            self.wake.notify_one();
        }
        Ok(id)
    }

    fn publish(&self, current: Result<SignInStatus>) {
        let mut listener = self
            .listener
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        let Some(held) = listener.as_mut() else {
            return;
        };
        let unchanged = match (&held.previous, &current) {
            (Some(Ok(previous)), Ok(current)) => previous == current,
            (Some(Err(previous)), Err(current)) => {
                previous.code == current.code && previous.operation == current.operation
            }
            _ => false,
        };
        if unchanged {
            return;
        }
        held.revision = held.revision.saturating_add(1);
        let signal = match &current {
            Ok(status) => Signal::SignInState {
                revision: held.revision,
                status: status.clone(),
            },
            Err(error) => Signal::SignInObservationFailed {
                revision: held.revision,
                error: error.clone(),
            },
        };
        if held.channel.send(signal).is_err() {
            *listener = None;
        } else {
            held.previous = Some(current);
        }
    }

    fn unsubscribe(&self, subscription: u32) {
        let mut listener = self
            .listener
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        if listener
            .as_ref()
            .is_some_and(|held| held.channel.id() == subscription)
        {
            *listener = None;
        }
    }

    pub(super) fn close(&self) {
        let _worker = self
            .worker
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        self.closed.store(true, Ordering::Release);
        *self
            .listener
            .lock()
            .unwrap_or_else(|error| error.into_inner()) = None;
        self.wake.notify_one();
    }

    pub(super) async fn join(&self) -> Result<()> {
        let worker = self
            .worker
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .take();
        if let Some(worker) = worker {
            worker
                .await
                .map_err(|_| super::failure(ErrorCode::SessionUnavailable))?;
        }
        Ok(())
    }
}

#[tauri::command]
pub async fn sign_in_subscribe(
    state: State<'_, Arc<SignIn>>,
    updates: Channel<Signal>,
) -> Result<u32> {
    state.observation.subscribe(state.inner().clone(), updates)
}

#[tauri::command]
pub fn sign_in_unsubscribe(state: State<'_, Arc<SignIn>>, subscription: u32) {
    state.observation.unsubscribe(subscription);
}

#[cfg(test)]
mod tests {
    use super::super::wire::Presence;
    use super::*;
    use tauri::ipc::InvokeResponseBody;

    fn listener(observer: &Observer, frames: Arc<Mutex<Vec<serde_json::Value>>>) -> u32 {
        let channel = Channel::new(move |body| {
            let InvokeResponseBody::Json(body) = body else {
                panic!("expected JSON observation")
            };
            frames
                .lock()
                .unwrap()
                .push(serde_json::from_str(&body).unwrap());
            Ok(())
        });
        let id = channel.id();
        *observer.listener.lock().unwrap() = Some(Listener {
            channel,
            previous: None,
            revision: 0,
        });
        id
    }

    #[test]
    fn public_snapshots_coalesce_and_report_profile_logout_runtime_and_read_failures() {
        let observer = Observer::default();
        let frames = Arc::new(Mutex::new(Vec::new()));
        listener(&observer, frames.clone());
        let mut status = SignInStatus {
            supported: true,
            state: Presence::Present,
            active_profile: Some("A".into()),
            runtime_available: true,
            refusal: None,
        };
        observer.publish(Ok(status.clone()));
        observer.publish(Ok(status.clone()));
        status.active_profile = Some("B".into());
        observer.publish(Ok(status.clone()));
        status.state = Presence::Absent;
        observer.publish(Ok(status.clone()));
        status.runtime_available = false;
        observer.publish(Ok(status));
        observer.publish(Err(super::super::failure(ErrorCode::SessionUnavailable)));
        observer.publish(Err(super::super::failure(ErrorCode::SessionUnavailable)));
        let frames = frames.lock().unwrap();
        assert_eq!(frames.len(), 5);
        for (index, frame) in frames.iter().enumerate() {
            assert_eq!(frame["revision"], index + 1);
        }
        assert_eq!(frames[0]["status"]["state"], "present");
        assert_eq!(frames[1]["status"]["active_profile"], "B");
        assert_eq!(frames[2]["status"]["state"], "absent");
        assert_eq!(frames[3]["status"]["runtimeAvailable"], false);
        assert_eq!(frames[4]["kind"], "sign-in-observation-failed");
        assert_eq!(frames[0]["status"].as_object().unwrap().len(), 5);
    }

    #[test]
    fn old_document_unsubscribe_does_not_remove_replacement() {
        let observer = Observer::default();
        let frames = Arc::new(Mutex::new(Vec::new()));
        let first = listener(&observer, frames.clone());
        let replacement = listener(&observer, frames.clone());
        observer.unsubscribe(first);
        observer.publish(Ok(SignInStatus::unsupported()));
        assert_eq!(frames.lock().unwrap().len(), 1);
        observer.unsubscribe(replacement);
        observer.publish(Ok(SignInStatus::unsupported()));
        assert_eq!(frames.lock().unwrap().len(), 1);
        observer.close();
        assert!(observer.closed.load(Ordering::Acquire));
    }
}
