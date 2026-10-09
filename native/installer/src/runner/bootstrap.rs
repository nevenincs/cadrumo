//! Desktop provisioning reuses the authenticated native transaction owner.
#![allow(unsafe_code)]

use super::{Artifact, Plan, artifact};
use crate::{admission::Scope, custody::FileCustody};
use cadrumo_application::{
    installation::{DiscoveryContract, Selection},
    package::{PackageManifest, Readiness},
    value::{RelativePath, Sha256Digest},
};
use serde::Deserialize;
use std::{
    collections::BTreeMap,
    fs,
    io::{Read, Write},
    os::windows::{
        ffi::OsStrExt,
        io::{AsRawHandle, FromRawHandle, OwnedHandle},
        process::CommandExt,
    },
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    time::{SystemTime, UNIX_EPOCH},
};
use windows::{
    Win32::{
        System::Com::CoTaskMemFree,
        UI::Shell::{
            FOLDERID_LocalAppData, FOLDERID_ProgramFiles, KF_FLAG_DEFAULT, SEE_MASK_NOASYNC,
            SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW, SHGetKnownFolderPath, ShellExecuteExW,
        },
    },
    core::PCWSTR,
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Failure {
    KitUnavailable,
    KitRefused,
    Cancelled,
    NativeFailed,
    PublicationUnconfirmed,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Source {
    path: RelativePath,
    sha256: Sha256Digest,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Product {
    path: RelativePath,
    sha256: Sha256Digest,
    product_code: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Template {
    version: String,
    manifest_sha256: Sha256Digest,
    desktop_present: bool,
    contract: serde_json::Value,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Kit {
    schema: u32,
    runner: Source,
    maintenance: Template,
    artifacts: BTreeMap<String, Product>,
}

fn read_kit(path: &Path) -> Result<(Kit, FileCustody), Failure> {
    let mut custody = crate::custody::file(path).map_err(|_| Failure::KitUnavailable)?;
    let mut bytes = Vec::new();
    Read::by_ref(&mut custody.file)
        .take(super::PLAN_LIMIT + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| Failure::KitUnavailable)?;
    if bytes.len() as u64 > super::PLAN_LIMIT {
        return Err(Failure::KitRefused);
    }
    let kit: Kit = serde_json::from_slice(&bytes).map_err(|_| Failure::KitRefused)?;
    if kit.schema != 1
        || kit.artifacts.len() != 4
        || !kit.maintenance.desktop_present
        || [
            "user-version",
            "user-registration",
            "machine-version",
            "machine-registration",
        ]
        .iter()
        .any(|name| !kit.artifacts.contains_key(*name))
    {
        return Err(Failure::KitRefused);
    }
    Ok((kit, custody))
}

fn prefix(contract: &DiscoveryContract, scope: Scope) -> Result<PathBuf, Failure> {
    let name = &contract.installation_identity.application_id;
    let member = RelativePath::new(name.clone()).map_err(|_| Failure::KitRefused)?;
    if member.as_str().contains('/') {
        return Err(Failure::KitRefused);
    }
    let folder = match scope {
        Scope::User => &FOLDERID_LocalAppData,
        Scope::Machine => &FOLDERID_ProgramFiles,
    };
    // SAFETY: The shell returns a task-allocated, terminated UTF-16 path.
    let raw = unsafe { SHGetKnownFolderPath(folder, KF_FLAG_DEFAULT, None) }
        .map_err(|_| Failure::NativeFailed)?;
    // SAFETY: A successful shell call owns this string until CoTaskMemFree.
    let base = unsafe { raw.to_string() }.map(PathBuf::from);
    // SAFETY: Release the allocation even if decoding failed.
    unsafe { CoTaskMemFree(Some(raw.0.cast())) };
    let base = base.map_err(|_| Failure::NativeFailed)?;
    let base = if scope == Scope::User {
        base.join("Programs")
    } else {
        base
    };
    Ok(member.under(&base))
}

fn prepare_plan(
    kit: Kit,
    directory: &Path,
    package: &Path,
    expected: &DiscoveryContract,
    scope: Scope,
    prefix: PathBuf,
) -> Result<(Plan, PathBuf, FileCustody), Failure> {
    let contract: DiscoveryContract = serde_json::from_value(kit.maintenance.contract.clone())
        .map_err(|_| Failure::KitRefused)?;
    if serde_json::to_value(&contract).map_err(|_| Failure::KitRefused)?
        != serde_json::to_value(expected).map_err(|_| Failure::KitRefused)?
    {
        return Err(Failure::KitRefused);
    }
    super::version(&kit.maintenance.version).map_err(|_| Failure::KitRefused)?;
    let mut manifest = crate::custody::file(&expected.layout.files.package_manifest.under(package))
        .map_err(|_| Failure::KitRefused)?;
    let actual =
        crate::registration::file_digest(&mut manifest.file).map_err(|_| Failure::KitRefused)?;
    if actual != kit.maintenance.manifest_sha256 {
        return Err(Failure::KitRefused);
    }
    let active: serde_json::Value = serde_json::from_slice(
        &fs::read(expected.layout.files.package_manifest.under(package))
            .map_err(|_| Failure::KitRefused)?,
    )
    .map_err(|_| Failure::KitRefused)?;
    if active["build"]["version"].as_str() != Some(kit.maintenance.version.as_str())
        || active["build"]["application_id"].as_str()
            != Some(expected.installation_identity.application_id.as_str())
        || active["build"]["channel"].as_str()
            != Some(expected.installation_identity.channel.as_str())
    {
        return Err(Failure::KitRefused);
    }
    let inspected = PackageManifest::read(package, &expected.layout.files.package_manifest)
        .and_then(|value| {
            value.inspect(
                package,
                &expected.layout.files.package_manifest,
                &expected.layout.platform,
                expected.layout.abi,
            )
        })
        .map_err(|_| Failure::KitRefused)?;
    if inspected.readiness != Readiness::Ready {
        return Err(Failure::KitRefused);
    }
    let runner = kit.runner.path.under(directory);
    let mut custody = crate::custody::file(&runner).map_err(|_| Failure::KitRefused)?;
    let digest =
        crate::registration::file_digest(&mut custody.file).map_err(|_| Failure::KitRefused)?;
    if digest != kit.runner.sha256 {
        return Err(Failure::KitRefused);
    }
    cadrumo_application::binary::verify(
        &runner,
        &digest,
        cadrumo_application::binary::BinaryExpectation::host().map_err(|_| Failure::KitRefused)?,
    )
    .map_err(|_| Failure::KitRefused)?;
    let name = if scope == Scope::User {
        "user"
    } else {
        "machine"
    };
    let product = |role: &str| -> Result<Artifact, Failure> {
        let value = kit
            .artifacts
            .get(&format!("{name}-{role}"))
            .ok_or(Failure::KitRefused)?;
        Ok(Artifact {
            path: value.path.under(directory),
            sha256: value.sha256.clone(),
            product_code: value.product_code.clone(),
        })
    };
    let plan = Plan {
        schema: 1,
        scope,
        prefix,
        version: kit.maintenance.version,
        manifest_sha256: actual,
        desktop_present: true,
        contract,
        version_product: product("version")?,
        registration_product: product("registration")?,
    };
    Ok((plan, runner, custody))
}

/// Holds every admitted artifact until native maintenance and rediscovery settle.
/// The caller runs this on an owned blocking worker, never on the GUI thread.
pub fn install<G>(
    package: &Path,
    contract: &DiscoveryContract,
    scope: Scope,
    temporary: &Path,
    authorize_launch: impl FnOnce() -> Result<G, Failure>,
) -> Result<Selection, Failure> {
    require_host()?;
    let bootstrap = contract
        .layout
        .installation
        .bootstrap
        .as_ref()
        .ok_or(Failure::KitUnavailable)?;
    let parent = package.parent().ok_or(Failure::KitUnavailable)?;
    let directory = bootstrap.directory.under(parent);
    let (kit, _kit_custody) = read_kit(&bootstrap.manifest.under(&directory))?;
    let (plan, runner, _runner_custody) = prepare_plan(
        kit,
        &directory,
        package,
        contract,
        scope,
        prefix(contract, scope)?,
    )?;
    let runner_digest = {
        let mut source = crate::custody::file(&runner).map_err(|_| Failure::KitRefused)?;
        crate::registration::file_digest(&mut source.file).map_err(|_| Failure::KitRefused)?
    };
    let (admission, _version_custody) =
        artifact(&plan.version_product, &plan, "version", &runner_digest)
            .map_err(|_| Failure::KitRefused)?;
    let (registration, _registration_custody) = artifact(
        &plan.registration_product,
        &plan,
        "registration",
        &runner_digest,
    )
    .map_err(|_| Failure::KitRefused)?;
    if admission.permitted_families != registration.permitted_families
        || admission.conflicting_families != registration.conflicting_families
        || plan.version_product.product_code == plan.registration_product.product_code
    {
        return Err(Failure::KitRefused);
    }
    if crate::windows::standalone_gate_present(&plan.version_product.path).unwrap_or(true)
        || crate::windows::standalone_gate_present(&plan.registration_product.path).unwrap_or(true)
    {
        return Err(Failure::KitRefused);
    }
    let request = TemporaryPlan::new(&plan, temporary)?;
    let _request_custody = crate::custody::file(&request.path).map_err(|_| Failure::KitRefused)?;
    // The caller's close fence is held only through process creation. An active
    // native transaction must settle, even after its GUI caller closes.
    let permission = authorize_launch()?;
    let process = launch(&runner, &request.path, scope)?;
    drop(permission);
    let exit = process
        .wait()
        .map_err(|_| Failure::PublicationUnconfirmed)?;
    if exit != 0 {
        // The native owner may report a committed-but-pending publication.
        // A nonzero exit cannot establish that nothing was installed.
        return Err(Failure::PublicationUnconfirmed);
    }
    // Process exit is not publication. Catalogue admission retains the version lease.
    let selection = contract
        .inspect(&plan.prefix)
        .map_err(|_| Failure::PublicationUnconfirmed)?;
    if selection.version != super::version(&plan.version).map_err(|_| Failure::KitRefused)?
        || selection.registration.as_ref().is_none_or(|owner| {
            !matches!(
                (scope, owner.context()),
                (
                    Scope::Machine,
                    cadrumo_application::installation::maintenance::NativeContext::Machine
                ) | (
                    Scope::User,
                    cadrumo_application::installation::maintenance::NativeContext::User { .. }
                )
            )
        })
    {
        return Err(Failure::PublicationUnconfirmed);
    }
    Ok(selection)
}

fn require_host() -> Result<(), Failure> {
    use windows_sys::Win32::{
        Security::{GetTokenInformation, TOKEN_QUERY, TokenElevationType, TokenElevationTypeFull},
        System::{
            RemoteDesktop::ProcessIdToSessionId,
            Threading::{GetCurrentProcess, OpenProcessToken},
        },
    };
    let mut session = 0;
    // SAFETY: The current PID and writable session output are valid.
    if unsafe { ProcessIdToSessionId(std::process::id(), &mut session) } == 0 || session == 0 {
        return Err(Failure::KitRefused);
    }
    let mut raw = std::ptr::null_mut();
    // SAFETY: Query-only access to our own process token.
    if unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut raw) } == 0 {
        return Err(Failure::KitRefused);
    }
    // SAFETY: A successful token open transfers ownership.
    let token = unsafe { OwnedHandle::from_raw_handle(raw) };
    let mut elevation: i32 = 0;
    let mut size = 0;
    // SAFETY: Exact TOKEN_ELEVATION_TYPE output and owned query token.
    if unsafe {
        GetTokenInformation(
            token.as_raw_handle(),
            TokenElevationType,
            std::ptr::from_mut(&mut elevation).cast(),
            std::mem::size_of::<i32>() as u32,
            &mut size,
        )
    } == 0
        || elevation == TokenElevationTypeFull
    {
        return Err(Failure::KitRefused);
    }
    Ok(())
}

struct TemporaryPlan {
    directory: PathBuf,
    path: PathBuf,
}
impl TemporaryPlan {
    fn new(plan: &Plan, temporary: &Path) -> Result<Self, Failure> {
        if !temporary.is_absolute() || !temporary.is_dir() {
            return Err(Failure::NativeFailed);
        }
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| Failure::NativeFailed)?
            .as_nanos();
        let directory = temporary.join(format!("services-install-{}-{stamp}", std::process::id()));
        fs::create_dir(&directory).map_err(|_| Failure::NativeFailed)?;
        let value = Self {
            path: directory.join("plan.json"),
            directory,
        };
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&value.path)
            .map_err(|_| Failure::NativeFailed)?;
        file.write_all(&serde_json::to_vec(plan).map_err(|_| Failure::KitRefused)?)
            .and_then(|_| file.sync_all())
            .map_err(|_| Failure::NativeFailed)?;
        drop(file);
        // Re-enter the owning parser before passing the request across elevation.
        super::read_plan(&value.path).map_err(|_| Failure::KitRefused)?;
        Ok(value)
    }
}
impl Drop for TemporaryPlan {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
        let _ = fs::remove_dir(&self.directory);
    }
}

