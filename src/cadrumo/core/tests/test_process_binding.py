"""Real concurrency proofs for the process-wide binding with scoped overrides."""

from __future__ import annotations

import asyncio
import threading
from contextvars import copy_context

import pytest

from ..process_binding import ProcessScopedBinding

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Holder:
    """A distinguishable object identity for the binding to carry."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"_Holder({self.name!r})"


def test_unbound_binding_reads_absent() -> None:
    """A binding nobody published reads as an absence, not as a default object."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_unbound")

    assert binding.get() is None


def test_bind_publishes_to_a_sibling_thread() -> None:
    """A value bound on one thread is the process truth every other thread reads.

    This is the contract a plain ``ContextVar`` cannot hold and the reason this
    type exists: a credential surface that authenticates on a worker thread
    must be observable from the thread that reads storage afterwards.
    """
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_cross_thread")
    holder = _Holder("bound-on-worker")
    observed: list[_Holder | None] = []

    def bind_on_worker() -> None:
        binding.bind(holder)

    worker = threading.Thread(target=bind_on_worker)
    worker.start()
    worker.join()

    assert binding.get() is holder

    def read_on_worker() -> None:
        observed.append(binding.get())

    reader = threading.Thread(target=read_on_worker)
    reader.start()
    reader.join()

    assert observed == [holder]


def test_bind_inside_a_copied_context_survives_that_context() -> None:
    """A bind made under ``Context.run`` publishes, where a ``ContextVar`` set would not.

    Textual runs a credential door on a thread worker under
    :meth:`contextvars.Context.run`, which discards every context write made
    inside it. The process value is what carries the login out of that frame.
    """
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_copied_context")
    holder = _Holder("bound-under-copy-context")

    copy_context().run(binding.bind, holder)

    assert binding.get() is holder


def test_bind_inside_a_copied_context_of_a_worker_thread_reaches_the_main_task() -> None:
    """The real Textual shape: a copied context, on a thread, read from the event loop."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_worker_thread_copy")
    holder = _Holder("bound-on-textual-style-worker")

    async def authenticate_then_read() -> _Holder | None:
        def worker() -> None:
            copy_context().run(binding.bind, holder)

        await asyncio.to_thread(worker)
        return binding.get()

    assert asyncio.run(authenticate_then_read()) is holder


def test_a_copied_context_reads_the_process_value_when_it_carries_no_override() -> None:
    """A door running in a copied context observes the process binding it inherited."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_copy_reads_process")
    holder = _Holder("published-before-the-copy")
    binding.bind(holder)
    observed: list[_Holder | None] = []

    def read_on_worker() -> None:
        copy_context().run(lambda: observed.append(binding.get()))

    worker = threading.Thread(target=read_on_worker)
    worker.start()
    worker.join()

    assert observed == [holder]


def test_override_shadows_the_process_value_and_unwinds() -> None:
    """A scoped span shadows the process binding without replacing it."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_override")
    published = _Holder("published")
    scoped = _Holder("scoped")
    binding.bind(published)

    with binding.override(scoped):
        assert binding.get() is scoped

    assert binding.get() is published


def test_nested_overrides_restore_the_exact_enclosing_binding() -> None:
    """Nested spans stack and unwind to what their own caller observed."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_nested_override")
    outer = _Holder("outer")
    inner = _Holder("inner")

    with binding.override(outer):
        with binding.override(inner):
            assert binding.get() is inner
        assert binding.get() is outer

    assert binding.get() is None


def test_an_override_of_none_hides_the_process_value() -> None:
    """A deliberate suspension is an absence, not the lack of an override.

    The two are stored distinguishably on purpose: collapsing them would let
    the process value show through the very block that suspended it.
    """
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_suspend")
    published = _Holder("published")
    binding.bind(published)

    with binding.override(None):
        assert binding.get() is None

    assert binding.get() is published


def test_bind_inside_an_override_is_visible_to_its_own_caller() -> None:
    """An unscoped bind is observable in the span that performed it."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_bind_inside_override")
    scoped = _Holder("scoped")
    published = _Holder("published-from-inside")

    with binding.override(scoped):
        binding.bind(published)
        assert binding.get() is published

    assert binding.get() is published


def test_clear_bound_removes_the_value_from_both_layers() -> None:
    """Retiring a value inside the span that shadows it clears both bindings.

    This is the resurrection case: with a plain ``ContextVar`` the span's token
    reset would restore the retired object as the value the next caller reads,
    which for a bucket session means a sealed, zeroised object advertised as
    live.
    """
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_clear_both")
    retiring = _Holder("retiring")
    binding.bind(retiring)

    with binding.override(retiring):
        binding.clear_bound(retiring)
        assert binding.get() is None

    assert binding.get() is None


def test_clear_bound_leaves_an_unrelated_process_value_intact() -> None:
    """Closing a scoped value must not evict the process binding it shadowed."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_clear_scoped_only")
    published = _Holder("published")
    scoped = _Holder("scoped")
    binding.bind(published)

    with binding.override(scoped):
        binding.clear_bound(scoped)
        assert binding.get() is None

    assert binding.get() is published


def test_clear_bound_preserves_a_replacement_installed_during_retirement() -> None:
    """Identity, not equality: a reentrant replacement survives the retirement."""
    binding: ProcessScopedBinding[_Holder] = ProcessScopedBinding("test_clear_identity")
    retiring = _Holder("retiring")
    replacement = _Holder("replacement")
    binding.bind(replacement)

    binding.clear_bound(retiring)

    assert binding.get() is replacement
