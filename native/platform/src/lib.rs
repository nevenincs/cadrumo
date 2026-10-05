#[cfg(not(target_os = "windows"))]
compile_error!("Only the Windows foundation has been implemented");

use std::os::windows::{ffi::OsStringExt, fs::MetadataExt};
use std::{
    env,
    ffi::{OsString, c_void},
    fs,
    path::{Path, PathBuf},
    ptr,
};
include!(env!("CADRUMO_CONTRACT_RS"));
pub mod desktop;

#[repr(C)]
pub struct Buffer {
    data: *mut u8,
    len: u64,
}
pub struct Context {
    paths: Vec<PathBuf>,
}

fn buffer(s: String) -> Buffer {
    let bytes = s.into_bytes().into_boxed_slice();
    let len = bytes.len() as u64;
    Buffer {
        data: Box::into_raw(bytes) as *mut u8,
        len,
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Development,
    Installed,
}

/// Package or checkout evidence for one executable; the working directory is never read.
#[derive(Debug, PartialEq, Eq)]
struct Evidence {
    mode: Mode,
    package: PathBuf,
    checkout: Option<PathBuf>,
}

/// A declared refusal: `code` is one of the contract's root refusals.
#[derive(Debug, PartialEq, Eq)]
struct Refusal {
    code: &'static str,
    message: String,
}

fn refusal(code: &'static str, message: String) -> Refusal {
    debug_assert!(ROOT_REFUSALS.contains(&code), "undeclared refusal {code}");
    Refusal { code, message }
}

fn relative_components(relative: &str) -> PathBuf {
    relative
        .split('/')
        .filter(|part| !part.is_empty() && *part != ".")
        .collect()
}

/// Declared console entrypoints live in NATIVE; every other image sits at the package root.
fn package_root(exe: &Path) -> Result<PathBuf, String> {
    let directory = exe.parent().ok_or("Executable has no parent")?;
    let declared = exe
        .file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| {
            ENTRYPOINT_FILES
                .iter()
                .any(|file| file.eq_ignore_ascii_case(name))
        });
    if !declared {
        return Ok(directory.to_path_buf());
    }
    let mut package = directory;
    for expected in Path::new(NATIVE).components().rev() {
        let inside = package
            .file_name()
            .and_then(|name| name.to_str())
            .zip(expected.as_os_str().to_str())
            .is_some_and(|(actual, expected)| actual.eq_ignore_ascii_case(expected));
        if !inside {
            return Err(format!(
                "Entrypoint must reside in the package {NATIVE} directory: {}",
                exe.display()
            ));
        }
        package = package.parent().ok_or("Entrypoint has no package root")?;
    }
    Ok(package.to_path_buf())
}

/// Installed when the package root holds the package manifest; development when a
/// checkout marker is an ancestor of the executable; otherwise refuse.
fn detect_mode(exe: &Path) -> Result<Evidence, String> {
    let package = package_root(exe)?.join(relative_components(MODE_PACKAGE_ROOT_FROM_EXECUTABLE));
    if package
        .join(relative_components(MODE_PACKAGE_MANIFEST))
        .is_file()
    {
        return Ok(Evidence {
            mode: Mode::Installed,
            package,
            checkout: None,
        });
    }
    let directory = exe.parent().ok_or("Executable has no parent")?;
    if let Some(checkout) = directory
        .ancestors()
        .find(|ancestor| ancestor.join(MODE_CHECKOUT_MARKER).is_file())
    {
        return Ok(Evidence {
            mode: Mode::Development,
            package,
            checkout: Some(checkout.to_path_buf()),
        });
    }
    Err(format!(
        "CADRUMO cannot tell whether {} is installed or a development build: \
         {MODE_PACKAGE_MANIFEST} is not in the package and no ancestor directory holds \
         {MODE_CHECKOUT_MARKER}. Reinstall CADRUMO or run it from a source checkout.",
        exe.display()
    ))
}

