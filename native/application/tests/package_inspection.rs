use cadrumo_application::{
    component::Cancellation,
    error::Error,
    package::{PackageManifest, Readiness},
    value::{RelativePath, Sha256Digest},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Path, PathBuf},
};

const OWNER: &str = "data/package-manifest.json";
const PAYLOAD: &str = "lib/one/two/three/á payload.bin";
const DELEGATE: &str = "docs/user/manifest.json";
const DOCUMENT: &str = "docs/user/deep/index.html";

fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

struct Fixture {
    directory: tempfile::TempDir,
    root: PathBuf,
    payload: Vec<u8>,
    manifest: Value,
}

impl Fixture {
    fn new() -> Self {
        let temp_root = Path::new(env!("CARGO_TARGET_TMPDIR"));
        fs::create_dir_all(temp_root).unwrap();
        let directory = tempfile::tempdir_in(temp_root).unwrap();
        let root = directory.path().join("package ü space");
        let payload: Vec<_> = (0..70_123).map(|index| (index % 251) as u8).collect();
        for member in [OWNER, PAYLOAD, DELEGATE, DOCUMENT] {
            fs::create_dir_all(root.join(member).parent().unwrap()).unwrap();
        }
        fs::write(root.join(PAYLOAD), &payload).unwrap();
        fs::write(root.join(DOCUMENT), b"document fixture").unwrap();
        let delegated = serde_json::to_vec(&json!({
            "files": {"deep/index.html": digest(b"document fixture")}
        }))
        .unwrap();
        fs::write(root.join(DELEGATE), &delegated).unwrap();
        let manifest = json!({
            "layout": {"abi": 1, "platform": "fixture-target"},
            "python": "3.13.11", "distributions": {"cadrumo": "0.5.1"},
            "files": {PAYLOAD: digest(&payload), DELEGATE: digest(&delegated)},
            "delegated_inventories": {"docs/user": DELEGATE},
            "user_docs": {"directory": "docs/user", "bundled": true}
        });
        let fixture = Self {
            directory,
            root,
            payload,
            manifest,
        };
        fixture.write_manifest();
        fixture
    }

    fn write_manifest(&self) {
        fs::write(
            self.root.join(OWNER),
            serde_json::to_vec(&self.manifest).unwrap(),
        )
        .unwrap();
    }

    fn replace_delegated(&mut self, files: Value) {
        let bytes = serde_json::to_vec(&json!({"files": files})).unwrap();
        fs::write(self.root.join(DELEGATE), &bytes).unwrap();
        self.manifest["files"][DELEGATE] = json!(digest(&bytes));
        self.write_manifest();
    }

    fn inspect(&self) -> Result<Readiness, Error> {
        inspect_at(&self.root)
    }
}

fn inspect_at(root: &Path) -> Result<Readiness, Error> {
    let owner = RelativePath::new(OWNER).unwrap();
    Ok(PackageManifest::read(root, &owner)?
        .inspect(root, &owner, "fixture-target", 1)?
        .readiness)
}

#[test]
fn relocated_deep_package_is_rechecked_after_every_tamper() {
    let mut fixture = Fixture::new();
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
    let destination = fixture.directory.path().join("relocated 漢字 and spaces");
    let resolved_directory = fs::canonicalize(fixture.directory.path()).unwrap();
    assert!(
        fs::canonicalize(&fixture.root)
            .unwrap()
            .starts_with(&resolved_directory)
    );
    assert!(
        fs::canonicalize(destination.parent().unwrap())
            .unwrap()
            .starts_with(&resolved_directory)
    );
    fs::rename(&fixture.root, &destination).unwrap();
    fixture.root = destination;
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
    // The final byte lies past the streaming buffer's first 64 KiB.
    let mut tampered = fixture.payload.clone();
    *tampered.last_mut().unwrap() ^= 1;
    fs::write(fixture.root.join(PAYLOAD), tampered).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Incompatible(PAYLOAD.into())
    );
    fs::write(fixture.root.join(PAYLOAD), &fixture.payload).unwrap();
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
    fs::remove_file(fixture.root.join(PAYLOAD)).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Missing(PAYLOAD.into())
    );
    fs::create_dir(fixture.root.join(PAYLOAD)).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Incompatible(PAYLOAD.into())
    );
    fs::remove_dir(fixture.root.join(PAYLOAD)).unwrap();
    fs::write(fixture.root.join(PAYLOAD), &fixture.payload).unwrap();
    fs::create_dir(fixture.root.join("unlisted empty directory")).unwrap();
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
}

