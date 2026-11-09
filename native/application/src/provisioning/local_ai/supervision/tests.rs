use super::*;
use crate::provisioning::{
    items::Locations,
    local_ai::{
        fake_llamacpp, fake_ollama,
        huggingface::MODEL_MEDIA_TYPE,
        lease::PROGRAM_CHANGE_BUDGET,
        llama_server::tests as llama_tests,
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
    path::{Path, PathBuf},
    process::Child,
    sync::{
        Arc,
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

/// Reads the owner's environment with `CADRUMO_PROXY_URL` set to `url`, as a login
/// start would have given it.
fn with_proxy(url: &'static str) -> impl Fn(&str) -> Option<OsString> + Send {
    move |name: &str| {
        if name == PROXY_URL {
            return Some(OsString::from(url));
        }
        ambient(name)
    }
}

fn version_at(address: SocketAddr) -> Option<String> {
    let (status, body) = Loopback::new(address).ok()?.get("/api/version").ok()?;
    let value: serde_json::Value = serde_json::from_slice(&body).ok()?;
    (status == 200).then(|| value["version"].as_str().map(str::to_owned))?
}

/// Polls once and expects the server to run, naming the start's cause when it does not.
fn assert_running(supervisor: &mut ServerSupervisor, now: Instant) {
    let state = supervisor.poll(now);
    assert_eq!(
        state,
        ServerState::Running,
        "the start failed with: {:?}",
        supervisor.last_start_failure().map(ToString::to_string)
    );
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
fn a_set_up_program_runs_contained_on_its_address_and_restarts_after_a_crash() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let (program, _) = installed(&locations, "9.8.7");
    let address = free_address();
    let contained = Counting::default();
    let mut supervisor = supervisor(program, address, contained.clone());
    let start = Instant::now();

    assert_running(&mut supervisor, start);
    assert_eq!(version_at(address).as_deref(), Some("9.8.7"));
    assert_eq!(contained.0.load(Ordering::SeqCst), 1);
    let record = ServerRecord::read(&locations.programs).unwrap();
    assert_eq!(record.address, address.to_string());
    assert_running(&mut supervisor, start);
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
    assert_running(&mut supervisor, due);
    assert_eq!(version_at(address).as_deref(), Some("9.8.7"));
    assert_eq!(contained.0.load(Ordering::SeqCst), 2);

    // The second crash in the window waits twice as long; the third fails supervision.
    crash(&mut supervisor);
    let later = due + Duration::from_secs(2);
    assert_eq!(supervisor.poll(due), ServerState::Restarting { at: later });
    assert_running(&mut supervisor, later);
    crash(&mut supervisor);
    assert_eq!(supervisor.poll(later), ServerState::Failed);
    assert_eq!(
        supervisor.poll(later + Duration::from_secs(60)),
        ServerState::Failed
    );
    assert!(!answers(address));

    // A retry forgets the crashes and starts again.
    supervisor.retry();
    assert_running(&mut supervisor, later);
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
    assert_running(&mut supervisor, now);

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
    assert_running(&mut supervisor, now);
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
    assert_running(&mut supervisor, now);

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
    assert_running(&mut supervisor, now);
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
fn the_setting_the_owner_started_with_runs_the_server_and_one_it_cannot_use_runs_none() {
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let address = free_address();
    let contained = Counting::default();
    let now = Instant::now();

    // A setting the engine cannot use runs no server: one started without it would
    // fetch the models directly, which is the opposite of what the setting asks for.
    let (program, _) = installed(&locations, "9.8.7");
    let mut refused = ServerSupervisor::new(
        program,
        address,
        Box::new(contained.clone()),
        Box::new(with_proxy("ftp://proxy.example:3128")),
    )
    .unwrap();
    assert_eq!(refused.poll(now), ServerState::ProxyRefused);
    assert!(!answers(address));
    assert_eq!(contained.0.load(Ordering::SeqCst), 0);
    assert!(ServerRecord::read(&locations.programs).is_none());

    // The owner's environment is its own and cannot change while it runs, so nothing it
    // looks at again can make that setting usable.
    assert_eq!(
        refused.poll(now + Duration::from_secs(600)),
        ServerState::ProxyRefused
    );
    assert!(!answers(address));
    drop(refused);

    // A correction reaches the server at the next start of the owner: this supervisor
    // reads it once, and its server runs under it.
    let address = free_address();
    let (program, _) = installed(&locations, "9.8.7");
    let mut supervisor = ServerSupervisor::new(
        program,
        address,
        Box::new(contained.clone()),
        Box::new(with_proxy("http://user:secret@proxy.example:3128")),
    )
    .unwrap();
    assert_running(&mut supervisor, now);
    let record = ServerRecord::read(&locations.programs).unwrap();
    let corrected = ProxySettings::from_settings(|name| {
        (name == PROXY_URL).then(|| String::from("http://user:secret@proxy.example:3128"))
    })
    .unwrap()
    .unwrap();
    assert_eq!(record.proxy_fingerprint(), Some(corrected.fingerprint()));
    let written = fs::read_to_string(locations.programs.join(SERVER_RECORD)).unwrap();
    assert!(
        !written.contains("proxy.example") && !written.contains("secret"),
        "the address is a credential; only its digest is recorded: {written}"
    );
}

/// Both engines' programs set up under one storage, each standing in with its fake and
/// appending to one launch file whenever a server of its kind starts.
struct BothEngines {
    _root: tempfile::TempDir,
    locations: Locations,
    launches: PathBuf,
    ollama: Program,
    llama: LlamaServer,
}

fn both_engines() -> BothEngines {
    let root = tempfile::tempdir().unwrap();
    let (mut llama, locations) = llama_tests::packaged(root.path());
    let launches = root.path().join("launches");
    llama_tests::stand_in(
        &mut llama,
        "b12184-c0ab6e5c0",
        &[(fake_llamacpp::HELPER_LAUNCHES, launches.as_os_str())],
    );
    let (mut ollama, _) = installed(&locations, "9.8.7");
    if let Some(stand_in) = ollama.serve_override.as_mut() {
        stand_in.environment.push((
            OsString::from(fake_ollama::HELPER_LAUNCHES),
            launches.clone().into_os_string(),
        ));
    }
    BothEngines {
        _root: root,
        locations,
        launches,
        ollama,
        llama,
    }
}

/// The servers ever started, by kind, in order.
fn launched(launches: &Path) -> Vec<String> {
    fs::read_to_string(launches)
        .unwrap_or_default()
        .lines()
        .map(str::to_owned)
        .collect()
}

/// What a selection supervises and what it left: the storage, the launch file and
/// which engines' programs were built.
struct Selected {
    supervisor: ServerSupervisor<EngineProgram>,
    root: tempfile::TempDir,
    launches: PathBuf,
    locations: Locations,
    built: (bool, bool),
}

/// Supervises the program of `engine` as the manager does, noting which programs were
/// built.
fn selected(engine: LocalEngine, both: BothEngines) -> Selected {
    let BothEngines {
        _root: root,
        locations,
        launches,
        ollama,
        llama,
    } = both;
    let (mut ollama_built, mut llama_built) = (false, false);
    let program = EngineProgram::select(
        engine,
        || {
            ollama_built = true;
            Ok::<_, ()>(ollama)
        },
        || {
            llama_built = true;
            Ok(llama)
        },
    )
    .unwrap();
    assert_eq!(program.engine(), engine);
    let supervisor = ServerSupervisor::new(
        program,
        free_address(),
        Box::new(Counting::default()),
        Box::new(ambient),
    )
    .unwrap()
    .with_policy(RestartPolicy {
        initial_backoff: Duration::from_secs(1),
        maximum_backoff: Duration::from_secs(4),
        crash_loop_limit: 3,
        crash_loop_window: Duration::from_secs(60),
    });
    Selected {
        supervisor,
        root,
        launches,
        locations,
        built: (ollama_built, llama_built),
    }
}

fn assert_engine_running(supervisor: &mut ServerSupervisor<EngineProgram>, now: Instant) {
    let state = supervisor.poll(now);
    assert_eq!(
        state,
        ServerState::Running,
        "the start failed with: {:?}",
        supervisor.last_start_failure().map(ToString::to_string)
    );
}

/// Ends the running server as a crash would, and starts it again after its backoff.
fn crash_and_restart(supervisor: &mut ServerSupervisor<EngineProgram>, now: Instant) {
    let _ = Loopback::new(supervisor.address())
        .unwrap()
        .post("/fake/exit", b"{}");
    supervisor
        .program_mut()
        .running_mut()
        .expect("a running server")
        .wait_exit();
    let due = now + Duration::from_secs(1);
    assert_eq!(supervisor.poll(now), ServerState::Restarting { at: due });
    assert_engine_running(supervisor, due);
}

/// A model new in the store, as a pull that states its llama.cpp context leaves it.
fn model_arrives(locations: &Locations) {
    let path = ["registry.ollama.ai", "library", "text-reader", "small"];
    llama_tests::manifest(
        &locations.models,
        path,
        &[llama_tests::blob(
            &locations.models,
            MODEL_MEDIA_TYPE,
            b"text weights",
        )],
    );
    llama_tests::record(&locations.models, path, 4096);
}

#[test]
fn with_ollama_selected_no_llama_server_is_ever_started_through_the_whole_supervision() {
    let Selected {
        mut supervisor,
        root,
        launches,
        locations,
        built,
    } = selected(LocalEngine::Ollama, both_engines());
    assert_eq!(built, (true, false), "llama-server is never built");
    let now = Instant::now();

    assert_engine_running(&mut supervisor, now);
    crash_and_restart(&mut supervisor, now);
    // Ollama reads the store as it is: a new model restarts nothing.
    model_arrives(&locations);
    let later = now + Duration::from_secs(1);
    assert_engine_running(&mut supervisor, later);
    supervisor.stop();
    assert_eq!(supervisor.state(), ServerState::Stopped);
    drop(supervisor);

    // Every server ever started was Ollama: started once and once again after the crash.
    assert_eq!(launched(&launches), [fake_ollama::LAUNCHED; 2]);
    drop(root);
}

#[test]
fn with_llama_server_selected_no_ollama_is_ever_started_through_the_whole_supervision() {
    let Selected {
        mut supervisor,
        root,
        launches,
        locations,
        built,
    } = selected(LocalEngine::LlamaCpp, both_engines());
    assert_eq!(built, (false, true), "Ollama is never built");
    let now = Instant::now();

    assert_engine_running(&mut supervisor, now);
    crash_and_restart(&mut supervisor, now);
    // A new model in the store starts the idle router again with it.
    model_arrives(&locations);
    let later = now + Duration::from_secs(1);
    assert_engine_running(&mut supervisor, later);
    supervisor.stop();
    assert_eq!(supervisor.state(), ServerState::Stopped);
    drop(supervisor);

    // Every server ever started was llama-server: started, restarted after the crash and
    // started again for the new model.
    assert_eq!(launched(&launches), [fake_llamacpp::LAUNCHED; 3]);
    drop(root);
}
