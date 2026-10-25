use super::*;
use crate::provisioning::{
    items::Locations,
    local_ai::{
        lease::PROGRAM_CHANGE_BUDGET,
        loopback::Loopback,
        program::{
            SERVER_RECORD, ServerRecord,
            tests::{ambient, answers, free_address, installed, stand_in},
        },
    },
    pins::Platform,
    proxy::{PROXY_URL, ProxySettings},
};
use std::{
    ffi::OsString,
    fs,
    process::Child,
    sync::{
        Arc, Mutex,
        atomic::{AtomicUsize, Ordering},
        mpsc,
    },
};

/// Counts the servers it is asked to contain; the job itself is the owner's.
#[derive(Clone, Default)]
struct Counting(Arc<AtomicUsize>);

impl Containment for Counting {
    fn contain(&self, _: &Child) -> std::io::Result<Box<dyn Send>> {
        self.0.fetch_add(1, Ordering::SeqCst);
        Ok(Box::new(()))
    }
}

fn supervisor(program: Program, address: SocketAddr, containment: Counting) -> ServerSupervisor {
    ServerSupervisor::new(program, address, Box::new(containment), Box::new(ambient))
        .unwrap()
        .with_policy(RestartPolicy {
            initial_backoff: Duration::from_secs(1),
            maximum_backoff: Duration::from_secs(4),
            crash_loop_limit: 2,
            crash_loop_window: Duration::from_secs(60),
        })
}

fn version_at(address: SocketAddr) -> Option<String> {
    let (status, body) = Loopback::new(address).ok()?.get("/api/version").ok()?;
    let value: serde_json::Value = serde_json::from_slice(&body).ok()?;
    (status == 200).then(|| value["version"].as_str().map(str::to_owned))?
}

/// Ends the running server as a crash would, and waits until its process has ended.
fn crash(supervisor: &mut ServerSupervisor) {
    let address = supervisor.address();
    let _ = Loopback::new(address).unwrap().post("/fake/exit", b"{}");
    supervisor
        .program_mut()
        .server_mut()
        .expect("a running server")
        .wait_exit();
}

#[test]
fn a_program_that_is_not_set_up_runs_no_server() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let pins = crate::provisioning::pins::ProgramPins::parse(
        "program = \"ollama\"\nversion = \"9.8.7\"\nhosts = [\"github.com\"]\n\n\
         [[archives]]\nplatform = \"win-x64\"\n\
         url = \"https://github.com/ollama/ollama/releases/download/v9.8.7/ollama.zip\"\n\
         format = \"zip\"\nexecutable = \"ollama.exe\"\ndownload_bytes = 10\n\
         sha256 = \"0000000000000000000000000000000000000000000000000000000000000000\"\n",
    )
    .unwrap();
    let program = Program::new(&pins, Platform::WinX64, locations.clone())
        .unwrap()
        .unwrap();
    let address = free_address();
    let contained = Counting::default();
    let mut supervisor = supervisor(program, address, contained.clone());
    let now = Instant::now();
    assert_eq!(supervisor.poll(now), ServerState::NotSetUp);
    assert_eq!(supervisor.poll(now), ServerState::NotSetUp);
    assert_eq!(supervisor.next_due(), None);
    assert!(!answers(address));
    assert_eq!(contained.0.load(Ordering::SeqCst), 0);
    assert!(
        ServerSupervisor::new(
            Program::new(&pins, Platform::WinX64, locations)
                .unwrap()
                .unwrap(),
            "192.0.2.1:23743".parse().unwrap(),
            Box::new(Counting::default()),
            Box::new(ambient),
        )
        .is_err(),
        "only a loopback address is served"
    );
}

#[test]
fn a_set_up_program_runs_contained_on_the_fixed_address_and_restarts_after_a_crash() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let (program, _) = installed(&locations, "9.8.7");
    let address = free_address();
    let contained = Counting::default();
    let mut supervisor = supervisor(program, address, contained.clone());
    let start = Instant::now();

    assert_eq!(supervisor.poll(start), ServerState::Running);
    assert_eq!(version_at(address).as_deref(), Some("9.8.7"));
    assert_eq!(contained.0.load(Ordering::SeqCst), 1);
    let record = ServerRecord::read(&locations.programs).unwrap();
    assert_eq!(record.address, address.to_string());
    assert_eq!(supervisor.poll(start), ServerState::Running);
    assert_eq!(contained.0.load(Ordering::SeqCst), 1, "one server, kept");

    // A crash is restarted after the first backoff, on the same address.
    crash(&mut supervisor);
    let due = start + Duration::from_secs(1);
    assert_eq!(supervisor.poll(start), ServerState::Restarting { at: due });
    assert!(ServerRecord::read(&locations.programs).is_none());
    assert_eq!(supervisor.next_due(), Some(due));
    assert_eq!(
        supervisor.poll(due - Duration::from_millis(1)),
        ServerState::Restarting { at: due }
    );
    assert!(!answers(address), "nothing restarts before its backoff");
    assert_eq!(supervisor.poll(due), ServerState::Running);
    assert_eq!(version_at(address).as_deref(), Some("9.8.7"));
    assert_eq!(contained.0.load(Ordering::SeqCst), 2);

    // The second crash in the window waits twice as long; the third fails supervision.
    crash(&mut supervisor);
    let later = due + Duration::from_secs(2);
    assert_eq!(supervisor.poll(due), ServerState::Restarting { at: later });
    assert_eq!(supervisor.poll(later), ServerState::Running);
    crash(&mut supervisor);
    assert_eq!(supervisor.poll(later), ServerState::Failed);
    assert_eq!(
        supervisor.poll(later + Duration::from_secs(60)),
        ServerState::Failed
    );
    assert!(!answers(address));

    // A retry forgets the crashes and starts again.
    supervisor.retry();
    assert_eq!(supervisor.poll(later), ServerState::Running);
    assert_eq!(version_at(address).as_deref(), Some("9.8.7"));
}

