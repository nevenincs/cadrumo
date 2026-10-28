//! The window's one sign-in observation, read on the window's own runtime connection.
//!
//! The shell connects to the runtime that serves its storage root, asks which
//! profile is selected and whether its sign-in is stored, and reads again on
//! every cue the runtime pushes. Nothing here reads on a timer. A sign-in,
//! sign-out or profile creation from this window fences the observation:
//! until a read after it, no consumer acts on a status that may predate it.
//! Until the runtime serves the root, the observation says so, and the
//! connection is tried again with a growing pause.

use super::{
    failure,
    wire::{Presence, Refusal, SignInStatus},
};
use cadrumo_application::error::application::{ErrorCode, Result};
use std::{
    path::PathBuf,
    sync::{
        Arc, Mutex, MutexGuard,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::Duration,
};
use tokio::sync::watch;

/// Waits between attempts to reach a runtime that is not serving the root yet.
const RETRY: [Duration; 4] = [
    Duration::from_millis(500),
    Duration::from_secs(1),
    Duration::from_secs(3),
    Duration::from_secs(10),
];

/// What the connection to this window's runtime is made from.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Native {
    /// The storage root the runtime serves; its identity names the endpoint.
    pub storage_root: PathBuf,
    /// The installed product version the runtime must also be.
    pub product_version: String,
}

/// One observation: the public status and the private identity of its profile,
/// and the profiles on this computer when they were listed.
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Observed {
    pub status: SignInStatus,
    pub profile_id: Option<String>,
    pub profiles: Option<super::wire::ProfileList>,
}

#[derive(Clone)]
struct Snapshot {
    sequence: u64,
    value: Option<Result<Observed>>,
}

#[derive(Default)]
struct Fence {
    mutations: usize,
    /// Observations up to this sequence may predate a finished mutation.
    stale_through: u64,
}

/// Why the observing loop should read again or stop.
enum Wake {
    /// A mutation of this window finished: read again even if nothing changed.
    Forced,
    /// The runtime cued a change.
    Changed,
    /// The connection ended.
    Lost,
    Stop,
}

struct Inner {
    native: Result<Native>,
    snapshot: watch::Sender<Snapshot>,
    fence: Mutex<Fence>,
    wakes: Mutex<Option<mpsc::Sender<Wake>>>,
    #[cfg(windows)]
    connection: Mutex<Option<Arc<cadrumo_application::runtime_client::Connection>>>,
    started: AtomicBool,
    closed: AtomicBool,
    stopping: Mutex<Option<mpsc::Sender<()>>>,
    worker: Mutex<Option<thread::JoinHandle<()>>>,
}

fn lock<T>(value: &Mutex<T>) -> MutexGuard<'_, T> {
    value.lock().unwrap_or_else(|error| error.into_inner())
}

#[derive(Clone)]
pub(super) struct Watch {
    inner: Arc<Inner>,
}

/// A mutation from this window in progress; dropping it asks for a fresh read.
pub(super) struct Mutation<'a>(&'a Watch);

impl Watch {
    pub(super) fn new(native: Result<Native>) -> Self {
        let (snapshot, _) = watch::channel(Snapshot {
            sequence: 0,
            value: None,
        });
        Self {
            inner: Arc::new(Inner {
                native,
                snapshot,
                fence: Mutex::new(Fence::default()),
                wakes: Mutex::new(None),
                #[cfg(windows)]
                connection: Mutex::new(None),
                started: AtomicBool::new(false),
                closed: AtomicBool::new(false),
                stopping: Mutex::new(None),
                worker: Mutex::new(None),
            }),
        }
    }

    /// The current observation once it is known and postdates every mutation of this window.
    pub(super) async fn current(&self) -> Result<Observed> {
        self.start();
        let mut receiver = self.inner.snapshot.subscribe();
        loop {
            {
                let fence = lock(&self.inner.fence);
                if fence.mutations != 0 {
                    return Err(failure(ErrorCode::SessionUnavailable)
                        .with_reason("sign_in_mutation_in_progress"));
                }
                let snapshot = receiver.borrow_and_update();
                if snapshot.sequence > fence.stale_through
                    && let Some(value) = &snapshot.value
                {
                    return value.clone();
                }
            }
            receiver
                .changed()
                .await
                .map_err(|_| failure(ErrorCode::SessionUnavailable))?;
        }
    }