#[cfg(any(unix, windows))]
#[test]
fn nonportable_empty_directory_remains_allowed_but_its_leaf_is_refused() {
    let mut fixture = Fixture::new();
    // On Windows the resolved verbatim path preserves the actual trailing dot.
    // Unix permits the same directory name without platform-specific handling.
    fixture.root = fs::canonicalize(&fixture.root).unwrap();
    let directory = fixture.root.join("empty.");
    fs::create_dir(&directory).unwrap();
    assert!(
        fs::read_dir(&fixture.root)
            .unwrap()
            .any(|entry| entry.unwrap().file_name() == "empty.")
    );
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
    fs::write(directory.join("inside.bin"), b"unlisted leaf").unwrap();
    let result = fixture.inspect();
    fs::remove_file(directory.join("inside.bin")).unwrap();
    fs::remove_dir(directory).unwrap();
    assert!(matches!(result, Err(Error::Invalid(_))));
}

#[test]
fn delegated_missing_kind_corruption_and_parse_failures_remain_distinct() {
    let mut fixture = Fixture::new();
    let original = fs::read(fixture.root.join(DELEGATE)).unwrap();
    fs::remove_file(fixture.root.join(DELEGATE)).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Missing(DELEGATE.into())
    );
    fs::create_dir(fixture.root.join(DELEGATE)).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Incompatible(DELEGATE.into())
    );
    fs::remove_dir(fixture.root.join(DELEGATE)).unwrap();
    fs::write(fixture.root.join(DELEGATE), b"untrusted invalid JSON").unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Incompatible(DELEGATE.into())
    );
    fixture.manifest["files"][DELEGATE] = json!(digest(b"untrusted invalid JSON"));
    fixture.write_manifest();
    assert!(matches!(fixture.inspect(), Err(Error::Json(_))));
    fs::write(fixture.root.join(DELEGATE), &original).unwrap();
    fixture.manifest["files"][DELEGATE] = json!(digest(&original));
    fixture.write_manifest();
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
    fs::remove_file(fixture.root.join(DOCUMENT)).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Missing(DOCUMENT.into())
    );
    fs::create_dir(fixture.root.join(DOCUMENT)).unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Incompatible(DOCUMENT.into())
    );
}

#[test]
fn delegated_bytes_keep_the_existing_json_bound() {
    let mut fixture = Fixture::new();
    let oversized = vec![b' '; 16 * 1024 * 1024 + 1];
    fs::write(fixture.root.join(DELEGATE), &oversized).unwrap();
    fixture.manifest["files"][DELEGATE] = json!(digest(&oversized));
    fixture.write_manifest();
    assert!(matches!(fixture.inspect(), Err(Error::LimitExceeded)));
}

#[test]
fn delegated_containment_collisions_escapes_and_extra_members_are_refused() {
    let mut fixture = Fixture::new();
    fixture.manifest["delegated_inventories"]["docs/user"] = json!(PAYLOAD);
    fixture.write_manifest();
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));
    let mut fixture = Fixture::new();
    fixture.manifest["files"]
        .as_object_mut()
        .unwrap()
        .remove(DELEGATE);
    fixture.write_manifest();
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));
    for member in ["manifest.json", "../../lib/x", "..\\x", "C:/x"] {
        let mut fixture = Fixture::new();
        fixture.replace_delegated(json!({member: digest(b"collision fixture")}));
        assert!(fixture.inspect().is_err(), "accepted {member}");
    }
    let fixture = Fixture::new();
    fs::write(fixture.root.join("docs/user/deep/extra.html"), b"extra").unwrap();
    assert_eq!(
        fixture.inspect().unwrap(),
        Readiness::Incompatible("unexpected file: docs/user/deep/extra.html".into())
    );
}

