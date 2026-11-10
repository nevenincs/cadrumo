use super::*;
use crate::{
    component::Cancellation,
    provisioning::{
        items::ItemId,
        local_ai::fake_ollama::{
            HELPER_ARGUMENTS, HELPER_GATE, HELPER_MODE, HELPER_SILENCE, HELPER_VERSION,
        },
        pins::{ComponentPins, ProgramIdentity},
        plan::PlanEntry,
        receipts::ReceiptReading,
        test_servers::{Reply, Request, TestCertificate, TlsServer, network_to, response},
        transfer::{RetryPolicy, SystemPacing},
    },
    value::Sha256Digest,
};
use std::{
    collections::BTreeSet,
    io::{Cursor, Write},
    net::TcpStream,
    sync::{Arc, Mutex},
    time::UNIX_EPOCH,
};

fn committed_pins() -> ProgramPins {
    let pins = ComponentPins::load(&crate::provisioning::pins::committed_tables()).unwrap();
    pins.program(ProgramIdentity::Ollama).unwrap().clone()
}

#[test]
fn the_archive_bounds_hold_every_measured_archive_with_headroom() {
    let pins = committed_pins();
    assert_eq!(
        pins.version, "0.40.10",
        "the measured sizes below are this version's; measure the new archives and update them"
    );
    for (platform, unpacked, members) in [
        (Platform::WinX64, 2_230_768_655u64, 80usize),
        (Platform::LinuxX64, 5_001_030_082, 80),
        (Platform::LinuxArm64, 3_819_535_364, 51),
        (Platform::MacX64, 610_445_869, 59),
        (Platform::MacArm64, 610_445_869, 59),
    ] {
        let pin = pins.for_platform(platform).unwrap();
        let (max_unpacked, max_entries) = archive_limits(pin.download_bytes);
        assert!(max_unpacked >= unpacked + unpacked / 2, "{platform:?}");
        assert!(max_entries >= members * 12, "{platform:?}");
    }
    assert_eq!(archive_limits(u64::MAX).0, STORE_UNPACKED_LIMIT);
}

#[test]
fn the_program_part_plans_its_own_folder_and_nothing_outside_cadrumo() {
    let directory = tempfile::tempdir().unwrap();
    let pins = committed_pins();
    let program = Program::new(&pins, Platform::WinX64, Locations::under(directory.path()))
        .unwrap()
        .unwrap();
    let part = program.plan_part();
    assert_eq!(part.part_id, PROGRAM_PART);
    assert_eq!(part.destination, Some(Destination::LocalAiProgram));
    assert!(!part.installs_outside_program);
    assert_eq!(part.download_bytes, Some(1_586_229_413));
    assert_eq!(part.target_version.as_deref(), Some("0.40.10"));
    assert_eq!(
        part.source_hosts
            .iter()
            .map(HostName::as_str)
            .collect::<Vec<_>>(),
        ["github.com", "release-assets.githubusercontent.com"]
    );
    let entry = PlanEntry::of_parts(ItemId::LocalAi, vec![part]).unwrap();
    assert!(!entry.installs_outside_program);
    assert_eq!(entry.destinations(), [Destination::LocalAiProgram]);
    let artifact = program.artifact();
    assert_eq!(artifact.id, "ollama");
    assert_eq!(artifact.executable.as_str(), "ollama.exe");
    assert_eq!(
        artifact.max_unpacked_bytes,
        1_586_229_413 * UNPACKED_PER_DOWNLOADED_BYTE
    );
}

/// A pin table naming one archive for this platform at `url`'s path on github.com.
fn pins_for(bytes: &[u8], version: &str, executable: &str) -> ProgramPins {
    pins_for_platform(bytes, version, Platform::current().unwrap(), executable)
}

/// A pin table naming one archive for `platform`.
fn pins_for_platform(
    bytes: &[u8],
    version: &str,
    platform: Platform,
    executable: &str,
) -> ProgramPins {
    ProgramPins::parse(&format!(
        "program = \"ollama\"\nversion = \"{version}\"\nhosts = [\"github.com\"]\n\n\
         [[archives]]\nplatform = \"{}\"\n\
         url = \"https://github.com/ollama/ollama/releases/download/v{version}/ollama.zip\"\n\
         format = \"zip\"\nexecutable = \"{executable}\"\ndownload_bytes = {}\nsha256 = \"{}\"\n",
        platform.as_str(),
        bytes.len(),
        Sha256Digest::of(bytes),
    ))
    .unwrap()
}

#[test]
fn a_build_whose_pins_skip_this_platform_has_no_program() {
    let directory = tempfile::tempdir().unwrap();
    let pins = pins_for(b"archive", "1.2.3", "bin/ollama");
    let other = if Platform::current() == Some(Platform::WinX64) {
        Platform::LinuxX64
    } else {
        Platform::WinX64
    };
    assert!(
        Program::new(&pins, other, Locations::under(directory.path()))
            .unwrap()
            .is_none()
    );
}

const EXECUTABLE: &str = if cfg!(windows) {
    "ollama.exe"
} else {
    "bin/ollama"
};