fn channel_directory(channel: &str) -> String {
    if channel == STABLE_CHANNEL {
        PRODUCT_DIRECTORY.to_owned()
    } else {
        format!("{PRODUCT_DIRECTORY}{CHANNEL_SEPARATOR}{channel}")
    }
}

fn windows_rule() -> &'static InstalledDefault {
    INSTALLED_DEFAULTS
        .iter()
        .find(|rule| rule.platform == "windows")
        .expect("the contract declares a Windows installed default")
}

fn nonblank(lookup: &dyn Fn(&str) -> Option<String>, name: &str) -> Option<String> {
    lookup(name)
        .map(|value| value.trim().to_owned())
        .filter(|value| !value.is_empty())
}

/// Expand a leading `~` (the current user only) against the platform home variable.
fn expand_home(value: &str, lookup: &dyn Fn(&str) -> Option<String>) -> Result<PathBuf, Refusal> {
    let normalized = value.replace('\\', "/");
    let (head, tail) = normalized.split_once('/').unwrap_or((&normalized, ""));
    if head != "~" {
        return Ok(PathBuf::from(value));
    }
    let home_variable = windows_rule().home_variable;
    match nonblank(lookup, home_variable).map(PathBuf::from) {
        Some(home) if home.is_absolute() => Ok(home.join(relative_components(tail))),
        _ => Err(refusal(
            "home_unavailable",
            format!("{ROOT_VARIABLE} starts with '~' but {home_variable} is not an absolute path."),
        )),
    }
}

/// The contract's root algorithm on explicit inputs; the Windows mirror of the Python resolver.
///
/// `known_folder` replaces the environment base the Python resolver reads, because
/// the native host asks the shell for `FOLDERID_LocalAppData` directly.
fn resolve_root(
    mode: Mode,
    lookup: &dyn Fn(&str) -> Option<String>,
    checkout: Option<&Path>,
    known_folder: Option<&Path>,
    channel: &str,
) -> Result<PathBuf, Refusal> {
    let checkout_anchor = || {
        checkout.map(Path::to_path_buf).ok_or_else(|| {
            refusal(
                "checkout_unavailable",
                "A development storage root needs the source checkout that anchors it.".into(),
            )
        })
    };
    let precedence = match mode {
        Mode::Development => DEVELOPMENT_ROOT_PRECEDENCE,
        Mode::Installed => INSTALLED_ROOT_PRECEDENCE,
    };
    if let Some(raw) = precedence.iter().find_map(|name| nonblank(lookup, name)) {
        let candidate = expand_home(&raw, lookup)?;
        if candidate.is_absolute() {
            return Ok(candidate);
        }
        let rule = match mode {
            Mode::Development => DEVELOPMENT_RELATIVE_OVERRIDE,
            Mode::Installed => INSTALLED_RELATIVE_OVERRIDE,
        };
        if rule != "anchor_at_checkout" {
            return Err(refusal(
                "relative_override_installed",
                format!("{ROOT_VARIABLE} must be an absolute directory when CADRUMO is installed."),
            ));
        }
        return Ok(checkout_anchor()?.join(candidate));
    }
    if mode == Mode::Development {
        return Ok(checkout_anchor()?.join(relative_components(DEVELOPMENT_DEFAULT)));
    }
    match known_folder {
        Some(base) if base.is_absolute() => {
            let subpath: PathBuf = windows_rule().candidates[0].subpath.iter().collect();
            Ok(base.join(subpath).join(channel_directory(channel)))
        }
        _ => Err(refusal(
            "installed_base_unavailable",
            format!(
                "CADRUMO cannot locate the per-user local application data folder. \
                 Set {ROOT_VARIABLE} to an absolute directory."
            ),
        )),
    }
}