#[test]
fn two_delegated_prefixes_sharing_one_member_still_detect_collisions() {
    let mut fixture = Fixture::new();
    fixture.manifest["delegated_inventories"]["docs"] = json!(DELEGATE);
    fixture.replace_delegated(json!({
        "index.html": digest(b"document fixture"),
        "user/index.html": digest(b"document fixture")
    }));
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(reason))
        if reason.contains("collides") && reason.contains("docs/user/index.html")));
}

#[test]
fn owning_manifest_is_excluded_only_when_not_in_the_expanded_inventory() {
    let mut fixture = Fixture::new();
    fixture.manifest["files"][OWNER] = json!(digest(b"owner"));
    fixture.write_manifest();
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));

    let fixture = Fixture::new();
    let owner = RelativePath::new("docs/user/owner.json").unwrap();
    let old_owner_bytes = fs::read(fixture.root.join(OWNER)).unwrap();
    fs::write(owner.under(&fixture.root), &old_owner_bytes).unwrap();
    fs::remove_file(fixture.root.join(OWNER)).unwrap();
    let mut manifest: PackageManifest = serde_json::from_slice(&old_owner_bytes).unwrap();
    let nested = serde_json::to_vec(&json!({"files": {
        "deep/index.html": digest(b"document fixture"),
        "owner.json": digest(&old_owner_bytes)
    }}))
    .unwrap();
    fs::write(fixture.root.join(DELEGATE), &nested).unwrap();
    manifest.files.insert(
        RelativePath::new(DELEGATE).unwrap(),
        Sha256Digest::new(digest(&nested)).unwrap(),
    );
    // The API accepts an already parsed manifest. Its excluded on-disk owner
    // may nevertheless become an ordinary hashed member of delegated inventory.
    assert_eq!(
        manifest
            .inspect(&fixture.root, &owner, "fixture-target", 1)
            .unwrap()
            .readiness,
        Readiness::Ready
    );
    let mut manifest: PackageManifest = serde_json::from_slice(&old_owner_bytes).unwrap();
    manifest.files.insert(
        RelativePath::new(DELEGATE).unwrap(),
        Sha256Digest::new(digest(&nested)).unwrap(),
    );
    fs::write(owner.under(&fixture.root), b"changed owning manifest").unwrap();
    assert_eq!(
        manifest
            .inspect(&fixture.root, &owner, "fixture-target", 1)
            .unwrap()
            .readiness,
        Readiness::Incompatible(owner.as_str().into())
    );
}

#[test]
fn cancelled_package_read_and_inspection_refuse_without_changing_uncancelled_calls() {
    let fixture = Fixture::new();
    let owner = RelativePath::new(OWNER).unwrap();
    let manifest = PackageManifest::read(&fixture.root, &owner).unwrap();
    let cancellation = Cancellation::default();
    cancellation.cancel();
    assert!(matches!(
        PackageManifest::read_cancellable(&fixture.root.join("absent"), &owner, &cancellation),
        Err(Error::Cancelled)
    ));
    assert!(matches!(
        manifest.inspect_cancellable(&fixture.root, &owner, "fixture-target", 1, &cancellation),
        Err(Error::Cancelled)
    ));
    assert_eq!(fixture.inspect().unwrap(), Readiness::Ready);
    let fresh = Cancellation::default();
    assert_eq!(
        PackageManifest::read_cancellable(&fixture.root, &owner, &fresh)
            .unwrap()
            .inspect_cancellable(&fixture.root, &owner, "fixture-target", 1, &fresh)
            .unwrap()
            .readiness,
        Readiness::Ready
    );
}

#[cfg(any(unix, windows))]
struct Link {
    path: PathBuf,
    #[cfg(windows)]
    directory: bool,
}

#[cfg(any(unix, windows))]
impl Drop for Link {
    fn drop(&mut self) {
        #[cfg(windows)]
        let removed = if self.directory {
            fs::remove_dir(&self.path)
        } else {
            fs::remove_file(&self.path)
        };
        #[cfg(unix)]
        let removed = fs::remove_file(&self.path);
        assert!(
            removed.is_ok(),
            "failed to unlink the isolated link fixture"
        );
    }
}