/// The publisher's layout in miniature, with the test binary itself as the program.
fn archive(marker: &[u8]) -> Vec<u8> {
    archive_of(
        EXECUTABLE,
        &fs::read(std::env::current_exe().unwrap()).unwrap(),
        marker,
    )
}

/// The publisher's layout in miniature, with `program` as the program at `executable`.
/// Its entries name a Unix origin, as the publisher's do, so the archive has the same
/// bytes on every host rather than the writer's host default.
fn archive_of(executable: &str, program: &[u8], marker: &[u8]) -> Vec<u8> {
    let mut zip = zip::ZipWriter::new(Cursor::new(Vec::new()));
    let stored = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Stored)
        .system(zip::System::Unix)
        .unix_permissions(0o755);
    zip.start_file(executable, stored).unwrap();
    zip.write_all(program).unwrap();
    zip.start_file("lib/ollama/marker", stored.unix_permissions(0o644))
        .unwrap();
    zip.write_all(marker).unwrap();
    zip.finish().unwrap().into_inner()
}

/// One TLS server for github.com serving each archive at its version's path.
fn publisher(archives: Vec<(String, Vec<u8>)>) -> (TestCertificate, TlsServer) {
    let certificate = TestCertificate::new(&["github.com"]);
    let served = Arc::new(archives);
    let server = TlsServer::start(&certificate, move |request: &Request| {
        match served
            .iter()
            .find(|(version, _)| request.target().contains(&format!("/v{version}/")))
        {
            Some((_, bytes)) => Reply::Bytes(response(
                "200 OK",
                &[("Content-Length", bytes.len().to_string())],
                bytes,
            )),
            None => Reply::Bytes(response(
                "404 Not Found",
                &[("Content-Length", "0".into())],
                b"",
            )),
        }
    });
    (certificate, server)
}

pub(crate) fn ambient(name: &str) -> Option<OsString> {
    std::env::var_os(name)
}

pub(crate) fn stand_in(program: &mut Program, version: &str) {
    program.serve_override = Some(ServeOverride {
        arguments: HELPER_ARGUMENTS.map(OsString::from).to_vec(),
        environment: vec![
            (OsString::from(HELPER_MODE), OsString::from("serve")),
            (OsString::from(HELPER_VERSION), OsString::from(version)),
        ],
    });
}

/// Writes a start-failure record as an earlier start, in any process, left it.
fn earlier_failure(programs: &Path) {
    fs::create_dir_all(programs).unwrap();
    fs::write(
        programs.join(START_FAILURE_RECORD),
        br#"{"schema":1,"reason":"server_launch_failed"}"#,
    )
    .unwrap();
}

#[test]
fn an_earlier_failed_start_is_not_read_as_the_cause_of_a_later_one() {
    let bytes = archive(b"only");
    let (certificate, publisher) = publisher(vec![("9.8.7".into(), bytes.clone())]);
    let network = network_to(certificate.roots(), publisher.address(), None);
    let hosts: BTreeSet<HostName> = [HostName::new("github.com").unwrap()].into();
    let mut pacing = SystemPacing::default();
    let cancellation = Cancellation::default();
    let mut events = |_| {};
    let mut transfer = Transfer {
        network: &network,
        hosts: &hosts,
        policy: RetryPolicy::default(),
        pacing: &mut pacing,
        events: &mut events,
        cancellation: &cancellation,
    };
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let pins = pins_for(&bytes, "9.8.7", EXECUTABLE);
    let new_program = || {
        Program::new(&pins, Platform::current().unwrap(), locations.clone())
            .unwrap()
            .unwrap()
    };
    let mut program = new_program();
    let observer = new_program();

    // Installing changes the program: a failure under the earlier one is forgotten.
    earlier_failure(&locations.programs);
    program.install(&mut transfer).unwrap();
    assert_eq!(observer.latest_start_failure(), None);

    // A new attempt that has begun and not finished has not failed.
    earlier_failure(&locations.programs);
    let gate = root.path().join("announce");
    stand_in(&mut program, "9.8.7");
    if let Some(stand_in) = program.serve_override.as_mut() {
        stand_in
            .environment
            .push((OsString::from(HELPER_GATE), gate.clone().into_os_string()));
    }
    std::thread::scope(|scope| {
        let starting = scope.spawn(|| {
            program
                .start(free_address(), &Uncontained, &ambient, None)
                .map(|server| server.address())
        });
        let deadline = std::time::Instant::now() + Duration::from_secs(20);
        while observer.latest_start_failure().is_some() && std::time::Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(20));
        }
        assert_eq!(
            observer.latest_start_failure(),
            None,
            "the earlier failure is not this attempt's"
        );
        assert!(
            observer.running_server().is_none(),
            "the attempt has not finished"
        );
        fs::write(&gate, b"").unwrap();
        starting.join().unwrap().expect("the gated start finishes");
    });
    assert_eq!(observer.latest_start_failure(), None);

    // Removing the program forgets a failure under it too.
    program.stop();
    earlier_failure(&locations.programs);
    program.remove().unwrap();
    assert_eq!(observer.latest_start_failure(), None);
}

