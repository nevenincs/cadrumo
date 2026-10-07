//! Fixture image for the supervision tests; built only with the fixture test mode.
//!
//! Launched with the runtime's supervised arguments it stands in for the runtime: it speaks
//! the line protocol over its standard streams, publishes a boot record, maps console
//! Ctrl+C to a signal stop and follows one behaviour line per launch from the synthetic
//! root's `fixture-plan`. It writes its own protocol lines by hand, independently of the
//! manager's encoder. Launched with `--harness` it runs the supervision core with no
//! console, as the manager image does, and prints what the core observed.

#[cfg(windows)]
mod fixture {
    #![allow(unsafe_code)]

    use cadrumo_manager::supervision::adoption::{InstalledVersion, InstalledVersions};
    use cadrumo_manager::supervision::launch::LaunchTarget;
    use cadrumo_manager::supervision::stop::PlatformStopSignal;
    use cadrumo_manager::supervision::supervisor::{
        Collaborators, Event, Request, SessionActivity, Supervisor, SupervisorConfig, VersionProbe,
    };
    use serde_json::{Value, json};
    use std::collections::HashMap;
    use std::env;
    use std::ffi::c_void;
    use std::fs::{self, File, OpenOptions};
    use std::io::{BufRead, BufReader, ErrorKind, Write};
    use std::os::windows::io::FromRawHandle;
    use std::path::{Path, PathBuf};
    use std::process;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::mpsc::{self, RecvTimeoutError};
    use std::thread;
    use std::time::{Duration, SystemTime, UNIX_EPOCH};

    const STD_INPUT_HANDLE: u32 = 0xFFFF_FFF6;
    const STD_OUTPUT_HANDLE: u32 = 0xFFFF_FFF5;
    const SIGNAL_STOP: u32 = 65;
    const SUPERVISOR_STOP: u32 = 64;
    const SESSION_END_SETTLE: u32 = 66;
    const DRAIN_WATCHDOG: u32 = 71;
    const VERSION_MISMATCH: u32 = 69;
    const USAGE: u32 = 2;
    const UNEXPECTED_FAILURE: u32 = 73;
    /// A fixture left behind by a failed test run ends on its own after this bound.
    const LIFETIME: Duration = Duration::from_secs(120);

