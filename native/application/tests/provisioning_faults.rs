//! The pinned transfer's faults the engine's own unit tests leave open, driven through the
//! public `provisioning::transfer` API against real local TLS servers.
//!
//! The rest of the fault set is proven in `src/provisioning/transfer.rs`, against the same
//! servers: a timed-out connection and a stalled body (`a_stalled_body_or_an_unresolvable_
//! name_is_a_transient_host_failure`), HTTP 5xx and 429 (`transient_statuses_are_retried_
//! within_the_budget_and_then_reported_final`), a truncated body
//! (`a_truncated_body_is_retried_after_the_announced_wait_and_resumed`), a wrong digest
//! (`permanent_statuses_and_damaged_bytes_are_final_on_the_first_attempt`), an unapproved
//! redirect hop (`redirects_follow_only_approved_https_hops_on_the_default_port_and_at_most_
//! five`), resume of partial bytes (`partial_bytes_resume_with_a_range_and_a_server_
//! ignoring_it_restarts`) and cancellation (`cancellation_stops_between_chunks_and_during_
//! a_retry_wait`). Here: a connection dropped before its answer, a slow transfer that keeps
//! moving, an interruption resumed by the next run, and a full disk.
//!
//! Where it stops: the full disk is the kernel's `/dev/full`, so that case runs on Linux
//! only; Windows and macOS have no device that fails every write with "no space". The
//! retry clock is recorded rather than real, so no case waits. Built with the
//! `test-support` feature, which carries the local servers.
#![cfg(feature = "test-support")]

use cadrumo_application::{
    component::Cancellation,
    error::Error,
    provisioning::{
        test_servers::{
            Released, Reply, Request, TestCertificate, TlsServer, network_to, response,
        },
        transfer::{Pacing, Pinned, RetryPolicy, Transfer, TransferEvent},
        url::HttpsUrl,
    },
    value::{HostName, Sha256Digest},
};
use std::{
    collections::BTreeSet,
    path::Path,
    sync::{
        Arc,
        atomic::{AtomicUsize, Ordering},
    },
    time::Duration,
};

const HOST: &str = "cdn.example.com";
const SOURCE: &str = "https://cdn.example.com/a.zip";

/// A clock that advances by exactly what is waited, with fixed jitter.
#[derive(Default)]
struct RecordedPacing {
    now: Duration,
    waits: Vec<Duration>,
}

impl Pacing for RecordedPacing {
    fn elapsed(&self) -> Duration {
        self.now
    }
    fn wait(&mut self, delay: Duration, cancellation: &Cancellation) -> Result<(), Error> {
        if cancellation.is_cancelled() {
            return Err(Error::Cancelled);
        }
        self.waits.push(delay);
        self.now += delay;
        if cancellation.is_cancelled() {
            return Err(Error::Cancelled);
        }
        Ok(())
    }
    fn jitter(&mut self) -> f64 {
        0.5
    }
}

fn payload(size: usize) -> Vec<u8> {
    (0..size).map(|index| (index * 37 % 253) as u8).collect()
}

fn whole(bytes: &[u8]) -> Vec<u8> {
    response(
        "200 OK",
        &[("Content-Length", bytes.len().to_string())],
        bytes,
    )
}

/// Serves `bytes`, honouring a `Range` request.
fn ranged(request: &Request, bytes: &[u8]) -> Reply {
    let start = request
        .header("range")
        .and_then(|range| range.strip_prefix("bytes="))
        .and_then(|range| range.strip_suffix('-'))
        .and_then(|start| start.parse::<usize>().ok());
    match start {
        Some(start) => Reply::Bytes(response(
            "206 Partial Content",
            &[
                ("Content-Length", (bytes.len() - start).to_string()),
                (
                    "Content-Range",
                    format!("bytes {start}-{}/{}", bytes.len() - 1, bytes.len()),
                ),
            ],
            &bytes[start..],
        )),
        None => Reply::Bytes(whole(bytes)),
    }
}

struct Run {
    result: Result<(), Error>,
    events: Vec<TransferEvent>,
    waits: Vec<Duration>,
}

/// Fetches `bytes` from `server` into `partial`, telling `on_event` of every event.
fn fetch(
    certificate: &TestCertificate,
    server: &TlsServer,
    bytes: &[u8],
    partial: &Path,
    cancellation: &Cancellation,
    mut on_event: impl FnMut(&TransferEvent),
) -> Run {
    let network = network_to(certificate.roots(), server.address(), None);
    let hosts: BTreeSet<HostName> = [HostName::new(HOST).unwrap()].into_iter().collect();
    let sources = [HttpsUrl::parse(SOURCE).unwrap()];
    let digest = Sha256Digest::of(bytes);
    let mut pacing = RecordedPacing::default();
    let mut events = Vec::new();
    let result = {
        let mut sink = |event: TransferEvent| {
            on_event(&event);
            events.push(event);
        };
        Transfer {
            network: &network,
            hosts: &hosts,
            policy: RetryPolicy::default(),
            pacing: &mut pacing,
            events: &mut sink,
            cancellation,
        }
        .fetch(
            Pinned {
                sources: &sources,
                size: bytes.len() as u64,
                sha256: &digest,
            },
            partial,
        )
    };
    Run {
        result,
        events,
        waits: pacing.waits,
    }
}

