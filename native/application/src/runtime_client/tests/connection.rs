use super::super::connection::{Connection, ExchangeQueue, Shared, ready_for};
use super::super::events::{Event, Pushed, event};
use super::super::framing::{SECRET_FRAME, SUBMISSION_PAYLOAD_CHUNK_BYTES, frame};
use super::super::refusal::Refusal;
use super::super::timeout::TimeoutWait;
use serde_json::{Map, Value, json};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Condvar, Mutex, mpsc};
use std::thread;
use std::time::{Duration, Instant};

#[test]
fn an_expired_exchange_does_not_accept_a_buffered_reply() {
    let (sender, receiver) = mpsc::channel();
    sender.send(Map::new()).unwrap();
    assert!(matches!(
        Connection::next_reply(&receiver, Instant::now()),
        Err(Refusal::Timeout)
    ));
    assert!(
        Connection::next_reply(&receiver, Instant::now() + Duration::from_secs(1))
            .unwrap()
            .is_empty()
    );
}

#[test]
fn a_reply_wait_ends_at_its_deadline_without_waiting_for_sender_exit() {
    let (_sender, receiver) = mpsc::channel();
    assert!(matches!(
        Connection::next_reply(&receiver, Instant::now() + Duration::from_millis(20)),
        Err(Refusal::Timeout)
    ));
}