pub(crate) fn answers(address: SocketAddr) -> bool {
    TcpStream::connect_timeout(&address, Duration::from_secs(2)).is_ok()
}

/// A loopback address free now, for one server a test starts.
pub(crate) fn free_address() -> SocketAddr {
    std::net::TcpListener::bind("127.0.0.1:0")
        .unwrap()
        .local_addr()
        .unwrap()
}

/// The program of `version` for `platform`, installed under `locations` from a local
/// publisher of an archive holding `program` at `executable`, with the test binary
/// standing in for its server, and the pins that name it.
pub(crate) fn installed_with(
    locations: &Locations,
    version: &str,
    platform: Platform,
    executable: &str,
    program: &[u8],
) -> (Program, ProgramPins) {
    let bytes = archive_of(executable, program, b"marker");
    let (certificate, publisher) = publisher(vec![(version.into(), bytes.clone())]);
    let network = network_to(certificate.roots(), publisher.address(), None);
    let hosts: BTreeSet<HostName> = [HostName::new("github.com").unwrap()].into();
    let mut pacing = SystemPacing::default();
    let cancellation = Cancellation::default();
    let mut events = |_| {};
    let mut transfer = Transfer {
        network: &network,
        hosts: &hosts,
        policy: RetryPolicy::default(),
        pacing: &mut pacing,
        events: &mut events,
        cancellation: &cancellation,
    };
    let pins = pins_for_platform(&bytes, version, platform, executable);
    let mut program = Program::new(&pins, platform, locations.clone())
        .unwrap()
        .unwrap();
    program.install(&mut transfer).unwrap();
    stand_in(&mut program, version);
    (program, pins)
}

/// [`installed_with`] the test binary as the program.
pub(crate) fn installed(locations: &Locations, version: &str) -> (Program, ProgramPins) {
    installed_with(
        locations,
        version,
        Platform::current().unwrap(),
        EXECUTABLE,
        &fs::read(std::env::current_exe().unwrap()).unwrap(),
    )
}

#[test]
fn a_pinned_archive_installs_runs_as_the_engines_child_and_is_stopped_before_it_changes() {
    let first = archive(b"first");
    let second = archive(b"second");
    let (certificate, publisher) = publisher(vec![
        ("9.8.7".into(), first.clone()),
        ("9.8.8".into(), second.clone()),
    ]);
    let network = network_to(certificate.roots(), publisher.address(), None);
    let hosts: BTreeSet<HostName> = [HostName::new("github.com").unwrap()].into();
    let mut pacing = SystemPacing::default();
    let cancellation = Cancellation::default();
    let progress = Mutex::new(0u64);
    let mut events = |event| {
        if let crate::provisioning::transfer::TransferEvent::Progress { completed, .. } = event {
            *progress.lock().unwrap() = completed;
        }
    };
    let mut transfer = Transfer {
        network: &network,
        hosts: &hosts,
        policy: RetryPolicy::default(),
        pacing: &mut pacing,
        events: &mut events,
        cancellation: &cancellation,
    };
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let platform = Platform::current().unwrap();
    let mut program = Program::new(
        &pins_for(&first, "9.8.7", EXECUTABLE),
        platform,
        locations.clone(),
    )
    .unwrap()
    .unwrap();
    assert_eq!(program.observe_quick(), Observation::Absent);

    let active = program.install(&mut transfer).unwrap();
    assert!(active.executable.starts_with(&locations.programs));
    assert_eq!(program.observe_quick(), Observation::Present);

    // The program runs as this engine's child, configured only by the engine.
    stand_in(&mut program, "9.8.7");
    let server = program
        .start(free_address(), &Uncontained, &ambient, None)
        .unwrap();
    let address = server.address();
    assert!(address.ip().is_loopback());
    let (status, body) = server.loopback().get("/fake/environment").unwrap();
    assert_eq!(status, 200);
    let environment: BTreeMap<String, String> = serde_json::from_slice(&body).unwrap();
    let home = locations.ollama_home.to_string_lossy().into_owned();
    assert_eq!(environment["OLLAMA_HOST"], address.to_string());
    assert_eq!(
        environment["OLLAMA_MODELS"],
        locations.models.to_string_lossy()
    );
    for name in ["OLLAMA_HOME", "HOME", "USERPROFILE"] {
        assert_eq!(environment[name], home, "{name}");
    }
    assert_eq!(
        environment["OLLAMA_NOPRUNE"], "1",
        "the server never clears blobs the engine has stored before their manifest"
    );
    assert_eq!(
        environment["OLLAMA_NO_CLOUD"], "1",
        "the server reaches no Ollama cloud service"
    );
    assert!(
        environment
            .keys()
            .all(|name| !name.eq_ignore_ascii_case("CARGO_MANIFEST_DIR")),
        "the engine's own environment does not leak into the program"
    );
    let record = ServerRecord::read(&locations.programs).unwrap();
    assert_eq!(record.address, address.to_string());
    assert_eq!(record.version, "9.8.7");
    assert_eq!(record.models, locations.models);
    assert_eq!(Some(record.process_id), server.process_id());
    let (status, _) = server
        .loopback()
        .post(
            "/api/generate",
            br#"{"model":"synthetic-model:test","prompt":"hi"}"#,
        )
        .unwrap();
    assert_eq!(status, 200);

    // A version that has to be put in place again stops the server first.
    fs::remove_file(locations.programs.join("active.json")).unwrap();
    assert_eq!(program.observe_quick(), Observation::Absent);
    program.install(&mut transfer).unwrap();
    assert!(program.server().is_none());
    assert!(!answers(address), "the server outlived its replacement");
    assert!(ServerRecord::read(&locations.programs).is_none());
    assert_eq!(
        publisher.targets().len(),
        1,
        "the stored version was reused"
    );
    let log = fs::read_to_string(locations.ollama_home.join("requests.log")).unwrap();
    assert!(
        log.contains(
            r#"POST /api/generate HTTP/1.1 {"keep_alive":0,"model":"synthetic-model:test"}"#
        ),
        "a loaded model is unloaded before the server ends: {log}"
    );

    // Another engine's newer version waits for the running server's supervisor to stop
    // it before it is put in place.
    let address = program
        .start(free_address(), &Uncontained, &ambient, None)
        .unwrap()
        .address();
    let mut newer = Program::new(
        &pins_for(&second, "9.8.8", EXECUTABLE),
        platform,
        locations.clone(),
    )
    .unwrap()
    .unwrap();
    let (asked, request) = std::sync::mpsc::channel();
    newer.on_change_requested(Box::new(move || asked.send(()).unwrap()));
    // The supervisor's side: it notices the request, while its server still answers, and
    // stops the server, which is what the install waits for.
    let supervisor = std::thread::spawn(move || {
        request.recv().unwrap();
        let requested = program.leases().change_requested().unwrap();
        let answering = answers(address);
        program.stop();
        (program, requested, answering)
    });
    newer.install(&mut transfer).unwrap();
    let (mut program, requested, answering) = supervisor.join().unwrap();
    assert!(
        requested && answering,
        "the server ran until its supervisor stopped it"
    );
    assert!(!answers(address));
    assert_eq!(*progress.lock().unwrap(), second.len() as u64);
    assert_eq!(
        program.observe_quick(),
        Observation::Differs {
            stale: StaleReason::ProgramTooOld
        }
    );
    assert!(matches!(
        program.start(free_address(), &Uncontained, &ambient, None),
        Err(LocalAiError::Failed(FailureCategory::ProgramMissing))
    ));
    newer.prune().unwrap();
    assert_eq!(
        fs::read_dir(locations.programs.join("versions"))
            .unwrap()
            .count(),
        1
    );

    // Removal stops the engine's own server and leaves no version behind.
    stand_in(&mut newer, "9.8.8");
    let address = newer
        .start(free_address(), &Uncontained, &ambient, None)
        .unwrap()
        .address();
    newer.remove().unwrap();
    assert!(!answers(address));
    assert_eq!(newer.observe_quick(), Observation::Absent);
    assert!(!locations.programs.join("versions").exists());
    assert!(locations.ollama_home.exists(), "the program's home is kept");
}