#[test]
fn a_connection_dropped_before_its_answer_is_transient_and_the_retry_completes() {
    let bytes = payload(90_000);
    let answered = AtomicUsize::new(0);
    let served = bytes.clone();
    let certificate = TestCertificate::new(&[HOST]);
    let server = TlsServer::start(&certificate, move |request: &Request| {
        if answered.fetch_add(1, Ordering::SeqCst) == 0 {
            // The request is read and the connection goes away with no answer and no TLS close.
            return Reply::Cut(Vec::new());
        }
        ranged(request, &served)
    });
    let directory = tempfile::tempdir().unwrap();
    let partial = directory.path().join("a.part");
    let run = fetch(
        &certificate,
        &server,
        &bytes,
        &partial,
        &Cancellation::default(),
        |_| {},
    );
    run.result.unwrap();
    assert_eq!(std::fs::read(&partial).unwrap(), bytes);
    assert_eq!(
        run.waits,
        [Duration::from_millis(2500)],
        "one announced wait"
    );
    assert!(run.events.contains(&TransferEvent::Retrying {
        attempt: 2,
        delay: Duration::from_millis(2500)
    }));
    assert_eq!(server.targets(), ["/a.zip", "/a.zip"]);
}

#[test]
fn a_slow_transfer_that_keeps_moving_completes_without_a_retry() {
    let bytes = payload(300_000);
    let gate = Arc::new(Released::default());
    let split = bytes.len() / 3;
    let mut first = response(
        "200 OK",
        &[("Content-Length", bytes.len().to_string())],
        b"",
    );
    first.extend_from_slice(&bytes[..split]);
    let rest = bytes[split..].to_vec();
    let served = gate.clone();
    let certificate = TestCertificate::new(&[HOST]);
    let server = TlsServer::start(&certificate, move |_: &Request| Reply::Gated {
        first: first.clone(),
        rest: rest.clone(),
        gate: served.clone(),
    });
    let directory = tempfile::tempdir().unwrap();
    let partial = directory.path().join("a.part");
    // The publisher holds the rest of the body until the client has reported the bytes it
    // already has: the transfer pauses mid-body, then carries on.
    let released = gate.clone();
    let run = fetch(
        &certificate,
        &server,
        &bytes,
        &partial,
        &Cancellation::default(),
        move |event| {
            if let TransferEvent::Progress { completed, .. } = event
                && *completed >= split as u64
            {
                released.release();
            }
        },
    );
    run.result.unwrap();
    assert_eq!(std::fs::read(&partial).unwrap(), bytes);
    assert!(run.waits.is_empty(), "a slow body is not a failure");
    let completed: Vec<u64> = run
        .events
        .iter()
        .map(|event| match event {
            TransferEvent::Progress { completed, .. } => *completed,
            other => panic!("a slow transfer retried: {other:?}"),
        })
        .collect();
    assert!(completed.windows(2).all(|pair| pair[0] < pair[1]));
    assert_eq!(completed.last(), Some(&(bytes.len() as u64)));
    assert_eq!(server.targets(), ["/a.zip"]);
}

#[test]
fn an_interrupted_transfer_is_resumed_from_its_partial_bytes_by_the_next_run() {
    let bytes = payload(400_000);
    let served = bytes.clone();
    let certificate = TestCertificate::new(&[HOST]);
    let server = TlsServer::start(&certificate, move |request: &Request| {
        ranged(request, &served)
    });
    let directory = tempfile::tempdir().unwrap();
    let partial = directory.path().join("a.part");

    let interrupted = Cancellation::default();
    let first = fetch(
        &certificate,
        &server,
        &bytes,
        &partial,
        &interrupted,
        |event| {
            if let TransferEvent::Progress { .. } = event {
                interrupted.cancel();
            }
        },
    );
    assert!(matches!(first.result, Err(Error::Cancelled)));
    let kept = std::fs::metadata(&partial).unwrap().len();
    assert!(
        kept > 0 && kept < bytes.len() as u64,
        "the interruption keeps the bytes it held: {kept}"
    );

    let resumed = fetch(
        &certificate,
        &server,
        &bytes,
        &partial,
        &Cancellation::default(),
        |_| {},
    );
    resumed.result.unwrap();
    assert_eq!(std::fs::read(&partial).unwrap(), bytes);
    let requests = server.requests.lock().unwrap();
    assert_eq!(requests.len(), 2);
    assert_eq!(
        requests[1].header("range"),
        Some(format!("bytes={kept}-").as_str()),
        "the next run asks only for what is missing"
    );
    assert!(matches!(
        resumed.events.first(),
        Some(TransferEvent::Progress { completed, .. }) if *completed > kept
    ));
}

#[cfg(target_os = "linux")]
#[test]
fn a_full_disk_is_final_and_tries_no_other_source() {
    use cadrumo_application::provisioning::failure::FailureCategory;

    let bytes = payload(100_000);
    let served = bytes.clone();
    let certificate = TestCertificate::new(&[HOST]);
    let server = TlsServer::start(&certificate, move |_: &Request| {
        Reply::Bytes(whole(&served))
    });
    // Every write to the kernel's full device fails with "no space left on device".
    let run = fetch(
        &certificate,
        &server,
        &bytes,
        Path::new("/dev/full"),
        &Cancellation::default(),
        |_| {},
    );
    let Err(Error::Download(failure)) = run.result else {
        panic!("expected a download failure, got {:?}", run.result);
    };
    assert_eq!(failure.category, FailureCategory::DiskFull);
    assert!(!failure.transient);
    assert_eq!(failure.attempts, 1);
    assert!(run.waits.is_empty(), "a full disk is not retried");
    assert_eq!(server.targets(), ["/a.zip"]);
}