    /// The current observation if one is already known and fresh; never waits.
    pub(super) fn latest(&self) -> Result<Observed> {
        let fence = lock(&self.inner.fence);
        let snapshot = self.inner.snapshot.borrow();
        if fence.mutations != 0 || snapshot.sequence <= fence.stale_through {
            return Err(failure(ErrorCode::SessionUnavailable));
        }
        snapshot
            .value
            .clone()
            .unwrap_or_else(|| Err(failure(ErrorCode::SessionUnavailable)))
    }

    /// Resolves at the next observation after this call. Create it before reading,
    /// so an observation arriving meanwhile is not missed.
    pub(super) fn changed(&self) -> impl Future<Output = ()> + Send + 'static {
        let mut receiver = self.inner.snapshot.subscribe();
        async move {
            if receiver.changed().await.is_err() {
                // The window is going away; nothing will change any more.
                std::future::pending::<()>().await;
            }
        }
    }

    pub(super) fn mutating(&self) -> bool {
        lock(&self.inner.fence).mutations != 0
    }

    pub(super) fn mutation(&self) -> Mutation<'_> {
        lock(&self.inner.fence).mutations += 1;
        Mutation(self)
    }

    fn start(&self) {
        if self.inner.closed.load(Ordering::Acquire)
            || self.inner.started.swap(true, Ordering::AcqRel)
        {
            return;
        }
        let (stop, stopping) = mpsc::channel();
        *lock(&self.inner.stopping) = Some(stop);
        let inner = self.inner.clone();
        let worker = thread::Builder::new()
            .name("sign-in-watch".into())
            .spawn(move || supervise(&inner, &stopping));
        match worker {
            Ok(worker) => *lock(&self.inner.worker) = Some(worker),
            Err(_) => publish(&self.inner, Err(failure(ErrorCode::SpawnFailed))),
        }
    }

    /// Ends the connection and waits for the watch to settle. It only reads
    /// status, so ending it at once loses nothing.
    pub(super) fn close(&self) {
        self.inner.closed.store(true, Ordering::Release);
        lock(&self.inner.stopping).take();
        if let Some(wakes) = lock(&self.inner.wakes).take() {
            let _ = wakes.send(Wake::Stop);
        }
        #[cfg(windows)]
        if let Some(connection) = lock(&self.inner.connection).take() {
            connection.close();
        }
        let worker = lock(&self.inner.worker).take();
        if let Some(worker) = worker {
            let _ = worker.join();
        }
    }
}

impl Drop for Mutation<'_> {
    fn drop(&mut self) {
        let inner = &self.0.inner;
        {
            let mut fence = lock(&inner.fence);
            fence.mutations -= 1;
            fence.stale_through = inner.snapshot.borrow().sequence;
        }
        // A forced read gives the next observation even when nothing changed.
        if let Some(wakes) = lock(&inner.wakes).as_ref() {
            let _ = wakes.send(Wake::Forced);
        }
    }
}

fn publish(inner: &Inner, value: Result<Observed>) {
    inner.snapshot.send_modify(|snapshot| {
        snapshot.sequence += 1;
        snapshot.value = Some(value);
    });
}

/// The observation while the runtime cannot be reached or refuses: `code` is
/// what the runtime's own clients report for the same state.
fn refused(code: &str) -> Observed {
    Observed {
        status: SignInStatus {
            supported: true,
            state: Presence::Unknown,
            active_profile: None,
            runtime_available: code != "runtime_unavailable",
            reconnecting: None,
            refusal: Some(Refusal {
                code: code.to_owned(),
                retry_after_seconds: None,
            }),
        },
        profile_id: None,
        profiles: None,
    }
}

/// Observes for as long as the window lives, trying again when the runtime is
/// not there yet or the connection ends.
fn supervise(inner: &Arc<Inner>, stopping: &mpsc::Receiver<()>) {
    let mut retries = 0usize;
    while !inner.closed.load(Ordering::Acquire) {
        match run(inner) {
            Ok(true) => retries = 0,
            Ok(false) => {}
            Err(error) => publish(inner, Err(error)),
        }
        if inner.closed.load(Ordering::Acquire) {
            return;
        }
        let delay = RETRY[retries.min(RETRY.len() - 1)];
        retries += 1;
        // Only closing ends this wait early; it is the bounded pause before a retry.
        if !matches!(
            stopping.recv_timeout(delay),
            Err(mpsc::RecvTimeoutError::Timeout)
        ) {
            return;
        }
    }
}