#[repr(C)]
struct Guid {
    data1: u32,
    data2: u16,
    data3: u16,
    data4: [u8; 8],
}
/// FOLDERID_LocalAppData, {F1B32785-6FBA-4FCF-9D55-7B8E7F157091}.
const FOLDERID_LOCAL_APP_DATA: Guid = Guid {
    data1: 0xF1B3_2785,
    data2: 0x6FBA,
    data3: 0x4FCF,
    data4: [0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91],
};
#[link(name = "shell32")]
unsafe extern "system" {
    fn SHGetKnownFolderPath(
        id: *const Guid,
        flags: u32,
        token: *mut c_void,
        path: *mut *mut u16,
    ) -> i32;
}
#[link(name = "ole32")]
unsafe extern "system" {
    fn CoTaskMemFree(memory: *mut c_void);
}

/// The current user's local application data folder from the shell, never the environment.
fn local_app_data() -> Option<PathBuf> {
    let mut raw: *mut u16 = ptr::null_mut();
    let status =
        unsafe { SHGetKnownFolderPath(&FOLDERID_LOCAL_APP_DATA, 0, ptr::null_mut(), &mut raw) };
    let folder = if status >= 0 && !raw.is_null() {
        let length = (0..)
            .take_while(|&index| unsafe { *raw.add(index) } != 0)
            .count();
        let wide = unsafe { std::slice::from_raw_parts(raw, length) };
        Some(PathBuf::from(OsString::from_wide(wide)))
    } else {
        None
    };
    // The shell allocates the string even on some failures; freeing null is a no-op.
    unsafe { CoTaskMemFree(raw.cast()) };
    folder
}

fn environment_value(name: &str) -> Option<String> {
    env::var(name).ok()
}

fn refined_storage_path(name: &str, root: &Path, default: &Path) -> PathBuf {
    match nonblank(&environment_value, name).map(PathBuf::from) {
        Some(path) if path.is_absolute() => path,
        Some(path) => root.join(path),
        None => default.to_path_buf(),
    }
}

fn context() -> Result<Context, String> {
    let exe = env::current_exe().map_err(|e| e.to_string())?;
    let evidence = detect_mode(&exe)?;
    let known_folder = match evidence.mode {
        Mode::Installed => local_app_data(),
        Mode::Development => None,
    };
    let user = resolve_root(
        evidence.mode,
        &environment_value,
        evidence.checkout.as_deref(),
        known_folder.as_deref(),
        BUILD_CHANNEL,
    )
    .map_err(|refused| refused.message)?;
    let temporary = refined_storage_path(TEMPORARY_ENV, &user, &user.join(TEMPORARY_DEFAULT));
    let package = evidence.package;
    let paths = vec![
        package.clone(),
        user.clone(),
        exe,
        package.join(STDLIB),
        package.join(PACKAGES),
        package.join(NATIVE),
        package.join(AUTHORITY),
        user,
        temporary,
    ];
    Ok(Context { paths })
}
fn refuse_links(path: &Path) -> Result<(), String> {
    for ancestor in path.ancestors() {
        match fs::symlink_metadata(ancestor) {
            Ok(meta) if meta.file_attributes() & 0x400 != 0 => {
                return Err(format!(
                    "Reparse point is not permitted: {}",
                    ancestor.display()
                ));
            }
            Ok(_) => {}
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.to_string()),
        }
    }
    Ok(())
}

/// Names the contract clears from a packaged process, keeping the product and package allowlists.
fn cleared(name: &str) -> bool {
    let upper = name.to_ascii_uppercase();
    let allowed = PRODUCT_ENV_ALLOWLIST.contains(&upper.as_str())
        || PACKAGE_ENV_ALLOWLIST.contains(&upper.as_str());
    CLEARED_PREFIXES
        .iter()
        .any(|prefix| upper.starts_with(prefix))
        || CLEARED_NAMES.contains(&upper.as_str())
        || ((upper.starts_with(NAMESPACE_PREFIX) || RESERVED_ENV.contains(&upper.as_str()))
            && !allowed)
}