/// Says when the guard of the group it opened is let go.
#[cfg(unix)]
struct Released(std::sync::mpsc::Sender<()>);

#[cfg(unix)]
impl Drop for Released {
    fn drop(&mut self) {
        let _ = self.0.send(());
    }
}

/// Opens a group of the server's own, or fails to open any.
#[cfg(unix)]
struct GroupOpening(Option<std::sync::mpsc::Sender<()>>);

#[cfg(unix)]
impl Containment for GroupOpening {
    fn open_group(&self) -> std::io::Result<Option<ProcessGroup>> {
        let released = self.0.clone().ok_or(std::io::ErrorKind::Unsupported)?;
        Ok(Some(ProcessGroup {
            id: 0,
            guard: Box::new(Released(released)),
        }))
    }

    fn contain(&self, _: &Child) -> std::io::Result<Box<dyn Send>> {
        Ok(Box::new(()))
    }
}

#[cfg(target_os = "linux")]
#[test]
fn the_server_runs_in_the_group_its_containment_opens_which_is_kept_until_it_ends() {
    let directory = tempfile::tempdir().unwrap();
    let locations = Locations::under(directory.path());
    let (mut program, _) = installed(&locations, "9.8.7");
    stand_in(&mut program, "9.8.7");
    let (released, release) = std::sync::mpsc::channel();
    let server = program
        .start(
            free_address(),
            &GroupOpening(Some(released)),
            &ambient,
            None,
        )
        .unwrap();
    let process = server.process_id().unwrap();
    let address = server.address();
    // The fields after the command name in parentheses: state, parent, process group.
    let stat = fs::read_to_string(format!("/proc/{process}/stat")).unwrap();
    let (_, fields) = stat.rsplit_once(") ").unwrap();
    let group: u32 = fields.split_whitespace().nth(2).unwrap().parse().unwrap();
    assert_eq!(
        group, process,
        "a group of its own, as the containment opened"
    );
    assert!(release.try_recv().is_err(), "kept while the server runs");
    program.stop();
    assert!(!answers(address));
    release
        .try_recv()
        .expect("let go once the server has ended");
}

