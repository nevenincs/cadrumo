use super::*;
use std::{cell::RefCell, rc::Rc};
use webview2_com::Microsoft::Web::WebView2::Win32::{
    ICoreWebView2, ICoreWebView2FrameInfoCollection, ICoreWebView2ProcessFailedEventArgs_Impl,
    ICoreWebView2ProcessFailedEventArgs2_Impl,
};
use windows_core::{PWSTR, implement};

const FAILED: i32 = 0x8000_4005_u32 as i32;

// A local COM object drives the real argument decoder and generated callback;
// no browser, GUI, runtime launch or private data is involved in these tests.
#[implement(ICoreWebView2ProcessFailedEventArgs2)]
struct Arguments {
    kind: Result<i32, i32>,
    reason: Result<i32, i32>,
    exit_code: Result<i32, i32>,
}
impl ICoreWebView2ProcessFailedEventArgs_Impl for Arguments_Impl {
    fn ProcessFailedKind(
        &self,
        value: *mut COREWEBVIEW2_PROCESS_FAILED_KIND,
    ) -> windows_core::Result<()> {
        let kind = self
            .kind
            .map_err(|code| Error::from_hresult(HRESULT(code)))?;
        // SAFETY: the real decoder supplies a valid writable stack scalar.
        unsafe { value.write(COREWEBVIEW2_PROCESS_FAILED_KIND(kind)) };
        Ok(())
    }
}
impl ICoreWebView2ProcessFailedEventArgs2_Impl for Arguments_Impl {
    fn Reason(&self, value: *mut COREWEBVIEW2_PROCESS_FAILED_REASON) -> windows_core::Result<()> {
        let reason = self
            .reason
            .map_err(|code| Error::from_hresult(HRESULT(code)))?;
        // SAFETY: the real decoder supplies a valid writable stack scalar.
        unsafe { value.write(COREWEBVIEW2_PROCESS_FAILED_REASON(reason)) };
        Ok(())
    }
    fn ExitCode(&self, value: *mut i32) -> windows_core::Result<()> {
        let exit_code = self
            .exit_code
            .map_err(|code| Error::from_hresult(HRESULT(code)))?;
        // SAFETY: the real decoder supplies a valid writable stack scalar.
        unsafe { value.write(exit_code) };
        Ok(())
    }
    fn ProcessDescription(&self, _: *mut PWSTR) -> windows_core::Result<()> {
        panic!("diagnostics must never request process descriptions");
    }
    fn FrameInfosForFailedProcess(&self) -> windows_core::Result<ICoreWebView2FrameInfoCollection> {
        panic!("diagnostics must never request frame names or sources");
    }
}

fn event_arguments(values: Arguments) -> ICoreWebView2ProcessFailedEventArgs {
    let details: ICoreWebView2ProcessFailedEventArgs2 = values.into();
    details.into()
}

#[implement(ICoreWebView2ProcessFailedEventArgs)]
struct LegacyArguments;
impl ICoreWebView2ProcessFailedEventArgs_Impl for LegacyArguments_Impl {
    fn ProcessFailedKind(
        &self,
        value: *mut COREWEBVIEW2_PROCESS_FAILED_KIND,
    ) -> windows_core::Result<()> {
        // SAFETY: the real decoder supplies a valid writable stack scalar.
        unsafe { value.write(COREWEBVIEW2_PROCESS_FAILED_KIND(3)) };
        Ok(())
    }
}

#[test]
fn real_com_callback_reads_only_scalar_getters_and_preserves_unknown_codes() {
    let events = Rc::new(RefCell::new(Vec::new()));
    let sink = events.clone();
    let callback = handler(move |event| sink.borrow_mut().push(event));
    let arguments = event_arguments(Arguments {
        kind: Ok(104),
        reason: Ok(-9),
        exit_code: Ok(0x8000_0003_u32 as i32),
    });
    // SAFETY: the owned COM objects stay live throughout their synchronous call.
    unsafe { callback.Invoke(None::<&ICoreWebView2>, &arguments) }.unwrap();
    assert_eq!(
        events.borrow().as_slice(),
        &[ProcessFailure {
            kind: Some(104),
            reason: Some(-9),
            exit_code: Some(0x8000_0003_u32 as i32),
            read_failures: ReadFailures::default(),
        }]
    );
}

#[test]
fn failed_getters_do_not_discard_independent_values() {
    let arguments = event_arguments(Arguments {
        kind: Err(FAILED),
        reason: Ok(3),
        exit_code: Err(0x8007_0005_u32 as i32),
    });
    let failure = read(Some(&arguments));
    assert_eq!(failure.kind, None);
    assert_eq!(failure.reason, Some(3));
    assert_eq!(failure.exit_code, None);
    assert_eq!(failure.read_failures.kind_hresult, Some(FAILED));
    assert_eq!(
        failure.read_failures.exit_code_hresult,
        Some(0x8007_0005_u32 as i32)
    );

    let arguments = event_arguments(Arguments {
        kind: Ok(2),
        reason: Err(FAILED),
        exit_code: Ok(259),
    });
    let failure = read(Some(&arguments));
    assert_eq!(failure.kind, Some(2));
    assert_eq!(failure.reason, None);
    assert_eq!(failure.exit_code, Some(259));
    assert_eq!(failure.read_failures.reason_hresult, Some(FAILED));
}

#[test]
fn legacy_or_missing_arguments_still_produce_an_observation() {
    let legacy: ICoreWebView2ProcessFailedEventArgs = LegacyArguments.into();
    let failure = read(Some(&legacy));
    assert_eq!(failure.kind, Some(3));
    assert_eq!(failure.reason, None);
    assert_eq!(failure.exit_code, None);
    assert_eq!(
        failure.read_failures.details_hresult,
        Some(0x8000_4002_u32 as i32)
    );
    let missing = read(None);
    assert_eq!(
        missing.read_failures.arguments_hresult,
        Some(0x8000_4003_u32 as i32)
    );
    assert_eq!(missing.kind, None);
}

#[test]
fn reporter_panic_cannot_unwind_across_the_com_boundary() {
    let callback = handler(|_| panic!("synthetic-private-panic-payload"));
    // SAFETY: live handler and optional null event arguments are valid COM input.
    let outcome = catch_unwind(AssertUnwindSafe(|| unsafe {
        callback.Invoke(
            None::<&ICoreWebView2>,
            None::<&ICoreWebView2ProcessFailedEventArgs>,
        )
    }));
    let failure = outcome.expect("panic must be contained").unwrap_err();
    assert_eq!(failure.code().0, FAILED);
}