/// One connection's life: whether it was connected at all, so a retry after a
/// served stretch starts its pauses over.
#[cfg(windows)]
fn run(inner: &Inner) -> Result<bool> {
    use cadrumo_application::runtime_client::{Cohort, Connection, Endpoint, Event};
    use std::time::Instant;

    const CONNECT: Duration = Duration::from_secs(10);

    let native = inner.native.as_ref().map_err(Clone::clone)?;
    let (wake, wakes) = mpsc::channel();
    *lock(&inner.wakes) = Some(wake.clone());
    if inner.closed.load(Ordering::Acquire) {
        return Ok(false);
    }
    let cohort = Cohort {
        product_version: native.product_version.clone(),
        authority_generation: None,
    };
    let connected = Endpoint::of(&native.storage_root)
        .and_then(|endpoint| Connection::open(&endpoint, &cohort, Instant::now() + CONNECT));
    let connection = match connected {
        Ok(connection) => Arc::new(connection),
        Err(refusal) => {
            publish(inner, Ok(refused(&unavailable_code(&refusal))));
            return Ok(false);
        }
    };
    *lock(&inner.connection) = Some(connection.clone());
    let events = connection.subscribe();
    let forward = wake;
    let forwarding = thread::Builder::new()
        .name("sign-in-watch-events".into())
        .spawn(move || {
            for event in events {
                let wake = match event {
                    Event::SignInChanged => Wake::Changed,
                    Event::Disconnected => Wake::Lost,
                    _ => continue,
                };
                let lost = matches!(wake, Wake::Lost);
                if forward.send(wake).is_err() || lost {
                    return;
                }
            }
        });
    let result = match forwarding {
        Ok(_) => follow(inner, &connection, &wakes),
        Err(_) => Err(failure(ErrorCode::SpawnFailed)),
    };
    lock(&inner.connection).take();
    connection.close();
    result.map(|()| true)
}

#[cfg(not(windows))]
fn run(_: &Inner) -> Result<bool> {
    Err(failure(ErrorCode::UnsupportedPlatform))
}

#[cfg(windows)]
fn unavailable_code(refusal: &cadrumo_application::runtime_client::Refusal) -> String {
    use cadrumo_application::runtime_client::Refusal;
    match refusal {
        // Not serving the root yet, gone, or unreachable: the runtime is unavailable.
        Refusal::EndpointNotReady
        | Refusal::ConnectionClosed
        | Refusal::Unavailable
        | Refusal::Io(_) => "runtime_unavailable".to_owned(),
        other => other.code().to_owned(),
    }
}

/// Reads the observation and publishes it on every cue, until the connection
/// ends or the window closes.
#[cfg(windows)]
fn follow(
    inner: &Inner,
    connection: &cadrumo_application::runtime_client::Connection,
    wakes: &mpsc::Receiver<Wake>,
) -> Result<()> {
    loop {
        match observe(connection) {
            Ok(observed) => publish(inner, Ok(observed)),
            Err(refusal) => {
                publish(inner, Ok(refused(&unavailable_code(&refusal))));
                return Ok(());
            }
        }
        match wakes.recv() {
            Ok(Wake::Forced | Wake::Changed) => {}
            Ok(Wake::Lost) => {
                publish(inner, Ok(refused("runtime_unavailable")));
                return Ok(());
            }
            Ok(Wake::Stop) | Err(_) => return Ok(()),
        }
    }
}

/// The selected profile, its label and its stored sign-in, each asked of the
/// runtime, which also cues this connection on every later change.
#[cfg(windows)]
fn observe(
    connection: &cadrumo_application::runtime_client::Connection,
) -> std::result::Result<Observed, cadrumo_application::runtime_client::Refusal> {
    use std::time::Instant;

    const EXCHANGE: Duration = Duration::from_secs(30);

    let deadline = Instant::now() + EXCHANGE;
    let active = connection.active_profile(true, deadline)?;
    let Some(profile_id) = active.selected_profile_id else {
        return Ok(Observed {
            status: SignInStatus {
                supported: true,
                state: Presence::Absent,
                active_profile: None,
                runtime_available: true,
                reconnecting: None,
                refusal: None,
            },
            profile_id: None,
            profiles: None,
        });
    };
    let label = connection
        .login_target(&profile_id, deadline)?
        .map(|(_, label)| label);
    let status = connection.sign_in_status(&profile_id, true, deadline)?;
    Ok(Observed {
        status: SignInStatus {
            supported: true,
            state: presence(&status.presence),
            active_profile: label,
            runtime_available: true,
            reconnecting: None,
            refusal: None,
        },
        profile_id: Some(profile_id),
        profiles: None,
    })
}