#[cfg(unix)]
#[test]
fn a_group_that_cannot_be_opened_starts_no_server() {
    let directory = tempfile::tempdir().unwrap();
    let locations = Locations::under(directory.path());
    let (mut program, _) = installed(&locations, "9.8.7");
    stand_in(&mut program, "9.8.7");
    let address = free_address();
    let refused = failure(
        program
            .start(address, &GroupOpening(None), &ambient, None)
            .map(|_| ()),
        "no group, no server",
    );
    assert!(matches!(
        refused,
        LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Launch {
            step: LaunchStep::OpenGroup,
            kind: io::ErrorKind::Unsupported,
        }))
    ));
    assert_eq!(refused.category(), FailureCategory::ProgramNotRunning);
    assert!(program.server().is_none());
    assert!(ServerRecord::read(&locations.programs).is_none());
    assert!(!answers(address));
}

/// The failure of a start that must not succeed.
fn failure(result: Result<(), LocalAiError>, expected: &str) -> LocalAiError {
    match result {
        Ok(()) => panic!("{expected}"),
        Err(error) => error,
    }
}

/// Starts `executable` as a server of the installed program through `containment`.
fn spawn_through(
    program: &Program,
    directory: &Path,
    executable: PathBuf,
    containment: &dyn Containment,
) -> LocalAiError {
    let lease = program
        .leases()
        .try_serve()
        .unwrap()
        .expect("no other server");
    let command = ServeCommand {
        executable,
        arguments: ["--exact", "no::such::test"].map(OsString::from).to_vec(),
        environment: BTreeMap::new(),
        working_directory: directory.to_path_buf(),
        address: free_address(),
    };
    failure(
        Server::spawn(
            LocalEngine::Ollama,
            command,
            "9.8.7",
            directory.join(SERVER_RECORD),
            containment,
            lease,
            None,
        )
        .map(|_| ()),
        "the server must not start",
    )
}

#[test]
fn a_server_the_system_cannot_create_says_which_step_failed_and_why() {
    let directory = tempfile::tempdir().unwrap();
    let locations = Locations::under(directory.path());
    let (program, _) = installed(&locations, "9.8.7");
    let error = spawn_through(
        &program,
        directory.path(),
        directory.path().join("absent-program"),
        &Uncontained,
    );
    assert!(matches!(
        error,
        LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Launch {
            step: LaunchStep::Create,
            kind: io::ErrorKind::NotFound,
        }))
    ));
    assert_eq!(error.category(), FailureCategory::ProgramNotRunning);
}

#[cfg(windows)]
#[test]
fn a_creation_the_system_refuses_as_no_program_image_reads_as_a_damaged_program() {
    // ERROR_BAD_EXE_FORMAT and ERROR_EXE_MACHINE_TYPE_MISMATCH.
    for code in [193, 216] {
        let error = launch_failure(LaunchStep::Create, &io::Error::from_raw_os_error(code));
        assert!(
            matches!(
                error,
                LocalAiError::NotRunning(NotRunningCause::Start(
                    ServerStartFailure::ProgramDamaged
                ))
            ),
            "{code}: {error}"
        );
        assert_eq!(error.category(), FailureCategory::DamagedDownload);
    }
    // Any other refusal, and the same code from another step, keeps its own account.
    let denied = launch_failure(LaunchStep::Create, &io::Error::from_raw_os_error(5));
    assert_eq!(denied.category(), FailureCategory::ProgramNotRunning);
    let contained = launch_failure(LaunchStep::Contain, &io::Error::from_raw_os_error(216));
    assert!(matches!(
        contained,
        LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Launch {
            step: LaunchStep::Contain,
            ..
        }))
    ));
}

#[cfg(all(windows, feature = "platform"))]
#[test]
fn a_program_file_that_is_no_image_fails_the_start_as_damaged_and_never_hangs() {
    use std::{sync::mpsc, time::Duration};
    // Far above a refusal's milliseconds: past it, an error dialog is waiting.
    const BOUND: Duration = Duration::from_secs(60);
    let (sender, receiver) = mpsc::channel();
    std::thread::spawn(move || {
        let directory = tempfile::tempdir().unwrap();
        let locations = Locations::under(directory.path());
        let (program, _) = installed(&locations, "9.8.7");
        let image = directory.path().join("damaged-server.exe");
        fs::write(
            &image,
            b"#!/bin/sh
exit 3
",
        )
        .unwrap();
        let error = spawn_through(&program, directory.path(), image, &Uncontained);
        let damaged = matches!(
            error,
            LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::ProgramDamaged))
        );
        let _ = sender.send((damaged, error.category()));
    });
    let (damaged, category) = receiver
        .recv_timeout(BOUND)
        .expect("the start returned: an error dialog is not waiting");
    assert!(damaged);
    assert_eq!(category, FailureCategory::DamagedDownload);
}