enum NativeProcess {
    User(Child),
    Machine(OwnedHandle),
}

impl NativeProcess {
    fn wait(self) -> Result<u32, Failure> {
        let Self::Machine(process) = self else {
            let Self::User(mut child) = self else {
                unreachable!()
            };
            return child
                .wait()
                .map_err(|_| Failure::NativeFailed)?
                .code()
                .and_then(|code| u32::try_from(code).ok())
                .ok_or(Failure::NativeFailed);
        };
        let handle = process.as_raw_handle();
        // SAFETY: Retain the handle and all source custody until native settlement.
        if unsafe { windows_sys::Win32::System::Threading::WaitForSingleObject(handle, u32::MAX) }
            != 0
        {
            return Err(Failure::NativeFailed);
        }
        let mut exit = 0;
        // SAFETY: The settled process handle and writable DWORD are valid.
        if unsafe { windows_sys::Win32::System::Threading::GetExitCodeProcess(handle, &mut exit) }
            == 0
        {
            return Err(Failure::NativeFailed);
        }
        Ok(exit)
    }
}

fn launch(runner: &Path, plan: &Path, scope: Scope) -> Result<NativeProcess, Failure> {
    if scope == Scope::User {
        let child = Command::new(runner)
            .args([
                std::ffi::OsStr::new("install"),
                std::ffi::OsStr::new("--plan"),
                plan.as_os_str(),
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x0800_0000)
            .spawn()
            .map_err(|_| Failure::NativeFailed)?;
        return Ok(NativeProcess::User(child));
    }
    let executable: Vec<u16> = runner.as_os_str().encode_wide().chain([0]).collect();
    let path = plan.to_str().ok_or(Failure::KitRefused)?;
    if path.contains(['"', '\r', '\n']) {
        return Err(Failure::KitRefused);
    }
    let parameters: Vec<u16> = format!("install --plan \"{path}\"")
        .encode_utf16()
        .chain([0])
        .collect();
    let verb: Vec<u16> = "runas".encode_utf16().chain([0]).collect();
    let mut request = SHELLEXECUTEINFOW {
        cbSize: std::mem::size_of::<SHELLEXECUTEINFOW>() as u32,
        fMask: SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC,
        lpVerb: PCWSTR(verb.as_ptr()),
        lpFile: PCWSTR(executable.as_ptr()),
        lpParameters: PCWSTR(parameters.as_ptr()),
        nShow: 0,
        ..Default::default()
    };
    // SAFETY: All strings stay alive through the synchronous shell call. Only
    // the verified maintenance runner is elevated; no product process is.
    if let Err(error) = unsafe { ShellExecuteExW(&mut request) } {
        return Err(if error.code().0 as u32 == 0x800704c7 {
            Failure::Cancelled
        } else {
            Failure::NativeFailed
        });
    }
    if request.hProcess.is_invalid() {
        return Err(Failure::NativeFailed);
    }
    // SAFETY: SEE_MASK_NOCLOSEPROCESS transfers this process handle to us.
    Ok(NativeProcess::Machine(unsafe {
        OwnedHandle::from_raw_handle(request.hProcess.0)
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn descriptor() -> serde_json::Value {
        let product = json!({"path":"product.msi", "sha256":"a".repeat(64),
            "product_code":"10000000-0000-4000-8000-000000000000"});
        json!({"schema":1, "runner":{"path":"installer.exe","sha256":"b".repeat(64)},
            "maintenance":{"version":"1.0.0", "manifest_sha256":"c".repeat(64),
                "desktop_present":true, "contract":{}},
            "artifacts":{"user-version":product,"user-registration":product,
                "machine-version":product,"machine-registration":product}})
    }

    #[test]
    #[ignore = "requires a real assembled desktop package and compiled native MSI kit"]
    fn assembled_kit_admits_both_scopes_and_refuses_wrong_native_role_without_installing() {
        let package = PathBuf::from(std::env::var_os("CADRUMO_BOOTSTRAP_TEST_PACKAGE").unwrap());
        let contract: DiscoveryContract = serde_json::from_slice(
            &fs::read(std::env::var_os("CADRUMO_NATIVE_CONTRACT").unwrap()).unwrap(),
        )
        .unwrap();
        let bootstrap = contract.layout.installation.bootstrap.as_ref().unwrap();
        let directory = bootstrap.directory.under(package.parent().unwrap());
        let root = tempfile::tempdir().unwrap();
        for scope in [Scope::User, Scope::Machine] {
            let (kit, _custody) = read_kit(&bootstrap.manifest.under(&directory)).unwrap();
            let (plan, runner_path, _runner_custody) = prepare_plan(
                kit,
                &directory,
                &package,
                &contract,
                scope,
                root.path().join("unused-install-prefix"),
            )
            .unwrap();
            let mut runner = crate::custody::file(&runner_path).unwrap();
            let digest = crate::registration::file_digest(&mut runner.file).unwrap();
            let (version, _version_custody) =
                artifact(&plan.version_product, &plan, "version", &digest).unwrap();
            let (registration, _registration_custody) =
                artifact(&plan.registration_product, &plan, "registration", &digest).unwrap();
            assert_eq!(version.permitted_families, registration.permitted_families);
            assert!(!crate::windows::standalone_gate_present(&plan.version_product.path).unwrap());
            assert!(
                !crate::windows::standalone_gate_present(&plan.registration_product.path).unwrap()
            );
            assert!(artifact(&plan.registration_product, &plan, "version", &digest).is_err());
            let changed_runner = Sha256Digest::new("0".repeat(64)).unwrap();
            assert!(artifact(&plan.version_product, &plan, "version", &changed_runner).is_err());
            let request = TemporaryPlan::new(&plan, root.path()).unwrap();
            assert_eq!(super::super::read_plan(&request.path).unwrap().scope, scope);
            let path = request.path.clone();
            drop(request);
            assert!(!path.exists());
        }
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 0);
    }

    #[test]
    fn kit_requires_exact_roles_schema_desktop_and_safe_members() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("kit.json");
        for kind in 0..6 {
            let mut value = descriptor();
            match kind {
                0 => value["schema"] = json!(2),
                1 => value["maintenance"]["desktop_present"] = json!(false),
                2 => {
                    value["artifacts"]
                        .as_object_mut()
                        .unwrap()
                        .remove("machine-version");
                }
                3 => value["extra"] = json!(true),
                4 => value["runner"]["path"] = json!("../installer.exe"),
                _ => value["artifacts"]["user-version"]["path"] = json!("C:/other.msi"),
            }
            fs::write(&path, serde_json::to_vec(&value).unwrap()).unwrap();
            assert!(matches!(read_kit(&path), Err(Failure::KitRefused)));
        }
    }

    #[test]
    fn kit_custody_blocks_writer_and_replacement_until_admission_settles() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("kit.json");
        fs::write(&path, serde_json::to_vec(&descriptor()).unwrap()).unwrap();
        let (_, custody) = read_kit(&path).unwrap();
        assert!(fs::OpenOptions::new().write(true).open(&path).is_err());
        assert!(fs::remove_file(&path).is_err());
        drop(custody);
        fs::remove_file(&path).unwrap();
    }

    #[test]
    fn missing_or_oversize_kit_refuses_without_launch() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("kit.json");
        assert!(matches!(read_kit(&path), Err(Failure::KitUnavailable)));
        fs::write(&path, vec![b' '; super::super::PLAN_LIMIT as usize + 1]).unwrap();
        assert!(matches!(read_kit(&path), Err(Failure::KitRefused)));
    }

    #[test]
    fn changed_active_contract_refuses_before_reading_or_launching_artifacts() {
        let root = tempfile::tempdir().unwrap();
        let mut definition = json!({
            "installation_identity":{"application_id":"test.application","channel":"stable"},
            "layout":serde_json::from_str::<serde_json::Value>(include_str!("../../../package-layout.json")).unwrap()
        });
        // The source layout carries target-independent defaults; select the host.
        definition["layout"]["platform"] = json!("windows-x64");
        definition["layout"]["application_images"] = json!([]);
        definition["layout"]["entrypoint_suffix"] = json!(".exe");
        let expected: DiscoveryContract = serde_json::from_value(definition.clone()).unwrap();
        definition["installation_identity"]["channel"] = json!("other");
        let mut value = descriptor();
        value["maintenance"]["contract"] = definition;
        let kit = serde_json::from_value(value).unwrap();
        assert!(matches!(
            prepare_plan(
                kit,
                root.path(),
                root.path(),
                &expected,
                Scope::User,
                root.path().join("prefix")
            ),
            Err(Failure::KitRefused)
        ));
    }
}