#[test]
fn a_queued_exchange_times_out_without_disturbing_the_owner() {
    let (sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(Some(receiver)),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let owner = queue
        .claim(Instant::now() + Duration::from_secs(2))
        .unwrap();
    let (done, finished) = mpsc::channel();
    let contender = {
        let queue = queue.clone();
        thread::spawn(move || {
            let timed_out = matches!(
                queue.claim(Instant::now() + Duration::from_millis(50)),
                Err(Refusal::Timeout)
            );
            done.send(timed_out).unwrap();
        })
    };
    let timed_out = finished.recv_timeout(Duration::from_secs(2));
    sender.send(Map::new()).unwrap();
    assert!(
        owner
            .recv_timeout(Duration::from_secs(1))
            .unwrap()
            .is_empty()
    );
    drop(owner);
    contender.join().unwrap();
    assert!(timed_out.unwrap());
    assert!(queue.claim(Instant::now() + Duration::from_secs(1)).is_ok());
}

#[test]
fn close_serializes_with_the_claim_check_before_condvar_wait() {
    let (_sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(Some(receiver)),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let owner = queue.claim(TimeoutWait::new().deadline()).unwrap();
    let (at_gap, gap) = mpsc::channel();
    let (resume, resumed) = mpsc::channel();
    let (answer, answered) = mpsc::channel();
    let waiter = {
        let queue = queue.clone();
        thread::spawn(move || {
            let result = queue.claim_observed(TimeoutWait::new().deadline(), || {
                at_gap.send(()).unwrap();
                resumed.recv().unwrap();
            });
            answer
                .send(matches!(result, Err(Refusal::ConnectionClosed)))
                .unwrap();
        })
    };
    gap.recv_timeout(Duration::from_secs(5)).unwrap();
    let (started, starting) = mpsc::channel();
    let (closed, closing) = mpsc::channel();
    let closer = {
        let queue = queue.clone();
        thread::spawn(move || {
            started.send(()).unwrap();
            queue.close();
            closed.send(()).unwrap();
        })
    };
    starting.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(
        closing.recv_timeout(Duration::from_millis(50)).is_err(),
        "close must serialize with the held reply mutex"
    );
    resume.send(()).unwrap();
    assert!(answered.recv_timeout(Duration::from_secs(5)).unwrap());
    closing.recv_timeout(Duration::from_secs(5)).unwrap();
    waiter.join().unwrap();
    closer.join().unwrap();
    drop(owner);
}

#[test]
fn closing_wakes_a_queued_slot_without_waiting_for_the_startup_timeout() {
    let (_sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(Some(receiver)),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let owner = queue.claim(TimeoutWait::new().deadline()).unwrap();
    let (started, waiting) = mpsc::channel();
    let contender = {
        let queue = queue.clone();
        thread::spawn(move || {
            started.send(()).unwrap();
            matches!(
                queue.claim(TimeoutWait::new().deadline()),
                Err(Refusal::ConnectionClosed)
            )
        })
    };
    waiting.recv().unwrap();
    queue.close();
    assert!(contender.join().unwrap());
    drop(owner);
}

#[test]
fn subscription_racing_disconnect_always_receives_the_terminal_event() {
    for _ in 0..100 {
        let shared = Arc::new(Shared {
            connection_id: Mutex::new(None),
            subscribers: Mutex::new(Vec::new()),
            scoped: Mutex::new(Vec::new()),
            closed: AtomicBool::new(false),
            timeout: AtomicBool::new(false),
        });
        let barrier = Arc::new(std::sync::Barrier::new(2));
        let subscriber = {
            let shared = shared.clone();
            let barrier = barrier.clone();
            thread::spawn(move || {
                barrier.wait();
                (shared.subscribe(), shared.subscribe_scoped())
            })
        };
        barrier.wait();
        shared.closed.store(true, Ordering::Release);
        shared.dispatch(&Pushed {
            event: Event::Disconnected,
            profile_id: None,
            session_id: None,
        });
        let (plain, scoped) = subscriber.join().unwrap();
        assert_eq!(
            plain.recv_timeout(Duration::from_secs(1)).unwrap(),
            Event::Disconnected
        );
        assert_eq!(
            scoped.recv_timeout(Duration::from_secs(1)).unwrap().event,
            Event::Disconnected
        );
        assert!(plain.try_recv().is_err());
        assert!(scoped.try_recv().is_err());
    }
}

#[test]
fn an_expired_claimant_passes_on_a_release_wake() {
    let (_sender, receiver) = mpsc::channel();
    let queue = Arc::new(ExchangeQueue {
        replies: Mutex::new(None),
        available: Condvar::new(),
        closed: AtomicBool::new(false),
    });
    let (waiting, started) = mpsc::channel();
    let (done, finished) = mpsc::channel();
    let waiter = {
        let queue = queue.clone();
        thread::spawn(move || {
            let held = queue.replies.lock().unwrap();
            waiting.send(()).unwrap();
            let (held, timeout) = queue
                .available
                .wait_timeout(held, Duration::from_secs(3))
                .unwrap();
            done.send(!timeout.timed_out() && held.is_some()).unwrap();
        })
    };
    started.recv_timeout(Duration::from_secs(1)).unwrap();
    // The receiver became available, but the release wake went to an
    // expired claimant rather than the waiter above.
    *queue.replies.lock().unwrap() = Some(receiver);
    assert!(matches!(
        queue.claim(Instant::now() - Duration::from_secs(1)),
        Err(Refusal::Timeout)
    ));
    let woke = finished.recv_timeout(Duration::from_secs(1));
    waiter.join().unwrap();
    assert!(woke.unwrap());
}

#[test]
fn a_streamed_payload_follows_only_readiness_for_the_declared_upload() {
    let descriptor = json!({"kind": "financial_operand_input", "byte_count": 70_000});
    let request = json!({"action": "operation_submit_payload", "descriptor": descriptor});
    let ready = |kind: &str, descriptor: Value| {
        json!({"kind": kind, "descriptor": descriptor})
            .as_object()
            .unwrap()
            .clone()
    };
    assert!(ready_for(
        &request,
        &ready("operation_payload_ready", descriptor.clone())
    ));
    assert!(!ready_for(
        &request,
        &ready(
            "operation_payload_ready",
            json!({"kind": "financial_operand_input", "byte_count": 69_999})
        )
    ));
    assert!(!ready_for(
        &request,
        &ready("operation_submitted", descriptor.clone())
    ));
    assert!(!ready_for(
        &json!({"action": "operation_submit_payload"}),
        &ready("operation_payload_ready", Value::Null)
    ));
    // Every chunk but the last fills one secret frame within its bound.
    assert!(frame(SECRET_FRAME, &[0; SUBMISSION_PAYLOAD_CHUNK_BYTES]).is_ok());
}

#[test]
fn events_are_read_by_kind_and_an_unknown_kind_ends_the_connection() {
    let read = |value: Value| event(value.as_object().unwrap());
    assert_eq!(
        read(json!({"kind": "sign_in_changed"})),
        Event::SignInChanged
    );
    assert_eq!(
        read(
            json!({"kind": "session_event", "event": "signed_out", "reason": "authentication_required"})
        ),
        Event::SessionRetired {
            kind: "signed_out".into(),
            reason: "authentication_required".into()
        }
    );
    assert_eq!(read(json!({"kind": "profile_status"})), Event::Disconnected);
}