#[test]
fn a_damaged_program_is_recorded_and_reads_as_damaged_until_a_start_succeeds() {
    let directory = tempfile::tempdir().unwrap();
    let programs = directory.path();
    record_start_failure(programs, &ServerStartFailure::ProgramDamaged);
    let record: serde_json::Value =
        serde_json::from_slice(&fs::read(programs.join(START_FAILURE_RECORD)).unwrap()).unwrap();
    assert_eq!(
        record,
        serde_json::json!({"schema": 1, "reason": "server_program_damaged"})
    );
    let latest = latest_start_failure(programs);
    assert_eq!(latest, Some(StartFailureKind::ProgramDamaged));
    // A wait that runs out after such a start, and a quick look with no server running,
    // read the program as damaged; any other kind, or none, reads as not running.
    let waited = NotRunningCause::NoServerWithin {
        budget: START_BUDGET,
        latest_start: latest,
    };
    assert_eq!(waited.category(), FailureCategory::DamagedDownload);
    assert_eq!(
        StartFailureKind::category_after(latest),
        FailureCategory::DamagedDownload
    );
    for other in [
        None,
        Some(StartFailureKind::Launch),
        Some(StartFailureKind::Closed),
    ] {
        assert_eq!(
            StartFailureKind::category_after(other),
            FailureCategory::ProgramNotRunning
        );
    }
    clear_start_failure(programs);
    assert_eq!(latest_start_failure(programs), None);
}

struct Refusing;

impl Containment for Refusing {
    fn contain(&self, _: &Child) -> io::Result<Box<dyn Send>> {
        Err(io::ErrorKind::PermissionDenied.into())
    }
}

#[test]
fn a_server_that_cannot_be_contained_says_so_and_does_not_run() {
    let directory = tempfile::tempdir().unwrap();
    let locations = Locations::under(directory.path());
    let (program, _) = installed(&locations, "9.8.7");
    let error = spawn_through(
        &program,
        directory.path(),
        std::env::current_exe().unwrap(),
        &Refusing,
    );
    assert!(matches!(
        error,
        LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Launch {
            step: LaunchStep::Contain,
            kind: io::ErrorKind::PermissionDenied,
        }))
    ));
    assert_eq!(error.category(), FailureCategory::ProgramNotRunning);
}

#[test]
fn a_program_that_never_listens_or_answers_otherwise_is_ended_and_not_running() {
    let bytes = archive(b"only");
    let (certificate, publisher) = publisher(vec![("9.8.7".into(), bytes.clone())]);
    let network = network_to(certificate.roots(), publisher.address(), None);
    let hosts: BTreeSet<HostName> = [HostName::new("github.com").unwrap()].into();
    let mut pacing = SystemPacing::default();
    let cancellation = Cancellation::default();
    let mut events = |_| {};
    let mut transfer = Transfer {
        network: &network,
        hosts: &hosts,
        policy: RetryPolicy::default(),
        pacing: &mut pacing,
        events: &mut events,
        cancellation: &cancellation,
    };
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let mut program = Program::new(
        &pins_for(&bytes, "9.8.7", EXECUTABLE),
        Platform::current().unwrap(),
        locations.clone(),
    )
    .unwrap()
    .unwrap();
    assert!(matches!(
        program.start(free_address(), &Uncontained, &ambient, None),
        Err(LocalAiError::Failed(FailureCategory::ProgramMissing))
    ));
    program.install(&mut transfer).unwrap();

    // A program that exits without announcing itself is seen to end at once.
    program.serve_override = Some(ServeOverride {
        arguments: ["--exact", "no::such::test"].map(OsString::from).to_vec(),
        environment: Vec::new(),
    });
    let exited = failure(
        program
            .start(free_address(), &Uncontained, &ambient, None)
            .map(|_| ()),
        "a program that exits is not running",
    );
    assert!(
        matches!(
            exited,
            LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Closed { .. }))
        ),
        "{exited}"
    );
    assert_eq!(
        program.latest_start_failure(),
        Some(StartFailureKind::Closed),
        "the failed start is recorded for an engine waiting elsewhere"
    );
    assert_eq!(exited.category(), FailureCategory::ProgramNotRunning);
    // A program that listens but reports another version is ended.
    stand_in(&mut program, "0.0.1");
    let other = failure(
        program
            .start(free_address(), &Uncontained, &ambient, None)
            .map(|_| ()),
        "another version is not the pinned one",
    );
    assert!(
        matches!(
            &other,
            LocalAiError::NotRunning(NotRunningCause::Start(ServerStartFailure::Version(VersionFailure::Different { found })))
                if found == "0.0.1"
        ),
        "{other}"
    );
    assert_eq!(
        program.latest_start_failure(),
        Some(StartFailureKind::VersionUnconfirmed),
        "the record holds the latest failed start"
    );
    let record: serde_json::Value =
        serde_json::from_slice(&fs::read(locations.programs.join(START_FAILURE_RECORD)).unwrap())
            .unwrap();
    assert_eq!(
        record,
        serde_json::json!({
            "schema": 1,
            "reason": "server_version_unconfirmed",
            "last_check": "different_version",
        }),
        "the record says what the last check got, and not the version the server sent"
    );
    assert_eq!(other.category(), FailureCategory::ProgramNotRunning);
    assert_eq!(
        other.to_string(),
        "local AI failed: program_not_running: its version could not be confirmed: it reports version 0.0.1"
    );
    assert!(program.server().is_none());
    assert!(ServerRecord::read(&locations.programs).is_none());
    assert_eq!(
        program.observe_full(),
        Observation::Failed(FailureCategory::ProgramNotRunning)
    );
    stand_in(&mut program, "9.8.7");
    // The full check only observes: it starts nothing of its own.
    assert_eq!(
        program.observe_full(),
        Observation::Failed(FailureCategory::ProgramNotRunning)
    );
    assert!(program.server().is_none());
    let address = program
        .start(free_address(), &Uncontained, &ambient, None)
        .unwrap()
        .address();
    assert_eq!(program.observe_full(), Observation::Present);
    // A second start under the same lease is refused while this server holds it.
    let mut second = Program::new(
        &pins_for(&bytes, "9.8.7", EXECUTABLE),
        Platform::current().unwrap(),
        locations.clone(),
    )
    .unwrap()
    .unwrap();
    stand_in(&mut second, "9.8.7");
    assert!(matches!(
        second.start(free_address(), &Uncontained, &ambient, None),
        Err(LocalAiError::Engine(Error::Busy))
    ));
    assert_eq!(
        second.running_server().map(|server| server.address()),
        Some(address),
        "another engine observes the one running server"
    );
    assert_eq!(
        second.latest_start_failure(),
        None,
        "a start that succeeded clears the failed one, and a refused start records none"
    );
    drop(second);
    assert!(
        answers(address),
        "an observing engine leaves the server running"
    );
    drop(program);
    assert!(
        !answers(address),
        "dropping the engine's program ends its server"
    );
}

