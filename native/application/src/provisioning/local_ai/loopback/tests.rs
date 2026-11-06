use super::*;
use std::net::TcpListener;

#[test]
fn a_connect_that_fails_names_the_connect_bound() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let address = listener.local_addr().unwrap();
    drop(listener);
    let loopback = Loopback::new(address).unwrap();

    let error = loopback.get("/api/version").expect_err("nothing listens");
    let failure = loopback.failure(&error);

    assert_eq!(failure.phase, ExchangePhase::Connect, "{error}");
    assert_eq!(failure.bound, loopback.connect_timeout);
    assert_eq!(failure.kind, error.kind());
}

#[test]
fn an_answer_that_never_comes_runs_out_of_the_read_bound_on_every_platform() {
    // The listener's backlog completes the connection and takes the request; nothing
    // ever answers it.
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let bound = Duration::from_millis(200);
    let loopback = Loopback::new(listener.local_addr().unwrap())
        .unwrap()
        .with_io_timeout(bound);

    let error = loopback.get("/api/tags").expect_err("no answer comes");

    assert_eq!(
        loopback.failure(&error),
        ExchangeFailure {
            phase: ExchangePhase::Exchange,
            kind: io::ErrorKind::TimedOut,
            bound,
        },
        "{error:?}"
    );
    drop(listener);
}

#[test]
fn a_read_timeout_reported_as_would_block_is_the_bound_running_out() {
    let loopback = Loopback::new("127.0.0.1:9".parse().unwrap()).unwrap();
    let failure = loopback.failure(&io::Error::from(io::ErrorKind::WouldBlock));
    assert_eq!(failure.kind, io::ErrorKind::TimedOut);
    assert_eq!(failure.phase, ExchangePhase::Exchange);
    assert_eq!(failure.bound, loopback.io_timeout);
}