fn presence(text: &str) -> Presence {
    match text {
        "present" => Presence::Present,
        "absent" => Presence::Absent,
        _ => Presence::Unknown,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_refusal_names_whether_the_runtime_is_there() {
        let gone = refused("runtime_unavailable");
        assert!(!gone.status.runtime_available);
        assert_eq!(gone.status.state, Presence::Unknown);
        assert_eq!(gone.status.refusal.unwrap().code, "runtime_unavailable");
        let untrusted = refused("runtime_peer_untrusted");
        assert!(untrusted.status.runtime_available && !untrusted.status.runtime_ready());
        assert_eq!(presence("present"), Presence::Present);
        assert_eq!(presence("absent"), Presence::Absent);
        assert_eq!(presence("whatever"), Presence::Unknown);
    }

    #[cfg(windows)]
    #[test]
    fn transport_refusals_read_as_an_unavailable_runtime_and_others_keep_their_code() {
        use cadrumo_application::runtime_client::Refusal;
        for refusal in [
            Refusal::EndpointNotReady,
            Refusal::ConnectionClosed,
            Refusal::Unavailable,
            Refusal::Io(std::io::ErrorKind::Other.into()),
        ] {
            assert_eq!(unavailable_code(&refusal), "runtime_unavailable");
        }
        assert_eq!(
            unavailable_code(&Refusal::VersionMismatch),
            "runtime_version_mismatch"
        );
        assert_eq!(
            unavailable_code(&Refusal::denied("profile_locked")),
            "profile_locked"
        );
    }

    #[tokio::test]
    async fn a_mutation_fences_observations_until_one_arrives_after_it() {
        let watch = Watch::new(Err(failure(ErrorCode::PackageUnavailable)));
        // No connection is made for this test: observations are published directly.
        watch.inner.started.store(true, Ordering::Release);
        let present = Observed {
            status: SignInStatus {
                supported: true,
                state: Presence::Present,
                active_profile: Some("Ana".into()),
                runtime_available: true,
                reconnecting: None,
                refusal: None,
            },
            profile_id: None,
            profiles: None,
        };
        publish(&watch.inner, Ok(present.clone()));
        assert_eq!(watch.current().await.unwrap(), present);
        let mutation = watch.mutation();
        let pending = watch.current().await.unwrap_err();
        assert_eq!(pending.code, ErrorCode::SessionUnavailable);
        assert_eq!(
            pending.reason.as_deref(),
            Some("sign_in_mutation_in_progress")
        );
        drop(mutation);
        assert!(
            watch.latest().is_err(),
            "an observation from before the mutation is stale"
        );
        let changed = watch.changed();
        let mut absent = present.clone();
        absent.status.state = Presence::Absent;
        let waiting = {
            let expected = absent.clone();
            let current = watch.current();
            async move { assert_eq!(current.await.unwrap(), expected) }
        };
        let publishing = async {
            tokio::task::yield_now().await;
            publish(&watch.inner, Ok(absent.clone()));
        };
        tokio::join!(waiting, publishing);
        changed.await;
        assert_eq!(watch.latest().unwrap(), absent);
    }

    #[test]
    fn a_watch_without_a_runtime_description_reports_that_and_stops_when_closed() {
        let watch = Watch::new(Err(failure(ErrorCode::PackageUnavailable)));
        let mut receiver = watch.inner.snapshot.subscribe();
        watch.start();
        // The first attempt publishes the description's own failure.
        let deadline = std::time::Instant::now() + Duration::from_secs(5);
        while receiver.borrow_and_update().value.is_none() {
            assert!(
                std::time::Instant::now() < deadline,
                "no observation was published"
            );
            thread::sleep(Duration::from_millis(10));
        }
        assert_eq!(
            watch.latest().unwrap_err().code,
            ErrorCode::PackageUnavailable
        );
        watch.close();
        assert!(lock(&watch.inner.worker).is_none());
    }
}
