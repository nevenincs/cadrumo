//! Windows desktop admission. Query existing objects; never create or register a session.
use std::{ffi::c_void, mem::size_of, ptr};

#[repr(C)]
struct UserObjectFlags {
    inherit: i32,
    reserved: i32,
    flags: u32,
}

#[link(name = "user32")]
unsafe extern "system" {
    fn GetProcessWindowStation() -> *mut c_void;
    fn GetUserObjectInformationW(
        object: *mut c_void,
        index: i32,
        information: *mut c_void,
        length: u32,
        needed: *mut u32,
    ) -> i32;
    fn OpenInputDesktop(flags: u32, inherit: i32, access: u32) -> *mut c_void;
    fn CloseDesktop(desktop: *mut c_void) -> i32;
}
#[link(name = "kernel32")]
unsafe extern "system" {
    fn FreeConsole() -> i32;
}

pub fn available() -> bool {
    let mut flags = UserObjectFlags {
        inherit: 0,
        reserved: 0,
        flags: 0,
    };
    // SAFETY: the process owns the station; the writable buffer has the API's
    // documented layout and size. Every acquired desktop handle is closed here.
    unsafe {
        let station = GetProcessWindowStation();
        if station.is_null()
            || GetUserObjectInformationW(
                station,
                1,
                ptr::from_mut(&mut flags).cast(),
                size_of::<UserObjectFlags>() as u32,
                ptr::null_mut(),
            ) == 0
            || flags.flags & 1 == 0
        {
            return false;
        }
        let desktop = OpenInputDesktop(0, 0, 1);
        if desktop.is_null() {
            return false;
        }
        CloseDesktop(desktop) != 0
    }
}

pub fn detach_console() {
    // SAFETY: this detaches only the current process, after GUI mode was selected.
    unsafe {
        FreeConsole();
    }
}