/// The contract's pinned set plus the host-inherited authority pin, from resolved paths.
fn pinned(ctx: &Context) -> Vec<(&'static str, &Path)> {
    let mut values: Vec<(&'static str, &Path)> = PINNED_ENV
        .iter()
        .map(|&name| {
            let value = if name == ROOT_VARIABLE {
                &ctx.paths[7]
            } else {
                &ctx.paths[8]
            };
            (name, value.as_path())
        })
        .collect();
    values.extend(
        HOST_INHERITED_ENV
            .iter()
            .map(|&name| (name, ctx.paths[6].as_path())),
    );
    values
}

fn prepare(ctx: &Context) -> Result<(), String> {
    for path in [&ctx.paths[1], &ctx.paths[8]] {
        refuse_links(path)?;
        fs::create_dir_all(path).map_err(|e| e.to_string())?;
        refuse_links(path)?;
    }
    // Environment mutation occurs once, before Python or application threads exist.
    let names: Vec<_> = env::vars_os().map(|(key, _)| key).collect();
    for name in names {
        if cleared(&name.to_string_lossy()) {
            unsafe {
                env::remove_var(name);
            }
        }
    }
    unsafe {
        for (name, value) in pinned(ctx) {
            env::set_var(name, value);
        }
        let system = env::var_os("SystemRoot").ok_or("SystemRoot is missing")?;
        let mut search = vec![ctx.paths[0].clone()];
        if let Some(overrides) = env::var_os("CADRUMO_EXTERNAL_BIN_DIRS") {
            for directory in env::split_paths(&overrides) {
                if !directory.is_absolute() || !directory.is_dir() {
                    return Err(
                        "CADRUMO_EXTERNAL_BIN_DIRS requires existing absolute directories".into(),
                    );
                }
                search.push(directory);
            }
        }
        search.push(ctx.paths[5].clone());
        search.push(PathBuf::from(system).join("System32"));
        let path = env::join_paths(search).map_err(|e| e.to_string())?;
        env::set_var("PATH", path);
    }
    Ok(())
}

#[unsafe(no_mangle)]
pub extern "C" fn cadrumo_platform_abi() -> u32 {
    ABI
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_create(
    abi: u32,
    out: *mut *mut Context,
    error: *mut Buffer,
) -> u32 {
    if out.is_null() || error.is_null() {
        return 2;
    }
    unsafe {
        *out = ptr::null_mut();
        *error = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    if abi != ABI {
        unsafe {
            *error = buffer("Incompatible platform ABI".into());
        }
        return 1;
    }
    match context() {
        Ok(ctx) => {
            unsafe {
                *out = Box::into_raw(Box::new(ctx));
            }
            0
        }
        Err(e) => {
            unsafe {
                *error = buffer(e);
            }
            3
        }
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_path(
    ctx: *mut Context,
    key: u32,
    out: *mut Buffer,
) -> u32 {
    if ctx.is_null() || out.is_null() {
        return 2;
    }
    unsafe {
        *out = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    match unsafe { &*ctx }.paths.get(key as usize) {
        Some(path) => match path.to_str() {
            Some(s) => {
                unsafe {
                    *out = buffer(s.into());
                }
                0
            }
            None => 3,
        },
        None => 2,
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_prepare(ctx: *mut Context, error: *mut Buffer) -> u32 {
    if ctx.is_null() || error.is_null() {
        return 2;
    }
    unsafe {
        *error = Buffer {
            data: ptr::null_mut(),
            len: 0,
        };
    }
    match prepare(unsafe { &*ctx }) {
        Ok(()) => 0,
        Err(e) => {
            unsafe {
                *error = buffer(e);
            }
            3
        }
    }
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_release(b: *mut Buffer) {
    if b.is_null() {
        return;
    }
    let b = unsafe { &mut *b };
    if !b.data.is_null() {
        unsafe {
            drop(Box::from_raw(ptr::slice_from_raw_parts_mut(
                b.data,
                b.len as usize,
            )));
        }
    }
    b.data = ptr::null_mut();
    b.len = 0;
}
#[unsafe(no_mangle)]
pub unsafe extern "C" fn cadrumo_platform_destroy(ctx: *mut Context) {
    if !ctx.is_null() {
        unsafe {
            drop(Box::from_raw(ctx));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Scratch(PathBuf);
    impl Scratch {
        fn new(label: &str) -> Self {
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = env::temp_dir().join(format!(
                "cadrumo-platform-{label}-{}-{nanos}",
                std::process::id()
            ));
            fs::create_dir_all(&path).unwrap();
            Scratch(path)
        }
    }
    impl Drop for Scratch {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn same_path(actual: &Path, expected: &str) -> bool {
        actual.components().eq(Path::new(expected).components())
    }

    #[test]
    fn package_root_maps_declared_entrypoints_from_the_native_directory() {
        let package = Path::new(r"C:\Program Files\CADRUMO\app");
        let interpreter = package.join(EXECUTABLE);
        assert_eq!(package_root(&interpreter).unwrap(), package);
        for file in ENTRYPOINT_FILES {
            let entrypoint = package.join(NATIVE).join(file);
            assert_eq!(package_root(&entrypoint).unwrap(), package);
            let uppercase = package
                .join(NATIVE.to_uppercase())
                .join(file.to_uppercase());
            assert_eq!(package_root(&uppercase).unwrap(), package);
        }
    }

    #[test]
    fn package_root_refuses_a_declared_entrypoint_outside_the_native_directory() {
        assert!(!ENTRYPOINT_FILES.is_empty());
        let package = Path::new(r"C:\Program Files\CADRUMO\app");
        for file in ENTRYPOINT_FILES {
            assert!(package_root(&package.join(file)).is_err());
            assert!(package_root(&package.join("data").join(file)).is_err());
        }
        let undeclared = package.join(NATIVE).join("other.exe");
        assert_eq!(package_root(&undeclared).unwrap(), package.join(NATIVE));
    }

    #[test]
    fn resolver_reproduces_every_windows_contract_vector() {
        let windows: Vec<_> = STORAGE_ROOT_VECTORS
            .iter()
            .filter(|vector| vector.platform == "windows")
            .collect();
        assert!(
            windows.len() >= 10,
            "the contract carries the Windows vectors"
        );
        for vector in windows {
            let lookup = |name: &str| {
                vector
                    .environment
                    .iter()
                    .find(|(key, _)| *key == name)
                    .map(|(_, value)| (*value).to_owned())
            };
            let mode = match vector.mode {
                "development" => Mode::Development,
                "installed" => Mode::Installed,
                other => panic!("undeclared mode {other}"),
            };
            let outcome = resolve_root(
                mode,
                &lookup,
                vector.checkout.map(Path::new),
                vector.known_folder.map(Path::new),
                vector.channel,
            );
            match (outcome, vector.expected_root, vector.refusal) {
                (Ok(root), Some(expected), None) => assert!(
                    same_path(&root, expected),
                    "{}: resolved {} expected {expected}",
                    vector.name,
                    root.display()
                ),
                (Err(refused), None, Some(code)) => {
                    assert_eq!(refused.code, code, "{}", vector.name)
                }
                (outcome, expected, code) => panic!(
                    "{}: got {outcome:?}, expected root {expected:?} refusal {code:?}",
                    vector.name
                ),
            }
        }
    }

    #[test]
    fn known_folder_default_matches_the_shell_local_application_data() {
        let folder = local_app_data().expect("the shell reports FOLDERID_LocalAppData");
        assert!(folder.is_absolute());
        if let Some(local) = env::var_os("LOCALAPPDATA") {
            assert_eq!(folder, PathBuf::from(local));
        }
        let none = |_: &str| None;
        let root =
            resolve_root(Mode::Installed, &none, None, Some(&folder), BUILD_CHANNEL).unwrap();
        assert_eq!(root, folder.join(channel_directory(BUILD_CHANNEL)));
    }

    #[test]
    fn mode_comes_from_package_or_checkout_evidence_never_the_working_directory() {
        let installed = Scratch::new("installed");
        let manifest = installed.0.join(relative_components(MODE_PACKAGE_MANIFEST));
        fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        fs::write(&manifest, b"{}").unwrap();
        let checkout = Scratch::new("checkout");
        fs::write(checkout.0.join(MODE_CHECKOUT_MARKER), b"[project]\n").unwrap();
        let unrelated = Scratch::new("unrelated");
        // A checkout marker in the working directory must not make anything a development build.
        fs::write(unrelated.0.join(MODE_CHECKOUT_MARKER), b"[project]\n").unwrap();
        let previous = env::current_dir().unwrap();
        env::set_current_dir(&unrelated.0).unwrap();

        let packaged = detect_mode(&installed.0.join(EXECUTABLE));
        let entrypoint = ENTRYPOINT_FILES[0];
        let packaged_entrypoint = detect_mode(&installed.0.join(NATIVE).join(entrypoint));
        let built = detect_mode(&checkout.0.join("build").join("bin").join(EXECUTABLE));
        // Mode detection only probes for files, so an absent directory at the drive root
        // stands outside every checkout even when the test runner's TEMP is inside one.
        let drive: PathBuf = env::temp_dir().components().take(2).collect();
        let orphan = drive.join(format!("cadrumo-platform-orphan-{}", std::process::id()));
        assert!(!orphan.exists() && !drive.join(MODE_CHECKOUT_MARKER).exists());
        let refused = detect_mode(&orphan.join(EXECUTABLE));
        env::set_current_dir(previous).unwrap();

        assert_eq!(
            packaged.unwrap(),
            Evidence {
                mode: Mode::Installed,
                package: installed.0.clone(),
                checkout: None,
            }
        );
        assert_eq!(packaged_entrypoint.unwrap().package, installed.0);
        let development = built.unwrap();
        assert_eq!(development.mode, Mode::Development);
        assert_eq!(development.checkout.as_deref(), Some(checkout.0.as_path()));
        assert!(refused.unwrap_err().contains(MODE_CHECKOUT_MARKER));
    }

    #[test]
    fn packaged_environment_pins_root_temporary_and_authority_and_clears_tool_and_cache_names() {
        let ctx = Context {
            paths: vec![
                PathBuf::from(r"C:\app"),
                PathBuf::from(r"C:\data"),
                PathBuf::from(r"C:\app\python.exe"),
                PathBuf::from(r"C:\app\python.zip"),
                PathBuf::from(r"C:\app\site"),
                PathBuf::from(r"C:\app\bin"),
                PathBuf::from(r"C:\app\data\authority"),
                PathBuf::from(r"C:\data"),
                PathBuf::from(r"C:\data\tmp"),
            ],
        };
        let set: Vec<_> = pinned(&ctx).into_iter().map(|(name, _)| name).collect();
        let mut expected: Vec<&str> = PINNED_ENV.to_vec();
        expected.extend(HOST_INHERITED_ENV);
        assert_eq!(set, expected);
        assert_eq!(set[0], ROOT_VARIABLE);
        assert!(!set.contains(&"XDG_CACHE_HOME"));
        assert!(
            pinned(&ctx)
                .iter()
                .any(|(name, value)| *name == ROOT_VARIABLE && *value == Path::new(r"C:\data"))
        );
        assert!(cleared("PYTHONPATH") && cleared("VIRTUAL_ENV"));
        assert!(cleared(&format!("{NAMESPACE_PREFIX}SECRET_PASSPHRASE")));
        assert!(!cleared(ROOT_VARIABLE));
        assert!(!cleared("SYSTEMROOT"));
        assert!(PRODUCT_ENV_ALLOWLIST.iter().all(|name| !cleared(name)));
    }
}
