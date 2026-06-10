"""Property-based tests for StateRegistry.

All tests use toy extract/make functions — no Manim dependency.

Object model
------------
- Objects are plain Python ints (used as stand-ins for Mobjects).
- Content = bytes(abs(obj))   when obj > 0,  else None
- State   = ("s", obj % 7)    when obj != 0, else None

This gives four cases:
  obj > 0  → (content, state)   -- image-like
  obj < 0  → (None, state)      -- vmobject-like
  obj == 0 → (None, None)       -- invalid, triggers ValueError on insert
  (content, None) case is exercised via a separate registry variant
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from manim_widget.registry import StateRegistry


# ---------------------------------------------------------------------------
# Toy registry factories
# ---------------------------------------------------------------------------


def _make_both() -> StateRegistry[int, bytes, tuple, dict]:
    """Registry where positive ints have content+state, negative have state only."""
    return StateRegistry(
        extract_content=lambda obj: bytes([obj % 256]) if obj > 0 else None,
        extract_state=lambda obj: ("s", obj % 7) if obj != 0 else None,
        make_from_content=lambda c: {"kind": "content", "data": list(c)},
        make_from_state=lambda s: {"kind": "state", "tag": s[1]},
    )


def _make_state_only() -> StateRegistry[int, bytes, tuple, dict]:
    """Registry where extract_content always returns None."""
    return StateRegistry(
        extract_content=lambda obj: None,
        extract_state=lambda obj: ("s", obj),
        make_from_content=lambda c: {},
        make_from_state=lambda s: {"tag": s[1]},
    )


def _make_content_only() -> StateRegistry[int, bytes, tuple, dict]:
    """Registry where extract_state always returns None."""
    return StateRegistry(
        extract_content=lambda obj: bytes([obj % 256]),
        extract_state=lambda obj: None,
        make_from_content=lambda c: {"data": list(c)},
        make_from_state=lambda s: {},
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

positive_int = st.integers(min_value=1, max_value=127)
negative_int = st.integers(min_value=-127, max_value=-1)
nonzero_int = st.integers(min_value=-127, max_value=127).filter(lambda x: x != 0)
any_val = st.dictionaries(st.text(max_size=4), st.integers(min_value=0, max_value=9))


# ---------------------------------------------------------------------------
# insert — four cases
# ---------------------------------------------------------------------------


@given(obj=positive_int)
def test_insert_content_and_state_returns_two_refs(obj):
    r = _make_both()
    main_ref, addon_ref = r.insert(obj)
    assert addon_ref is not None
    assert 0 <= main_ref < len(r)
    assert 0 <= addon_ref < len(r)
    assert main_ref != addon_ref


@given(obj=negative_int)
def test_insert_state_only_returns_none_addon(obj):
    r = _make_both()
    main_ref, addon_ref = r.insert(obj)
    assert addon_ref is None
    assert 0 <= main_ref < len(r)


@given(obj=positive_int)
def test_insert_content_only_returns_none_addon(obj):
    r = _make_content_only()
    main_ref, addon_ref = r.insert(obj)
    assert addon_ref is None
    assert 0 <= main_ref < len(r)


def test_insert_both_none_raises():
    r = _make_both()
    with pytest.raises(ValueError, match="None"):
        r.insert(0)


# ---------------------------------------------------------------------------
# insert — raise on duplicate
# ---------------------------------------------------------------------------


@given(obj=positive_int)
def test_insert_duplicate_content_raises(obj):
    r = _make_both()
    r.insert(obj)
    with pytest.raises(ValueError):
        r.insert(obj)


@given(obj=negative_int)
def test_insert_duplicate_state_raises(obj):
    r = _make_both()
    r.insert(obj)
    with pytest.raises(ValueError):
        r.insert(obj)


@given(obj=positive_int)
def test_insert_duplicate_content_only_raises(obj):
    r = _make_content_only()
    r.insert(obj)
    with pytest.raises(ValueError):
        r.insert(obj)


# ---------------------------------------------------------------------------
# get / get_addon before and after insert
# ---------------------------------------------------------------------------


@given(obj=nonzero_int)
def test_get_returns_none_before_insert(obj):
    r = _make_both()
    assert r.get(obj) is None


@given(obj=nonzero_int)
def test_get_returns_ref_after_insert(obj):
    r = _make_both()
    main_ref, _ = r.insert(obj)
    assert r.get(obj) == main_ref


@given(obj=positive_int)
def test_get_addon_returns_none_before_insert(obj):
    r = _make_both()
    assert r.get_addon(obj) is None


@given(obj=positive_int)
def test_get_addon_returns_ref_after_insert(obj):
    r = _make_both()
    _, addon_ref = r.insert(obj)
    assert r.get_addon(obj) == addon_ref


@given(obj=negative_int)
def test_get_addon_always_none_for_state_only(obj):
    r = _make_both()
    r.insert(obj)
    assert r.get_addon(obj) is None


# ---------------------------------------------------------------------------
# get_by_id — correct values stored
# ---------------------------------------------------------------------------


@given(obj=positive_int)
def test_content_entry_has_correct_value(obj):
    r = _make_both()
    main_ref, _ = r.insert(obj)
    val = r.get_by_id(main_ref)
    assert val == {"kind": "content", "data": [obj % 256]}


@given(obj=positive_int)
def test_addon_entry_has_correct_value(obj):
    r = _make_both()
    _, addon_ref = r.insert(obj)
    val = r.get_by_id(addon_ref)
    assert val == {"kind": "state", "tag": obj % 7}


@given(obj=negative_int)
def test_state_entry_has_correct_value(obj):
    r = _make_both()
    main_ref, _ = r.insert(obj)
    val = r.get_by_id(main_ref)
    assert val == {"kind": "state", "tag": obj % 7}


# ---------------------------------------------------------------------------
# dedup by value (not identity)
# ---------------------------------------------------------------------------


@given(tag=st.integers(min_value=0, max_value=6))
def test_same_state_value_reuses_entry(tag):
    """Two distinct negative ints sharing the same State value → same ref."""
    # In Python: (tag - 7) % 7 == tag and (tag - 14) % 7 == tag
    a, b = tag - 7, tag - 14
    r = _make_both()
    ref_a, _ = r.insert(a)
    assert r.get(b) == ref_a


@given(tag=st.integers(min_value=1, max_value=6))
def test_same_addon_state_reuses_addon_entry(tag):
    """Two images with same state (corner positions) share the addon entry."""
    # a=tag and b=tag+7 both satisfy x % 7 == tag but differ in x % 256 (content)
    a, b = tag, tag + 7
    r = _make_both()
    _, addon_a = r.insert(a)
    _, addon_b = r.insert(b)
    assert addon_a == addon_b


# ---------------------------------------------------------------------------
# as_list / len consistency
# ---------------------------------------------------------------------------


@given(objs=st.lists(nonzero_int, min_size=1, max_size=20))
def test_len_matches_as_list(objs):
    r = _make_both()
    for obj in objs:
        if r.get(obj) is None:
            r.insert(obj)
    assert len(r) == len(r.as_list())


@given(objs=st.lists(nonzero_int, min_size=1, max_size=20))
def test_all_refs_in_bounds(objs):
    r = _make_both()
    refs = []
    for obj in objs:
        if r.get(obj) is None:
            main, addon = r.insert(obj)
            refs.append(main)
            if addon is not None:
                refs.append(addon)
    for ref in refs:
        assert 0 <= ref < len(r)


# ---------------------------------------------------------------------------
# insert_raw
# ---------------------------------------------------------------------------


@given(vals=st.lists(any_val, min_size=1, max_size=20))
def test_insert_raw_always_appends(vals):
    r = _make_both()
    refs = [r.insert_raw(v) for v in vals]
    assert refs == list(range(len(vals)))


@given(vals=st.lists(any_val, min_size=1, max_size=20))
def test_insert_raw_value_retrievable(vals):
    r = _make_both()
    refs = [r.insert_raw(v) for v in vals]
    for ref, val in zip(refs, vals):
        assert r.get_by_id(ref) == val