#[test]
fn a_program_that_announces_before_it_answers_is_waited_for_within_the_start_budget() {
    let bytes = archive(b"only");
    let (certificate, publisher) = publisher(vec![("9.8.7".into(), bytes.clone())]);
    let network = network_to(certificate.roots(), publisher.address(), None);
    let hosts: BTreeSet<HostName> = [HostName::new("github.com").unwrap()].into();
    let mut pacing = SystemPacing::default();
    let cancellation = Cancellation::default();
    let mut events = |_| {};
    let mut transfer = Transfer {
        network: &network,
        hosts: &hosts,
        policy: RetryPolicy::default(),
        pacing: &mut pacing,
        events: &mut events,
        cancellation: &cancellation,
    };
    let root = tempfile::tempdir().unwrap();
    let locations = Locations::under(root.path());
    let mut program = Program::new(
        &pins_for(&bytes, "9.8.7", EXECUTABLE),
        Platform::current().unwrap(),
        locations.clone(),
    )
    .unwrap()
    .unwrap();
    program.install(&mut transfer).unwrap();

    // Silent for longer than one unbounded loopback question waits, and well inside the
    // start budget.
    let silence = Loopback::new(free_address()).unwrap().io_timeout + Duration::from_secs(2);
    assert!(silence < START_BUDGET);
    stand_in(&mut program, "9.8.7");
    if let Some(stand_in) = program.serve_override.as_mut() {
        stand_in.environment.push((
            OsString::from(HELPER_SILENCE),
            OsString::from(silence.as_millis().to_string()),
        ));
    }
    let began = std::time::Instant::now();
    let address = program
        .start(free_address(), &Uncontained, &ambient, None)
        .map(|server| server.address())
        .expect("a server that answers within the start budget runs");
    let waited = began.elapsed();
    assert!(
        waited >= silence && waited < START_BUDGET,
        "the start waited {waited:?} for a server silent for {silence:?}"
    );
    assert_eq!(program.latest_start_failure(), None);
    assert!(answers(address));
    drop(program);
    assert!(!answers(address), "dropping the program ends its server");
}

