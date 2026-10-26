//! Filesystem admission of boot records through the custody owner.
use cadrumo_manager::{
    custody::write_local_record,
    supervision::boot_record::{
        BootRecordUnavailable, MAXIMUM_BOOT_RECORD_BYTES, read_boot_record,
    },
};
use std::{
    fs,
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
};

struct Scratch(PathBuf);
impl Scratch {
    fn new() -> Self {
        static NEXT: AtomicUsize = AtomicUsize::new(0);
        let root = std::env::temp_dir().join(format!(
            "manager-boot-record-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        Self(root)
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

fn record() -> Vec<u8> {
    serde_json::to_vec(&serde_json::json!({
        "schema_version": 1,
        "boot_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
        "pid": 1234,
        "process_created": 133000000000000000_u64,
        "version": "0.5.1",
        "package_directory": null,
        "admission": "native"
    }))
    .unwrap()
}

#[test]
fn absence_valid_publication_and_unreadable_records_remain_distinct() {
    let scratch = Scratch::new();
    assert_eq!(
        read_boot_record(&scratch.0),
        Err(BootRecordUnavailable::Absent)
    );
    fs::create_dir(scratch.0.join(".runtime")).unwrap();
    let path = scratch.0.join(".runtime/boot.json");
    assert_eq!(
        read_boot_record(&scratch.0),
        Err(BootRecordUnavailable::Absent)
    );
    write_local_record(&path, &record(), MAXIMUM_BOOT_RECORD_BYTES).unwrap();
    assert_eq!(read_boot_record(&scratch.0).unwrap().pid, 1234);
    for bytes in [Vec::new(), b"{}".to_vec(), vec![b' '; 8193]] {
        fs::write(&path, bytes).unwrap();
        assert_eq!(
            read_boot_record(&scratch.0),
            Err(BootRecordUnavailable::Unreadable)
        );
    }
}

#[cfg(windows)]
#[test]
fn a_valid_record_below_a_junction_parent_is_refused() {
    let scratch = Scratch::new();
    let target = scratch.0.join("outside");
    fs::create_dir(&target).unwrap();
    fs::write(target.join("boot.json"), record()).unwrap();
    let junction = scratch.0.join(".runtime");
    assert!(
        std::process::Command::new("cmd")
            .args(["/C", "mklink", "/J"])
            .arg(&junction)
            .arg(&target)
            .stdout(std::process::Stdio::null())
            .status()
            .unwrap()
            .success()
    );
    assert_eq!(
        read_boot_record(&scratch.0),
        Err(BootRecordUnavailable::Unreadable)
    );
    fs::remove_dir(&junction).unwrap();
    assert!(target.join("boot.json").is_file());
}

#[cfg(unix)]
#[test]
fn a_valid_record_below_a_symbolic_link_parent_is_refused() {
    let scratch = Scratch::new();
    let target = scratch.0.join("outside");
    fs::create_dir(&target).unwrap();
    fs::write(target.join("boot.json"), record()).unwrap();
    std::os::unix::fs::symlink(&target, scratch.0.join(".runtime")).unwrap();
    assert_eq!(
        read_boot_record(&scratch.0),
        Err(BootRecordUnavailable::Unreadable)
    );
}