#[test]
fn a_program_change_stops_the_server_and_holds_every_start_until_it_is_over() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let (program, pins) = installed(&locations, "9.8.7");
    let address = free_address();
    let mut supervisor = supervisor(program, address, Counting::default());
    let now = Instant::now();
    assert_eq!(supervisor.poll(now), ServerState::Running);

    // An engine asks to remove the program while the server runs. It waits until the
    // supervisor, at its next look, has stopped the server.
    let mut engine = Program::new(&pins, Platform::current().unwrap(), locations.clone())
        .unwrap()
        .unwrap();
    let (asked, request) = mpsc::channel();
    engine.on_change_requested(Box::new(move || asked.send(()).unwrap()));
    let removing = std::thread::spawn(move || engine.remove());
    request.recv().unwrap();
    assert!(
        answers(address),
        "the server runs until the supervisor looks"
    );
    assert_eq!(supervisor.poll(now), ServerState::Held);
    assert!(!answers(address));
    removing.join().unwrap().unwrap();
    assert_eq!(supervisor.poll(now), ServerState::NotSetUp);
    assert!(!answers(address));

    // Put back, the program is served again; a change held by an engine holds the start.
    let (_, _) = installed(&locations, "9.8.7");
    let change = supervisor
        .program()
        .leases()
        .change_program(PROGRAM_CHANGE_BUDGET, &mut || {
            panic!("no server runs, so nothing is waited for")
        })
        .unwrap();
    assert_eq!(supervisor.poll(now), ServerState::Held);
    assert!(!answers(address));
    drop(change);
    assert_eq!(supervisor.poll(now), ServerState::Running);
    assert_eq!(version_at(address).as_deref(), Some("9.8.7"));
}

#[test]
fn the_owner_stops_the_server_at_exit_and_session_end_and_nothing_restarts_it() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let (program, _) = installed(&locations, "9.8.7");
    let address = free_address();
    let mut supervisor = supervisor(program, address, Counting::default());
    let now = Instant::now();
    assert_eq!(supervisor.poll(now), ServerState::Running);

    supervisor.stop();
    assert_eq!(supervisor.state(), ServerState::Stopped);
    assert!(!answers(address));
    assert!(ServerRecord::read(&locations.programs).is_none());
    assert_eq!(
        supervisor.poll(now + Duration::from_secs(600)),
        ServerState::Stopped
    );
    assert!(!answers(address));

    // A cancelled session end resumes supervision.
    supervisor.resume();
    assert_eq!(supervisor.poll(now), ServerState::Running);
    assert!(answers(address));

    // However the owner ends, the server it runs ends with it.
    drop(supervisor);
    assert!(!answers(address));
    let mut observer = Program::new(
        &installed(&locations, "9.8.7").1,
        Platform::current().unwrap(),
        locations.clone(),
    )
    .unwrap()
    .unwrap();
    stand_in(&mut observer, "9.8.7");
    assert!(observer.running_server().is_none());
}

#[test]
fn the_proxy_setting_is_read_at_every_start_and_one_the_engine_cannot_use_runs_no_server() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let (program, _) = installed(&locations, "9.8.7");
    let address = free_address();
    let contained = Counting::default();
    let setting = Arc::new(Mutex::new(String::from("ftp://proxy.example:3128")));
    let read = Arc::clone(&setting);
    let mut supervisor = ServerSupervisor::new(
        program,
        address,
        Box::new(contained.clone()),
        Box::new(move |name: &str| {
            if name == PROXY_URL {
                return Some(OsString::from(read.lock().unwrap().clone()));
            }
            ambient(name)
        }),
    )
    .unwrap();
    let now = Instant::now();

    // A setting the engine cannot use runs no server: one started without it would
    // fetch the models directly, which is the opposite of what the setting asks for.
    assert_eq!(supervisor.poll(now), ServerState::ProxyRefused);
    assert!(!answers(address));
    assert_eq!(contained.0.load(Ordering::SeqCst), 0);
    assert!(ServerRecord::read(&locations.programs).is_none());

    // The operator corrects the setting after this supervisor started: the next look
    // reads it, so it is the setting the server runs under.
    *setting.lock().unwrap() = String::from("http://user:secret@proxy.example:3128");
    assert_eq!(supervisor.poll(now), ServerState::Running);
    let record = ServerRecord::read(&locations.programs).unwrap();
    let corrected = ProxySettings::from_settings(|name| {
        (name == PROXY_URL).then(|| setting.lock().unwrap().clone())
    })
    .unwrap()
    .unwrap();
    assert_eq!(record.proxy_fingerprint(), Some(corrected.fingerprint()));
    let written = fs::read_to_string(locations.programs.join(SERVER_RECORD)).unwrap();
    assert!(
        !written.contains("proxy.example") && !written.contains("secret"),
        "the address is a credential; only its digest is recorded: {written}"
    );

    // A setting that becomes unusable stops the server already running under the old one.
    *setting.lock().unwrap() = String::from("http://proxy.example:0");
    assert_eq!(supervisor.poll(now), ServerState::ProxyRefused);
    assert!(!answers(address));
}