#[test]
fn the_start_failure_record_keeps_what_the_last_check_got_and_reads_records_without_it() {
    let root = tempfile::tempdir().unwrap();
    let programs = root.path();
    record_start_failure(
        programs,
        &ServerStartFailure::Version(VersionFailure::Status(503)),
    );
    let record: serde_json::Value =
        serde_json::from_slice(&fs::read(programs.join(START_FAILURE_RECORD)).unwrap()).unwrap();
    assert_eq!(
        record,
        serde_json::json!({
            "schema": 1,
            "reason": "server_version_unconfirmed",
            "last_check": "status_503",
        })
    );
    assert_eq!(
        latest_start_failure(programs),
        Some(StartFailureKind::VersionUnconfirmed)
    );

    record_start_failure(
        programs,
        &ServerStartFailure::Version(VersionFailure::Unreachable("timed out".into())),
    );
    let written = fs::read_to_string(programs.join(START_FAILURE_RECORD)).unwrap();
    assert!(
        written.contains(r#""last_check":"unreachable""#),
        "{written}"
    );
    assert!(
        !written.contains("timed out"),
        "the record keeps no error text"
    );

    // A kind other than an unconfirmed version has no last check.
    record_start_failure(programs, &ServerStartFailure::LogUnreadable);
    let record: serde_json::Value =
        serde_json::from_slice(&fs::read(programs.join(START_FAILURE_RECORD)).unwrap()).unwrap();
    assert!(record.get("last_check").is_none(), "{record}");
    assert_eq!(
        latest_start_failure(programs),
        Some(StartFailureKind::LogUnreadable)
    );

    // A record an earlier build wrote reads as before.
    earlier_failure(programs);
    assert_eq!(
        latest_start_failure(programs),
        Some(StartFailureKind::Launch)
    );
    assert_eq!(
        StartFailureKind::from_reason("server_version_unconfirmed"),
        Some(StartFailureKind::VersionUnconfirmed)
    );
}

#[test]
fn a_copy_installed_outside_cadrumo_is_reported_and_left_untouched() {
    let root = tempfile::tempdir().unwrap();
    let own = root.path().join("components/ollama");
    let on_path = root.path().join("tools");
    let local = root.path().join("local");
    let name = if cfg!(windows) {
        "ollama.exe"
    } else {
        "ollama"
    };
    let lookup = |variable: &str| match variable {
        "PATH" => Some(std::env::join_paths([own.join("versions"), on_path.clone()]).unwrap()),
        "LOCALAPPDATA" => Some(local.clone().into_os_string()),
        _ => None,
    };
    let candidates = system_locations(&lookup);
    assert_eq!(candidates[0], own.join("versions").join(name));
    assert_eq!(candidates[1], on_path.join(name));
    if cfg!(windows) {
        assert_eq!(
            candidates[2],
            local.join("Programs").join("Ollama").join(name)
        );
    } else if cfg!(target_os = "macos") {
        assert!(candidates.contains(&PathBuf::from(
            "/Applications/Ollama.app/Contents/Resources/ollama"
        )));
    } else {
        assert!(candidates.contains(&PathBuf::from("/usr/bin/ollama")));
    }
    let candidates = [
        own.join("versions").join(name),
        on_path.join(name),
        local.join("Programs").join("Ollama").join(name),
    ];
    assert_eq!(system_program(&candidates, &own), None);
    fs::create_dir_all(own.join("versions")).unwrap();
    fs::write(&candidates[0], b"cadrumo's own").unwrap();
    assert_eq!(
        system_program(&candidates, &own),
        None,
        "the engine's own copy is not a system one"
    );
    fs::create_dir_all(candidates[2].parent().unwrap()).unwrap();
    fs::write(&candidates[2], b"installed by its publisher").unwrap();
    let before = fs::metadata(&candidates[2]).unwrap().modified().unwrap();
    assert_eq!(
        system_program(&candidates, &own).as_ref(),
        Some(&candidates[2])
    );
    assert_eq!(
        fs::read(&candidates[2]).unwrap(),
        b"installed by its publisher"
    );
    assert_eq!(
        fs::metadata(&candidates[2]).unwrap().modified().unwrap(),
        before
    );
}

/// The fixed address the package's environment declaration gives the local AI server.
fn declared_address() -> SocketAddr {
    let native = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
    let declared: toml::Table =
        toml::from_str(&fs::read_to_string(native.join("application-environment.toml")).unwrap())
            .unwrap();
    declared["components"]["local_ai_address"]
        .as_str()
        .unwrap()
        .parse()
        .unwrap()
}

#[test]
fn the_record_names_the_program_the_models_and_the_fixed_address() {
    let directory = tempfile::tempdir().unwrap();
    let storage = directory.path().join("storage");
    let locations = Locations::under(&storage);
    // One platform's layout from one archive, so the record is the same on every host.
    let (program, pins) = installed_with(
        &locations,
        "0.40.10",
        Platform::WinX64,
        "ollama.exe",
        b"local AI program",
    );
    let receipts = ReceiptStore::new(locations.receipts.clone()).unwrap();
    let address = declared_address();
    assert!(address.ip().is_loopback());
    assert_ne!(address.port(), 11434, "never the publisher's default port");
    assert!(
        program
            .settle(&receipts, "192.0.2.1:80".parse().unwrap(), UNIX_EPOCH)
            .is_err(),
        "only a loopback address is recorded"
    );
    program
        .settle(
            &receipts,
            address,
            UNIX_EPOCH + Duration::from_secs(1_792_846_800),
        )
        .unwrap();
    let ReceiptReading::Present(receipt) = receipts.read(ItemId::LocalAi) else {
        panic!("the receipt reads back");
    };
    let location = receipt.location.as_ref().unwrap();
    assert_eq!(location.root(), storage);
    assert_eq!(location.facts["address"], address.to_string());
    assert!(location.paths["program"].under(&location.root()).is_file());
    // The version folder is named by the pinned archive's digest: the one part of the
    // record that follows the archive's bytes.
    let archive = pins.for_platform(Platform::WinX64).unwrap();
    assert_eq!(
        location.paths["program"].as_str(),
        format!(
            "components/ollama/versions/{}-0/payload/ollama.exe",
            archive.sha256
        )
    );
    assert_eq!(
        location.paths["models"].under(&location.root()),
        locations.models
    );
}