    #[repr(C)]
    #[derive(Default)]
    struct FileTime {
        low: u32,
        high: u32,
    }

    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetStdHandle(which: u32) -> *mut c_void;
        fn SetStdHandle(which: u32, handle: *mut c_void) -> i32;
        fn GetCurrentProcess() -> *mut c_void;
        fn GetProcessTimes(
            process: *mut c_void,
            creation: *mut FileTime,
            exit: *mut FileTime,
            kernel: *mut FileTime,
            user: *mut FileTime,
        ) -> i32;
        fn SetConsoleCtrlHandler(
            handler: Option<unsafe extern "system" fn(u32) -> i32>,
            add: i32,
        ) -> i32;
    }

    static INTERRUPTED: AtomicBool = AtomicBool::new(false);

    unsafe extern "system" fn on_interrupt(event: u32) -> i32 {
        if event <= 1 {
            INTERRUPTED.store(true, Ordering::SeqCst);
            1
        } else {
            0
        }
    }

    fn exit(code: u32) -> ! {
        process::exit(i32::from_ne_bytes(code.to_ne_bytes()))
    }

    /// Take sole ownership of one standard handle, as the runtime moves its protocol streams.
    fn take_standard(which: u32) -> Option<File> {
        // SAFETY: GetStdHandle only reads this process's standard handle slot.
        let handle = unsafe { GetStdHandle(which) };
        if handle.is_null() || handle as isize == -1 {
            return None;
        }
        // SAFETY: clearing the slot leaves this function the only holder of `handle`; the
        // fixture never reads the standard streams through std afterwards.
        unsafe { SetStdHandle(which, std::ptr::null_mut()) };
        // SAFETY: `handle` is an open handle this process owns and nothing else will close.
        Some(unsafe { File::from_raw_handle(handle.cast()) })
    }

    fn process_created() -> u64 {
        let (mut created, mut exited, mut kernel, mut user) = Default::default();
        // SAFETY: the pseudo-handle names this process for its lifetime; the four
        // out-pointers are distinct locals that outlive the call.
        let succeeded = unsafe {
            GetProcessTimes(
                GetCurrentProcess(),
                &mut created,
                &mut exited,
                &mut kernel,
                &mut user,
            )
        };
        assert_ne!(succeeded, 0, "GetProcessTimes");
        let FileTime { low, high } = created;
        (u64::from(high) << 32) | u64::from(low)
    }

    struct Arguments {
        root: PathBuf,
        identity: String,
        version: String,
    }

    fn arguments(raw: &[String]) -> Option<Arguments> {
        match raw {
            [
                root,
                root_value,
                identity,
                identity_value,
                version,
                version_value,
                supervised,
            ] if root == "--storage-root"
                && identity == "--storage-identity"
                && version == "--expected-version"
                && supervised == "--supervised" =>
            {
                Some(Arguments {
                    root: PathBuf::from(root_value),
                    identity: identity_value.clone(),
                    version: version_value.clone(),
                })
            }
            _ => None,
        }
    }

    /// Claim the next launch index and record what this launch received.
    fn record_launch(root: &Path, raw: &[String]) -> usize {
        let environment: Vec<String> = env::vars_os()
            .map(|(name, _)| name.to_string_lossy().into_owned())
            .collect();
        let record = json!({"pid": process::id(), "arguments": raw, "environment": environment,
            "pinned_root": env::var(cadrumo_manager::contract::ROOT_VARIABLE).ok()});
        for index in 0.. {
            let path = root.join(format!("fixture-launch-{index}"));
            match OpenOptions::new().write(true).create_new(true).open(&path) {
                Ok(mut file) => {
                    file.write_all(record.to_string().as_bytes())
                        .expect("write the launch record");
                    return index;
                }
                Err(error) if error.kind() == ErrorKind::AlreadyExists => {}
                Err(error) => panic!("claim a launch index: {error}"),
            }
        }
        unreachable!()
    }

    fn behaviour(root: &Path, index: usize) -> (String, HashMap<String, String>) {
        let plan = fs::read_to_string(root.join("fixture-plan")).expect("read the fixture plan");
        let lines: Vec<&str> = plan
            .lines()
            .filter(|line| !line.trim().is_empty())
            .collect();
        let line = lines
            .get(index)
            .or(lines.last())
            .expect("the plan has a line");
        let mut tokens = line.split_whitespace();
        let mode = tokens.next().expect("a mode").to_owned();
        let options = tokens
            .map(|token| match token.split_once('=') {
                Some((key, value)) => (key.to_owned(), value.to_owned()),
                None => (token.to_owned(), String::new()),
            })
            .collect();
        (mode, options)
    }

    fn boot_id() -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock after the epoch")
            .as_nanos();
        let digits = format!("{:032x}", nanos ^ (u128::from(process::id()) << 96));
        format!(
            "{}-{}-{}-{}-{}",
            &digits[..8],
            &digits[8..12],
            &digits[12..16],
            &digits[16..20],
            &digits[20..]
        )
    }

    struct Boot {
        id: String,
        version: String,
        admission: String,
    }

    fn publish_boot_record(root: &Path, boot: &Boot, options: &HashMap<String, String>) {
        let mut created = process_created();
        if options.contains_key("forge_created") {
            created += 1;
        }
        let package = env::current_exe()
            .expect("current image")
            .parent()
            .expect("image directory")
            .to_string_lossy()
            .into_owned();
        let record = json!({
            "admission": boot.admission,
            "boot_id": boot.id,
            "package_directory": package,
            "pid": process::id(),
            "process_created": created,
            "schema_version": 1,
            "version": boot.version,
        });
        let directory = root.join(".runtime");
        fs::create_dir_all(&directory).expect("create .runtime");
        let staged = directory.join(format!("boot.json.{}", process::id()));
        fs::write(&staged, record.to_string()).expect("stage the boot record");
        fs::rename(&staged, directory.join("boot.json")).expect("publish the boot record");
    }

    struct Announcer(Option<File>);

    impl Announcer {
        fn line(&mut self, line: &str) {
            if let Some(file) = self.0.as_mut()
                && file.write_all(format!("{line}\n").as_bytes()).is_err()
            {
                self.0 = None;
            }
        }

        fn stopping(&mut self, reason: u32) -> ! {
            self.line(&format!("{{\"type\":\"stopping\",\"reason\":{reason}}}"));
            exit(reason)
        }
    }

    fn ready(announcer: &mut Announcer, boot: &Boot, identity: &str) {
        announcer.line(&format!(
            "{{\"type\":\"ready\",\"boot_id\":\"{}\",\"pid\":{},\"version\":\"{}\",\
             \"storage_identity\":\"{identity}\",\"admission\":\"{}\"}}",
            boot.id,
            process::id(),
            boot.version,
            boot.admission
        ));
    }

    fn commands(input: Option<File>) -> mpsc::Receiver<Result<Value, ()>> {
        let (sender, receiver) = mpsc::channel();
        if let Some(input) = input {
            thread::spawn(move || {
                for line in BufReader::new(input).lines() {
                    let Ok(line) = line else { return };
                    let parsed = serde_json::from_str::<Value>(&line).map_err(|_| ());
                    if sender.send(parsed).is_err() {
                        return;
                    }
                }
            });
        }
        receiver
    }

    pub fn runtime(raw: &[String]) -> ! {
        let Some(arguments) = arguments(raw) else {
            exit(USAGE)
        };
        let input = take_standard(STD_INPUT_HANDLE);
        let mut announcer = Announcer(take_standard(STD_OUTPUT_HANDLE));
        // SAFETY: restores Ctrl+C processing, then installs a handler that only stores an
        // atomic, as the supervised runtime does.
        unsafe {
            SetConsoleCtrlHandler(None, 0);
            SetConsoleCtrlHandler(Some(on_interrupt), 1);
        }
        thread::spawn(|| {
            thread::sleep(LIFETIME);
            exit(UNEXPECTED_FAILURE)
        });
        let index = record_launch(&arguments.root, raw);
        let (mode, options) = behaviour(&arguments.root, index);
        let option = |name: &str| options.get(name).cloned();
        let boot = Boot {
            id: boot_id(),
            version: option("version").unwrap_or_else(|| arguments.version.clone()),
            admission: option("admission").unwrap_or_else(|| "native".into()),
        };
        if let Some(accepted) = option("accept_version")
            && accepted != arguments.version
        {
            exit(VERSION_MISMATCH)
        }
        match mode.as_str() {
            "exit" => {
                let code: u32 = option("code")
                    .and_then(|code| code.parse().ok())
                    .expect("code");
                if options.contains_key("after_ready") {
                    publish_boot_record(&arguments.root, &boot, &options);
                    ready(&mut announcer, &boot, &arguments.identity);
                    thread::sleep(Duration::from_millis(50));
                }
                exit(code)
            }
            "silent" => loop {
                thread::sleep(Duration::from_secs(1));
            },
            "serve" => serve(arguments, boot, options, input, announcer),
            other => panic!("unknown fixture mode {other}"),
        }
    }

    fn serve(
        arguments: Arguments,
        boot: Boot,
        options: HashMap<String, String>,
        input: Option<File>,
        mut announcer: Announcer,
    ) -> ! {
        let number = |name: &str| {
            options
                .get(name)
                .and_then(|value| value.parse::<u64>().ok())
        };
        let hang_after = number("hang_after");
        let hard_hang = options.get("hang").is_some_and(|hang| hang == "hard");
        let busy = options.contains_key("busy");
        let tick_age = number("tick_age_ms").unwrap_or(3);
        publish_boot_record(&arguments.root, &boot, &options);
        ready(&mut announcer, &boot, &arguments.identity);
        if options.contains_key("close_announcements") {
            announcer.0 = None;
        }
        let commands = commands(input);
        let mut answered = 0_u64;
        let mut connected = true;
        loop {
            let hung = hang_after.is_some_and(|limit| answered >= limit);
            if INTERRUPTED.load(Ordering::SeqCst) && !(hung && hard_hang) {
                announcer.stopping(SIGNAL_STOP);
            }
            let command = if connected {
                match commands.recv_timeout(Duration::from_millis(5)) {
                    Ok(command) => command,
                    Err(RecvTimeoutError::Timeout) => continue,
                    // End of input: the supervisor is gone, and serving continues.
                    Err(RecvTimeoutError::Disconnected) => {
                        connected = false;
                        continue;
                    }
                }
            } else {
                thread::sleep(Duration::from_millis(5));
                continue;
            };
            let Ok(command) = command else {
                announcer.line("{\"type\":\"refused\",\"code\":\"malformed\"}");
                continue;
            };
            match command.get("type").and_then(Value::as_str) {
                Some("ping") if !hung => {
                    let seq = command.get("seq").and_then(Value::as_u64).expect("seq");
                    answered += 1;
                    announcer.line(&format!(
                        "{{\"type\":\"heartbeat\",\"seq\":{seq},\"tick_age_ms\":{tick_age},\
                         \"frontends\":0,\"in_flight_operations\":{}}}",
                        u8::from(busy)
                    ));
                }
                Some("ping") => {}
                Some("stop") if hung && hard_hang => {}
                Some("stop") if hung => {
                    thread::sleep(Duration::from_millis(50));
                    exit(DRAIN_WATCHDOG)
                }
                Some("stop") => announcer.stopping(SUPERVISOR_STOP),
                Some("stop-if-idle") if busy => announcer.line("{\"type\":\"busy\"}"),
                Some("stop-if-idle") => announcer.stopping(SUPERVISOR_STOP),
                Some("session-end") if hung && hard_hang => {}
                Some("session-end") => announcer.stopping(SESSION_END_SETTLE),
                _ => announcer.line("{\"type\":\"refused\",\"code\":\"malformed\"}"),
            }
        }
    }

    struct Active;

    impl SessionActivity for Active {
        fn is_active(&self) -> bool {
            true
        }
    }

    struct NoProbe;

    impl VersionProbe for NoProbe {
        fn reprobe(&mut self) -> Option<String> {
            None
        }
    }

    struct NoVersions;

    impl InstalledVersions for NoVersions {
        fn containing(&self, _image: &Path) -> Option<InstalledVersion> {
            None
        }

        fn failed(&self, _version: &str) -> bool {
            false
        }
    }

    /// Run the core with no console, ask for a stop once the channel closes, print events.
    pub fn harness(raw: &[String]) -> ! {
        let [scenario, root, identity, version] = raw else {
            exit(USAGE)
        };
        assert_eq!(scenario, "stop-without-channel", "unknown harness scenario");
        let image = env::current_exe().expect("current image");
        let target = LaunchTarget::fixture(
            image,
            PathBuf::from(root),
            identity.clone(),
            version.clone(),
        )
        .expect("fixture target");
        let config = SupervisorConfig {
            readiness_ceiling: Duration::from_secs(20),
            heartbeat_interval: Duration::from_millis(50),
            heartbeat_staleness: Duration::from_secs(20),
            accept_tick_ceiling: Duration::from_secs(5),
            drain_bound: Duration::from_secs(10),
            termination_bound: Duration::from_secs(5),
            poll_interval: Duration::from_millis(10),
            ..SupervisorConfig::default()
        };
        let collaborators = Collaborators {
            session: Box::new(Active),
            probe: Box::new(NoProbe),
            versions: Box::new(NoVersions),
            stop_signal: Box::new(PlatformStopSignal::default()),
        };
        let (events, observed) = mpsc::channel();
        let mut supervisor = Supervisor::new(config, target, collaborators, events);
        let handle = supervisor.handle();
        let running = thread::spawn(move || supervisor.run());
        let mut out = std::io::stdout().lock();
        for event in observed {
            if matches!(event, Event::ChannelClosed { .. }) {
                handle.request(Request::Stop);
            }
            writeln!(out, "event {event:?}").expect("report an event");
        }
        let outcome = running.join().expect("the supervisor thread");
        writeln!(out, "outcome {outcome:?}").expect("report the outcome");
        exit(0)
    }
}

#[cfg(windows)]
fn main() {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    match raw.split_first() {
        Some((first, rest)) if first == "--harness" => fixture::harness(rest),
        _ => fixture::runtime(&raw),
    }
}

#[cfg(not(windows))]
fn main() {
    // The fixture runtime and harness exist for the Windows supervision core so far.
    std::process::exit(2);
}
