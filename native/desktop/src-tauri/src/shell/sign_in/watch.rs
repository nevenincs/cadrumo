//! The window's one sign-in observation, pushed by a long-lived `session watch` child.
//!
//! The shell holds no runtime connection; the child holds one, for status only,
//! and writes a line whenever what it observes changes. Nothing here reads on a
//! timer. A sign-in, sign-out or profile creation from this window fences the
//! observation: until the child has read again after it, no consumer acts on a
//! status that may predate it.

use super::{
    failure,
    wire::{Presence, Refusal, SignInStatus},
};
use cadrumo_application::{
    child::ChildConfiguration,
    error::application::{ErrorCode, Result},
};
use serde::Deserialize;
use std::{
    io::{BufRead, BufReader, Read, Write},
    process::{Child, ChildStdin, Stdio},
    sync::{
        Arc, Mutex, MutexGuard,
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    thread,
    time::Duration,
};
use tokio::sync::watch;

/// Waits between restarts of a child that ended on its own: restarting, not observing.
const RESTART: [Duration; 4] = [
    Duration::from_secs(1),
    Duration::from_secs(5),
    Duration::from_secs(15),
    Duration::from_secs(60),
];
/// The longest line the child writes, with room to spare.
const LINE_LIMIT: u64 = 16 * 1024;

/// One observation: the public status and the private identity of its profile.
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct Observed {
    pub status: SignInStatus,
    pub profile_id: Option<String>,
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

struct Inner {
    child: Result<ChildConfiguration>,
    snapshot: watch::Sender<Snapshot>,
    fence: Mutex<Fence>,
    input: Mutex<Option<ChildStdin>>,
    running: Mutex<Option<Child>>,
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

/// A mutation from this window in progress; dropping it asks the child to read again.
pub(super) struct Mutation<'a>(&'a Watch);

impl Watch {
    pub(super) fn new(child: Result<ChildConfiguration>) -> Self {
        let (snapshot, _) = watch::channel(Snapshot {
            sequence: 0,
            value: None,
        });
        Self {
            inner: Arc::new(Inner {
                child,
                snapshot,
                fence: Mutex::new(Fence::default()),
                input: Mutex::new(None),
                running: Mutex::new(None),
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
                    return Err(failure(ErrorCode::SessionUnavailable));
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

    /// Ends the child and waits for the watch to settle. The child only reads
    /// status, so ending it at once loses nothing.
    pub(super) fn close(&self) {
        self.inner.closed.store(true, Ordering::Release);
        lock(&self.inner.stopping).take();
        lock(&self.inner.input).take();
        if let Some(child) = lock(&self.inner.running).as_mut() {
            let _ = child.kill();
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
        if let Some(input) = lock(&inner.input).as_mut() {
            let _ = input.write_all(b"\n").and_then(|()| input.flush());
        }
    }
}

fn publish(inner: &Inner, value: Result<Observed>) {
    inner.snapshot.send_modify(|snapshot| {
        snapshot.sequence += 1;
        snapshot.value = Some(value);
    });
}

/// Runs the child for as long as the window lives, restarting one that ends on its own.
fn supervise(inner: &Arc<Inner>, stopping: &mpsc::Receiver<()>) {
    let mut restarts = 0usize;
    while !inner.closed.load(Ordering::Acquire) {
        match run(inner) {
            Ok(()) if inner.closed.load(Ordering::Acquire) => return,
            Ok(()) => publish(inner, Err(failure(ErrorCode::SessionUnavailable))),
            Err(error) => publish(inner, Err(error)),
        }
        let delay = RESTART[restarts.min(RESTART.len() - 1)];
        restarts += 1;
        // Only closing ends this wait early; it is the bounded pause before a restart.
        if !matches!(
            stopping.recv_timeout(delay),
            Err(mpsc::RecvTimeoutError::Timeout)
        ) {
            return;
        }
    }
}

fn run(inner: &Inner) -> Result<()> {
    let mut command = inner.child.as_ref().map_err(Clone::clone)?.command();
    command
        .args(["session", "watch"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x0800_0000);
    }
    let mut child = command.spawn().map_err(|error| {
        failure(ErrorCode::SpawnFailed)
            .with_reason("sign_in_watch_spawn")
            .caused_by(error)
    })?;
    let output = child.stdout.take();
    *lock(&inner.input) = child.stdin.take();
    *lock(&inner.running) = Some(child);
    if inner.closed.load(Ordering::Acquire) {
        lock(&inner.input).take();
    }
    let read = output
        .ok_or_else(|| failure(ErrorCode::ReadFailed).with_reason("sign_in_watch_stdout_missing"))
        .and_then(|output| follow(inner, output));
    lock(&inner.input).take();
    if let Some(mut child) = lock(&inner.running).take() {
        // Its output ended, so it is ending; a child that wrote a line it should
        // not have holds nothing this window needs either.
        let _ = child.kill();
        let _ = child.wait();
    }
    read
}

fn follow(inner: &Inner, output: std::process::ChildStdout) -> Result<()> {
    let mut reader = BufReader::new(output);
    loop {
        let mut line = Vec::with_capacity(256);
        let count = reader
            .by_ref()
            .take(LINE_LIMIT + 1)
            .read_until(b'\n', &mut line)
            .map_err(|error| {
                failure(ErrorCode::ReadFailed)
                    .with_reason("sign_in_watch_read")
                    .caused_by(error)
            })?;
        if count == 0 {
            return Ok(());
        }
        if line.last() != Some(&b'\n') {
            return Err(failure(ErrorCode::ReadFailed).with_reason("sign_in_watch_line"));
        }
        publish(inner, observed(&line));
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Line {
    kind: String,
    active_profile: Option<String>,
    profile_id: Option<String>,
    presence: Presence,
    refusal: Option<String>,
}

fn observed(line: &[u8]) -> Result<Observed> {
    let line: Line = serde_json::from_slice(line).map_err(|error| {
        failure(ErrorCode::ReadFailed)
            .with_reason("sign_in_watch_parse")
            .caused_by(error)
    })?;
    if line.kind != "sign_in"
        || line
            .profile_id
            .as_deref()
            .is_some_and(|id| !crate::shell::agent_access::wire::is_uuid(id))
    {
        return Err(failure(ErrorCode::ReadFailed).with_reason("sign_in_watch_shape"));
    }
    let status = match line.refusal {
        None => SignInStatus {
            supported: true,
            state: line.presence,
            active_profile: line.active_profile,
            runtime_available: true,
            refusal: None,
        },
        Some(code) => {
            if code.is_empty()
                || code.len() > 160
                || !code.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'_')
            {
                return Err(failure(ErrorCode::ReadFailed).with_reason("sign_in_watch_refusal"));
            }
            SignInStatus {
                supported: true,
                state: Presence::Unknown,
                active_profile: line.active_profile,
                runtime_available: code != "runtime_unavailable",
                refusal: Some(Refusal {
                    code,
                    retry_after_seconds: None,
                }),
            }
        }
    };
    Ok(Observed {
        status,
        profile_id: line.profile_id,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn line(text: &str) -> Result<Observed> {
        observed(format!("{text}\n").as_bytes())
    }

    #[test]
    fn a_line_maps_onto_the_status_the_window_already_shows() {
        let present = line(
            r#"{"kind":"sign_in","active_profile":"Ana","profile_id":"12345678-1234-4234-8234-123456789abc","presence":"present","refusal":null}"#,
        )
        .unwrap();
        assert_eq!(present.status.state, Presence::Present);
        assert!(present.status.runtime_ready());
        assert_eq!(
            present.profile_id.as_deref(),
            Some("12345678-1234-4234-8234-123456789abc")
        );
        let unavailable = line(
            r#"{"kind":"sign_in","active_profile":"Ana","profile_id":null,"presence":"unknown","refusal":"runtime_unavailable"}"#,
        )
        .unwrap();
        assert!(!unavailable.status.runtime_available);
        assert_eq!(
            unavailable.status.refusal.unwrap().code,
            "runtime_unavailable"
        );
        let refused = line(
            r#"{"kind":"sign_in","active_profile":null,"profile_id":null,"presence":"unknown","refusal":"peer_untrusted"}"#,
        )
        .unwrap();
        assert!(refused.status.runtime_available && refused.status.refusal.is_some());
        assert!(!refused.status.runtime_ready());
        let uncertain = line(
            r#"{"kind":"sign_in","active_profile":"Ana","profile_id":null,"presence":"unknown","refusal":null}"#,
        )
        .unwrap();
        assert!(uncertain.status.runtime_available && !uncertain.status.runtime_ready());
        let absent = line(
            r#"{"kind":"sign_in","active_profile":null,"profile_id":null,"presence":"absent","refusal":null}"#,
        )
        .unwrap();
        assert!(absent.status.runtime_ready());
        for invalid in [
            r#"{"kind":"other","active_profile":null,"profile_id":null,"presence":"absent","refusal":null}"#,
            r#"{"kind":"sign_in","active_profile":null,"profile_id":"not-a-uuid","presence":"absent","refusal":null}"#,
            r#"{"kind":"sign_in","active_profile":null,"profile_id":null,"presence":"absent","refusal":"has space"}"#,
            r#"{"kind":"sign_in","active_profile":null,"profile_id":null,"presence":"absent","refusal":null,"extra":1}"#,
        ] {
            assert_eq!(
                line(invalid).unwrap_err().code,
                ErrorCode::ReadFailed,
                "{invalid}"
            );
        }
    }

    #[tokio::test]
    async fn a_mutation_fences_observations_until_one_arrives_after_it() {
        let watch = Watch::new(Err(failure(ErrorCode::PackageUnavailable)));
        // No child is started for this test: observations are published directly.
        watch.inner.started.store(true, Ordering::Release);
        let present = Observed {
            status: SignInStatus {
                supported: true,
                state: Presence::Present,
                active_profile: Some("Ana".into()),
                runtime_available: true,
                refusal: None,
            },
            profile_id: None,
        };
        publish(&watch.inner, Ok(present.clone()));
        assert_eq!(watch.current().await.unwrap(), present);
        let mutation = watch.mutation();
        assert_eq!(
            watch.current().await.unwrap_err().code,
            ErrorCode::SessionUnavailable
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
}