#[cfg(any(unix, windows))]
fn directory_link(target: &Path, path: PathBuf) -> Link {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let result = std::process::Command::new("cmd.exe")
            .args(["/d", "/c", "mklink", "/J"])
            .arg(&path)
            .arg(target)
            .creation_flags(0x0800_0000)
            .output()
            .unwrap();
        assert!(result.status.success(), "junction fixture creation failed");
    }
    #[cfg(unix)]
    std::os::unix::fs::symlink(target, &path).unwrap();
    Link {
        path,
        #[cfg(windows)]
        directory: true,
    }
}

#[cfg(any(unix, windows))]
fn file_link(target: &Path, path: PathBuf) -> Link {
    #[cfg(windows)]
    std::os::windows::fs::symlink_file(target, &path).unwrap();
    #[cfg(unix)]
    std::os::unix::fs::symlink(target, &path).unwrap();
    Link {
        path,
        #[cfg(windows)]
        directory: false,
    }
}

#[cfg(any(unix, windows))]
#[test]
fn linked_root_and_deep_root_ancestor_are_refused() {
    let fixture = Fixture::new();
    let root_link = directory_link(&fixture.root, fixture.directory.path().join("linked root"));
    assert!(matches!(
        inspect_at(&root_link.path),
        Err(Error::Invalid(_))
    ));
    let ancestor_link = directory_link(
        fixture.directory.path(),
        fixture.directory.path().join("linked ancestor"),
    );
    let alias = ancestor_link.path.join("package ü space");
    assert!(matches!(inspect_at(&alias), Err(Error::Invalid(_))));
}

#[cfg(any(unix, windows))]
#[test]
fn descended_directory_and_unlisted_directory_links_are_refused() {
    let fixture = Fixture::new();
    let target = fixture.directory.path().join("outside directory");
    fs::create_dir(&target).unwrap();
    let path = fixture.root.join("lib/one/two/three");
    fs::remove_file(path.join("á payload.bin")).unwrap();
    fs::remove_dir(&path).unwrap();
    let _link = directory_link(&target, path);
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));

    let fixture = Fixture::new();
    let target = fixture.directory.path().join("extra target");
    fs::create_dir(&target).unwrap();
    let _link = directory_link(&target, fixture.root.join("unlisted linked directory"));
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));
}

#[cfg(any(unix, windows))]
#[test]
fn listed_file_links_and_file_position_junctions_are_refused() {
    let fixture = Fixture::new();
    let target = fixture.directory.path().join("regular target");
    fs::write(&target, &fixture.payload).unwrap();
    fs::remove_file(fixture.root.join(PAYLOAD)).unwrap();
    let _link = file_link(&target, fixture.root.join(PAYLOAD));
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));

    let fixture = Fixture::new();
    let target = fixture.directory.path().join("directory target");
    fs::create_dir(&target).unwrap();
    fs::remove_file(fixture.root.join(PAYLOAD)).unwrap();
    let _link = directory_link(&target, fixture.root.join(PAYLOAD));
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));
}

#[cfg(any(unix, windows))]
#[test]
fn delegated_manifest_link_and_its_linked_ancestor_are_refused() {
    let fixture = Fixture::new();
    let target = fixture.directory.path().join("delegated target.json");
    fs::write(&target, fs::read(fixture.root.join(DELEGATE)).unwrap()).unwrap();
    fs::remove_file(fixture.root.join(DELEGATE)).unwrap();
    let _link = file_link(&target, fixture.root.join(DELEGATE));
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));

    let fixture = Fixture::new();
    let target = fixture.directory.path().join("delegated directory target");
    fs::create_dir(&target).unwrap();
    fs::write(
        target.join("manifest.json"),
        fs::read(fixture.root.join(DELEGATE)).unwrap(),
    )
    .unwrap();
    fs::remove_file(fixture.root.join(DELEGATE)).unwrap();
    fs::remove_file(fixture.root.join(DOCUMENT)).unwrap();
    fs::remove_dir(fixture.root.join("docs/user/deep")).unwrap();
    fs::remove_dir(fixture.root.join("docs/user")).unwrap();
    let _link = directory_link(&target, fixture.root.join("docs/user"));
    assert!(matches!(fixture.inspect(), Err(Error::Invalid(_))));
}
