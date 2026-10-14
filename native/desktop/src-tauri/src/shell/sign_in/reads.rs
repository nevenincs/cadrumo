//! Share an in-flight canonical observation, never a completed cached status.
use super::{failure, wire::SignInStatus};
use cadrumo_application::error::application::{ErrorCode, Result};
use std::{
    future::Future,
    sync::{Arc, Mutex},
};
use tokio::sync::watch;

type Answer = Option<Result<SignInStatus>>;

#[derive(Default)]
struct Active {
    epoch: u64,
    mutations: usize,
    pending: Option<watch::Receiver<Answer>>,
}

#[derive(Default)]
pub(super) struct Reads {
    active: Mutex<Active>,
}

pub(super) struct Mutation<'a>(&'a Reads);

impl Reads {
    pub(super) fn mutating(&self) -> bool {
        self.active.lock().unwrap_or_else(|e| e.into_inner()).mutations != 0
    }

    pub(super) fn mutation(&self) -> Mutation<'_> {
        let mut active = self.active.lock().unwrap_or_else(|e| e.into_inner());
        active.epoch += 1;
        active.mutations += 1;
        active.pending = None;
        Mutation(self)
    }

    pub(super) async fn read<F, Fut>(self: &Arc<Self>, fetch: F) -> Result<SignInStatus>
    where
        F: FnOnce() -> Fut + Send + 'static,
        Fut: Future<Output = Result<SignInStatus>> + Send,
    {
        let (epoch, mut receiver) = {
            let mut active = self
                .active
                .lock()
                .map_err(|_| failure(ErrorCode::LockPoisoned))?;
            if active.mutations != 0 {
                return Err(failure(ErrorCode::SessionUnavailable));
            }
            let epoch = active.epoch;
            let receiver = if let Some(pending) = &active.pending {
                pending.clone()
            } else {
                let (sender, receiver) = watch::channel(None);
                active.pending = Some(receiver.clone());
                let owner = self.clone();
                // A caller going away must not cancel the shared child or strand
                // the other callers. The child remains owned by Children.
                tokio::spawn(async move {
                    let answer = fetch().await;
                    let mut active = owner.active.lock().unwrap_or_else(|e| e.into_inner());
                    if active.epoch == epoch {
                        active.pending = None;
                    }
                    let _ = sender.send(Some(answer));
                });
                receiver
            };
            (epoch, receiver)
        };
        receiver
            .wait_for(Option::is_some)
            .await
            .map_err(|_| failure(ErrorCode::SessionUnavailable))?;
        let active = self
            .active
            .lock()
            .map_err(|_| failure(ErrorCode::LockPoisoned))?;
        // Neither an old profile nor a read crossing logout can authorize a
        // service start. A later poll obtains a new canonical observation.
        if active.epoch != epoch || active.mutations != 0 {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        receiver
            .borrow()
            .clone()
            .ok_or_else(|| failure(ErrorCode::SessionUnavailable))?
    }
}

impl Drop for Mutation<'_> {
    fn drop(&mut self) {
        let mut active = self.0.active.lock().unwrap_or_else(|e| e.into_inner());
        active.epoch += 1;
        active.mutations -= 1;
        active.pending = None;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use tokio::sync::Notify;

    #[tokio::test]
    async fn overlapping_readers_share_one_child_but_later_reads_are_fresh() {
        let reads = Arc::new(Reads::default());
        let calls = Arc::new(AtomicUsize::new(0));
        let release = Arc::new(Notify::new());
        let fetch = || {
            let calls = calls.clone();
            let release = release.clone();
            move || async move {
                calls.fetch_add(1, Ordering::SeqCst);
                release.notified().await;
                Ok(SignInStatus::unsupported())
            }
        };
        let a = reads.read(fetch());
        let b = reads.read(fetch());
        let unblock = async {
            while calls.load(Ordering::SeqCst) == 0 {
                tokio::task::yield_now().await;
            }
            release.notify_one();
        };
        let (a, b, ()) = tokio::join!(a, b, unblock);
        assert!(a.is_ok() && b.is_ok());
        assert_eq!(calls.load(Ordering::SeqCst), 1);
        reads
            .read(move || async move { Err(failure(ErrorCode::ReadFailed)) })
            .await
            .unwrap_err();
    }

    #[tokio::test]
    async fn mutation_fences_old_results_and_refuses_reads_until_settled() {
        let reads = Arc::new(Reads::default());
        let started = Arc::new(Notify::new());
        let release = Arc::new(Notify::new());
        let start = started.clone();
        let end = release.clone();
        let read = reads.read(move || async move {
            start.notify_one();
            end.notified().await;
            Ok(SignInStatus::unsupported())
        });
        let mutate = async {
            started.notified().await;
            let mutation = reads.mutation();
            let result = reads
                .read(|| async { panic!("must not spawn during mutation") })
                .await;
            assert_eq!(result.unwrap_err().code, ErrorCode::SessionUnavailable);
            drop(mutation);
            release.notify_one();
        };
        let (result, ()) = tokio::join!(read, mutate);
        assert_eq!(result.unwrap_err().code, ErrorCode::SessionUnavailable);
        assert!(
            reads
                .read(|| async { Ok(SignInStatus::unsupported()) })
                .await
                .is_ok()
        );
    }

    #[tokio::test]
    async fn cancelled_waiter_does_not_cancel_shared_observation() {
        let reads = Arc::new(Reads::default());
        let release = Arc::new(Notify::new());
        let started = Arc::new(Notify::new());
        let owner = reads.clone();
        let end = release.clone();
        let start = started.clone();
        let waiter = tokio::spawn(async move {
            owner
                .read(move || async move {
                    start.notify_one();
                    end.notified().await;
                    Ok(SignInStatus::unsupported())
                })
                .await
        });
        started.notified().await;
        waiter.abort();
        let remaining = reads.read(|| async { panic!("must share existing child") });
        let (result, ()) = tokio::join!(remaining, async {
            release.notify_one();
        });
        assert!(result.is_ok());
    }
}
