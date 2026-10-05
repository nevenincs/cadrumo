use cadrumo_manager::identity;
use std::process::Command;

const MANAGER: &str = env!("CARGO_BIN_EXE_cadrumo-manager");

#[test]
fn version_reports_the_projected_manager_name_and_version() {
    let output = Command::new(MANAGER)
        .arg("--version")
        .output()
        .expect("run the manager");
    assert!(output.status.success(), "{output:?}");
    assert!(output.stderr.is_empty(), "{output:?}");
    assert_eq!(
        String::from_utf8(output.stdout).expect("UTF-8 version line"),
        format!("{} {}\n", identity::MANAGER_NAME, identity::VERSION)
    );
}

#[test]
fn bare_start_enforces_native_admission() {
    let output = Command::new(MANAGER).output().expect("run the manager");
    #[cfg(windows)]
    if let Err(refusal) = cadrumo_manager::admission::require_current() {
        assert_eq!(output.status.code(), Some(77), "{output:?}");
        assert!(output.stdout.is_empty(), "{output:?}");
        assert_eq!(
            String::from_utf8(output.stderr).unwrap(),
            format!("{}\n", refusal.code())
        );
        return;
    }
    assert!(output.status.success(), "{output:?}");
    assert!(
        output.stdout.is_empty() && output.stderr.is_empty(),
        "{output:?}"
    );
}

#[test]
fn unknown_arguments_are_refused() {
    for arguments in [&["--help"][..], &["--version", "--version"], &["start"]] {
        let output = Command::new(MANAGER)
            .args(arguments)
            .output()
            .expect("run the manager");
        assert_eq!(output.status.code(), Some(2), "{arguments:?}: {output:?}");
        assert!(output.stdout.is_empty(), "{arguments:?}: {output:?}");
    }
}

#[cfg(all(windows, target_pointer_width = "64"))]
mod windows_image {
    use super::MANAGER;

    const IMAGE_SUBSYSTEM_WINDOWS_GUI: u16 = 2;
    const LOAD_LIBRARY_SEARCH_SYSTEM32: u16 = 0x800;
    const PE32_PLUS: u16 = 0x20B;
    const LOAD_CONFIG_DIRECTORY: usize = 10;

    fn u16_at(image: &[u8], offset: usize) -> u16 {
        u16::from_le_bytes(image[offset..offset + 2].try_into().expect("two bytes"))
    }

    fn u32_at(image: &[u8], offset: usize) -> usize {
        let value = u32::from_le_bytes(image[offset..offset + 4].try_into().expect("four bytes"));
        usize::try_from(value).expect("offset fits usize")
    }

    /// Optional-header offset of the PE32+ image, after checking both signatures.
    fn optional_header(image: &[u8]) -> usize {
        assert_eq!(&image[..2], b"MZ");
        let pe = u32_at(image, 0x3C);
        assert_eq!(&image[pe..pe + 4], b"PE\0\0");
        let optional = pe + 24;
        assert_eq!(u16_at(image, optional), PE32_PLUS);
        optional
    }

    fn file_offset(image: &[u8], rva: usize) -> usize {
        let pe = u32_at(image, 0x3C);
        let sections = usize::from(u16_at(image, pe + 6));
        let table = pe + 24 + usize::from(u16_at(image, pe + 20));
        (0..sections)
            .map(|index| table + index * 40)
            .find_map(|section| {
                let address = u32_at(image, section + 12);
                let size = u32_at(image, section + 8).max(u32_at(image, section + 16));
                (address..address + size)
                    .contains(&rva)
                    .then(|| u32_at(image, section + 20) + (rva - address))
            })
            .expect("RVA belongs to a section")
    }

    fn image() -> Vec<u8> {
        std::fs::read(MANAGER).expect("read the manager image")
    }

    #[test]
    fn image_uses_the_gui_subsystem() {
        let image = image();
        assert_eq!(
            u16_at(&image, optional_header(&image) + 68),
            IMAGE_SUBSYSTEM_WINDOWS_GUI
        );
    }

    #[test]
    fn image_resolves_load_time_imports_from_system32_only() {
        let image = image();
        let directory = optional_header(&image) + 112 + LOAD_CONFIG_DIRECTORY * 8;
        let rva = u32_at(&image, directory);
        assert_ne!(rva, 0, "the image has a load configuration directory");
        let config = file_offset(&image, rva);
        // IMAGE_LOAD_CONFIG_DIRECTORY64.DependentLoadFlags sits at 0x4E.
        assert!(
            u32_at(&image, config) >= 0x50,
            "load configuration carries DependentLoadFlags"
        );
        assert_eq!(u16_at(&image, config + 0x4E), LOAD_LIBRARY_SEARCH_SYSTEM32);
    }
}
