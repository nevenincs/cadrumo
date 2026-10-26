use super::*;
use std::{
    os::unix::fs::{DirBuilderExt, PermissionsExt, symlink},
    time::{SystemTime, UNIX_EPOCH},
};

struct Scratch(PathBuf);
impl Scratch {
    fn new() -> Self {
        let path = fs::canonicalize("/tmp").unwrap().join(format!(
            "ct-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::DirBuilder::new().mode(0o700).create(&path).unwrap();
        Self(path)
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

#[test]
fn native_lookup_retains_a_private_canonical_base_without_product_creation() {
    let base = native_base().unwrap();
    base.verify().unwrap();
    assert_eq!(base.path, fs::canonicalize(&base.path).unwrap());
}

#[test]
fn passive_admission_does_not_create_and_active_admission_preserves_namespace() {
    let scratch = Scratch::new();
    let base = Directory::open(&scratch.0).unwrap();
    assert!(
        matches!(DarwinTransport::prepare(&base, false), Err(error) if error.kind() == io::ErrorKind::NotFound)
    );
    let transport = DarwinTransport::prepare(&base, true).unwrap();
    let path = transport.directory().to_owned();
    let inode = fs::metadata(&path).unwrap().ino();
    let second = DarwinTransport::prepare(&base, false).unwrap();
    assert_eq!(second.directory(), path);
    drop(transport);
    drop(second);
    assert_eq!(fs::metadata(&path).unwrap().ino(), inode);
}

#[test]
fn existing_links_and_insecure_modes_are_refused_without_repair() {
    let scratch = Scratch::new();
    let base = Directory::open(&scratch.0).unwrap();
    let path = scratch.0.join(DARWIN_RUNTIME_SOCKET_DIRECTORY);
    let other = scratch.0.join("other");
    fs::DirBuilder::new().mode(0o700).create(&other).unwrap();
    symlink(&other, &path).unwrap();
    assert!(DarwinTransport::prepare(&base, true).is_err());
    fs::remove_file(&path).unwrap();
    fs::create_dir(&path).unwrap();
    fs::set_permissions(&path, fs::Permissions::from_mode(0o755)).unwrap();
    assert!(DarwinTransport::prepare(&base, true).is_err());
    assert_eq!(fs::metadata(&path).unwrap().mode() & 0o777, 0o755);
    fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o755)).unwrap();
    assert!(Directory::open(&scratch.0).is_err());
    fs::set_permissions(&scratch.0, fs::Permissions::from_mode(0o700)).unwrap();
}

#[test]
fn replacement_of_either_retained_directory_refuses() {
    let scratch = Scratch::new();
    let base_path = scratch.0.join("base");
    fs::DirBuilder::new()
        .mode(0o700)
        .create(&base_path)
        .unwrap();
    let base = Directory::open(&base_path).unwrap();
    let transport = DarwinTransport::prepare(&base, true).unwrap();
    fs::rename(transport.directory(), scratch.0.join("retained-product")).unwrap();
    fs::DirBuilder::new()
        .mode(0o700)
        .create(transport.directory())
        .unwrap();
    assert!(transport.verify().is_err());
    let fresh = DarwinTransport::prepare(&base, false).unwrap();
    fs::rename(&base_path, scratch.0.join("retained-base")).unwrap();
    fs::DirBuilder::new()
        .mode(0o700)
        .create(&base_path)
        .unwrap();
    assert!(fresh.verify().is_err());
    assert!(DarwinTransport::prepare(&base, true).is_err());
    assert!(!base_path.join(DARWIN_RUNTIME_SOCKET_DIRECTORY).exists());
}

#[test]
fn repeated_resolution_never_recreates_or_adopts_a_replaced_live_namespace() {
    let scratch = Scratch::new();
    let base = Directory::open(&scratch.0).unwrap();
    let retained = Mutex::new(None);
    assert!(DarwinTransport::resolve(&base, false, &retained).is_err());
    assert!(retained.lock().unwrap().is_none());
    let transport = DarwinTransport::resolve(&base, true, &retained).unwrap();
    fs::rename(transport.directory(), scratch.0.join("retained-product")).unwrap();
    for create in [false, true] {
        assert!(DarwinTransport::resolve(&base, create, &retained).is_err());
        assert!(!transport.directory().exists());
    }
    fs::DirBuilder::new()
        .mode(0o700)
        .create(transport.directory())
        .unwrap();
    for create in [false, true] {
        assert!(DarwinTransport::resolve(&base, create, &retained).is_err());
    }
}

#[test]
fn socket_paths_enforce_leaf_and_encoded_length_boundaries() {
    let scratch = Scratch::new();
    let base = Directory::open(&scratch.0).unwrap();
    let transport = DarwinTransport::prepare(&base, true).unwrap();
    for name in ["", "..", "/absolute", "a/b", "nul\0byte"] {
        assert!(transport.socket_path(name).is_err());
    }
    let remaining =
        RUNTIME_SOCKET_PATH_LIMIT - transport.directory().as_os_str().as_bytes().len() - 1;
    assert!(transport.socket_path(&"a".repeat(remaining - 1)).is_ok());
    assert!(transport.socket_path(&"a".repeat(remaining)).is_err());
    assert!(transport.socket_path(&"ñ".repeat(remaining)).is_err());
}

#[test]
fn writable_ancestors_require_sticky_protection() {
    let scratch = Scratch::new();
    let parent = scratch.0.join("shared");
    let base = parent.join("private");
    fs::create_dir(&parent).unwrap();
    fs::DirBuilder::new().mode(0o700).create(&base).unwrap();
    fs::set_permissions(&parent, fs::Permissions::from_mode(0o777)).unwrap();
    assert!(Directory::open(&base).is_err());
    fs::set_permissions(&parent, fs::Permissions::from_mode(0o1777)).unwrap();
    assert!(Directory::open(&base).is_ok());
}
