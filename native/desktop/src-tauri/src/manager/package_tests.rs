//! Package admission fixtures never dispatch the copied image.
use super::*;
use std::{
    fs,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

// Admission tests use explicit empty registration hints and never depend on a host install.
fn target(package_root: &Path) -> Result<PathBuf> {
    let contract: DiscoveryContract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
    super::target_from(package_root, &contract, &[], &Cancellation::default())
}

struct PackageFixture {
    prefix: PathBuf,
    root: PathBuf,
    image: PathBuf,
    manifest: PathBuf,
    document: serde_json::Value,
    source: PathBuf,
}

impl PackageFixture {
    fn new() -> Self {
        let prefix = std::env::temp_dir().join(format!(
            "cadrumo-manager-package-{}-{} ü space",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let root = prefix.join("versions/0.1.0");
        fs::create_dir_all(&root).unwrap();
        let contract: DiscoveryContract =
            serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
        let member = contract.manager_member().unwrap();
        let image = member.under(&root);
        fs::create_dir_all(image.parent().unwrap()).unwrap();
        let source =
            PathBuf::from(std::env::var_os("SystemRoot").unwrap()).join("System32/where.exe");
        fs::copy(&source, &image).unwrap();
        // A known native OS fixture supplies real PE bytes. It is never executed.
        let mut hash = std::process::Command::new(
            PathBuf::from(std::env::var_os("SystemRoot").unwrap())
                .join("System32/WindowsPowerShell/v1.0/powershell.exe"),
        );
        use std::os::windows::process::CommandExt;
        hash.creation_flags(0x0800_0000);
        let output = hash.args(["-NoProfile", "-NonInteractive", "-Command",
            "[Console]::Out.Write(([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Console]::OpenStandardInput()))).Replace('-','').ToLowerInvariant())"])
            .stdin(fs::File::open(&image).unwrap()).output().unwrap();
        assert!(output.status.success());
        let digest = String::from_utf8(output.stdout).unwrap();
        assert_eq!(digest.len(), 64);
        let manifest = contract.layout.files.package_manifest.under(&root);
        fs::create_dir_all(manifest.parent().unwrap()).unwrap();
        let document = serde_json::json!({
            "layout": {"abi": contract.layout.abi, "platform": contract.layout.platform},
            "build": {"application_id": contract.installation_identity.application_id,
                "channel": contract.installation_identity.channel, "version": "0.1.0", "target": "windows-x86-64"},
            "python": "fixture", "distributions": {}, "files": {(member.as_str()): digest},
            "user_docs": {"directory": "docs/user", "bundled": false}
        });
        fs::write(&manifest, serde_json::to_vec(&document).unwrap()).unwrap();
        fs::create_dir_all(prefix.join("data")).unwrap();
        fs::write(contract.layout.installation.marker.under(&prefix), serde_json::to_vec(&serde_json::json!({
            "schema": contract.layout.installation.schema, "application_id": contract.installation_identity.application_id,
            "channel": contract.installation_identity.channel, "platform": contract.layout.platform, "abi": contract.layout.abi
        })).unwrap()).unwrap();
        fs::copy(&image, member.under(&prefix)).unwrap();
        Self {
            prefix,
            root,
            image,
            manifest,
            document,
            source,
        }
    }

    fn restore(&self) {
        fs::copy(&self.source, &self.image).unwrap();
        fs::write(&self.manifest, serde_json::to_vec(&self.document).unwrap()).unwrap();
    }
}

impl Drop for PackageFixture {
    fn drop(&mut self) {
        assert!(self.prefix.is_absolute());
        assert_eq!(self.prefix.parent(), Some(std::env::temp_dir().as_path()));
        let _ = fs::remove_dir_all(&self.prefix);
    }
}

#[test]
fn relocated_package_with_spaces_and_unicode_is_verified_without_cwd_assumptions() {
    let mut fixture = PackageFixture::new();
    let member = fixture.image.file_name().unwrap().to_owned();
    assert_eq!(target(&fixture.root).unwrap(), fixture.prefix.join(&member));
    let moved = fixture.prefix.with_file_name(format!(
        "{} moved",
        fixture.prefix.file_name().unwrap().to_str().unwrap()
    ));
    assert_eq!(moved.parent(), fixture.prefix.parent());
    fs::rename(&fixture.prefix, &moved).unwrap();
    let relative = fixture
        .root
        .strip_prefix(&fixture.prefix)
        .unwrap()
        .to_owned();
    fixture.prefix = moved;
    fixture.root = fixture.prefix.join(relative);
    assert_eq!(target(&fixture.root).unwrap(), fixture.prefix.join(member));
}

#[test]
fn package_admission_rechecks_damage_missing_members_and_repaired_bytes() {
    let fixture = PackageFixture::new();
    assert!(target(&fixture.root).is_ok());
    fs::write(&fixture.image, b"foreign damaged image").unwrap();
    assert_eq!(
        target(&fixture.root).unwrap_err().code,
        ErrorCode::PackageUnavailable
    );
    fixture.restore();
    assert!(target(&fixture.root).is_ok());
    fs::remove_file(&fixture.image).unwrap();
    assert!(target(&fixture.root).is_err());
    fixture.restore();
    fs::write(&fixture.manifest, b"{incomplete").unwrap();
    assert!(target(&fixture.root).is_err());
    fixture.restore();
    let mut wrong = fixture.document.clone();
    wrong["layout"]["abi"] = serde_json::json!(u32::MAX);
    fs::write(&fixture.manifest, serde_json::to_vec(&wrong).unwrap()).unwrap();
    assert!(target(&fixture.root).is_err());
    wrong = fixture.document.clone();
    wrong["layout"]["platform"] = serde_json::json!("foreign-platform");
    fs::write(&fixture.manifest, serde_json::to_vec(&wrong).unwrap()).unwrap();
    assert!(target(&fixture.root).is_err());
    wrong = fixture.document.clone();
    wrong["files"] = serde_json::json!({"../foreign.exe": "00".repeat(32)});
    fs::write(&fixture.manifest, serde_json::to_vec(&wrong).unwrap()).unwrap();
    assert!(target(&fixture.root).is_err());
    fixture.restore();
    assert!(target(&fixture.root).is_ok());
}

#[test]
fn cancelled_verification_maps_to_session_unavailable_without_a_dispatch() {
    let fixture = PackageFixture::new();
    let contract: DiscoveryContract =
        serde_json::from_str(include_str!(concat!(env!("OUT_DIR"), "/contract.json"))).unwrap();
    let cancellation = Cancellation::default();
    cancellation.cancel();
    assert_eq!(
        super::target_from(&fixture.root, &contract, &[], &cancellation)
            .unwrap_err()
            .code,
        ErrorCode::SessionUnavailable
    );
    assert!(target(&fixture.root).is_ok());
}

#[test]
fn package_verification_reports_measured_local_cost() {
    let fixture = PackageFixture::new();
    let mut samples = Vec::new();
    for _ in 0..32 {
        let start = Instant::now();
        assert!(target(&fixture.root).is_ok());
        samples.push(start.elapsed());
    }
    samples.sort();
    eprintln!(
        "package verification fixture_bytes={} samples=32 median_us={} p95_us={}",
        fs::metadata(&fixture.image).unwrap().len(),
        samples[16].as_micros(),
        samples[30].as_micros()
    );
}
