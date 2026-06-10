"""Global content-addressed state registry.

Stores values indexed by stable integers.  Three deduplication banks:

- **content_bank**: keyed by the ``Content`` value returned by ``extract_content``.
  Immutable blobs (e.g. ``PixelContent``).  ``make_from_content`` called at most
  once per unique content.

- **state_bank**: keyed by the ``State`` value returned by ``extract_state``.
  Two mobjects with identical visual state share the same entry — better dedup
  than identity-based keying.  ``make_from_state`` called at most once per
  unique state.

- **addon_bank**: keyed by ``State`` as well.  Populated only for objects where
  both extracts are non-None (e.g. ImageMobject: content = pixel data, state =
  corner positions).

Four insertion cases driven by ``(extract_content(obj), extract_state(obj))``:

  (content, state)  → (content_ref, addon_ref)    e.g. ImageMobject
  (None,    state)  → (state_ref,   None)          e.g. VMobject
  (content, None)   → (content_ref, None)          e.g. pure blob
  (None,    None)   → raises ValueError

All IDs share a single integer space and a single ``as_list()`` output, so they
are directly usable as indices into the JSON ``states`` array.

``insert_raw`` is an escape hatch for synthetic values (VGroup subpath states)
that cannot be captured in a hashable container.
"""

from __future__ import annotations

from typing import Callable, Generic, Hashable, TypeVar

Obj = TypeVar("Obj")
Content = TypeVar("Content", bound=Hashable)
State = TypeVar("State", bound=Hashable)
Val = TypeVar("Val")


class StateRegistry(Generic[Obj, Content, State, Val]):
    def __init__(
        self,
        extract_content: Callable[[Obj], Content | None],
        extract_state: Callable[[Obj], State | None],
        make_from_content: Callable[[Content], Val],
        make_from_state: Callable[[State], Val],
    ) -> None:
        self._extract_content = extract_content
        self._extract_state = extract_state
        self._make_from_content = make_from_content
        self._make_from_state = make_from_state

        self._values: list[Val] = []
        # Content value → state_id
        self._content_bank: dict[Hashable, int] = {}
        # State value → state_id  (state-only objects and content+state addon)
        self._state_bank: dict[Hashable, int] = {}
        # State value → state_id  (addon entries for content+state objects)
        self._addon_bank: dict[Hashable, int] = {}

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------

    def insert(self, obj: Obj) -> tuple[int, int | None]:
        """Insert obj and return ``(main_ref, addon_ref)``.

        ``addon_ref`` is ``None`` unless both extracts return non-None.

        pre:  self.get(obj) is None
        raises: ValueError if already registered or both extracts return None
        post: 0 <= __return__[0] < len(self)
        post: implies(__return__[1] is not None, 0 <= __return__[1] < len(self))
        """
        content = self._extract_content(obj)

        if content is not None and content in self._content_bank:
            raise ValueError(
                f"Content already registered — call get() before insert(). "
                f"content={content!r}"
            )

        if content is not None:
            content_ref = len(self._values)
            self._values.append(self._make_from_content(content))
            self._content_bank[content] = content_ref

        # extract_state is called after content is registered so that
        # extract_state implementations can call get_content_ref() safely.
        state = self._extract_state(obj)

        if content is None and state is None:
            raise ValueError(
                f"Both extract_content and extract_state returned None for {obj!r}"
            )

        if content is None and state is not None and state in self._state_bank:
            raise ValueError(
                f"State already registered — call get() before insert(). "
                f"state={state!r}"
            )

        if content is not None:
            if state is not None:
                addon_ref = self._addon_bank.get(state)
                if addon_ref is None:
                    addon_ref = len(self._values)
                    self._values.append(self._make_from_state(state))
                    self._addon_bank[state] = addon_ref
                return (content_ref, addon_ref)

            return (content_ref, None)

        # content is None, state is not None
        state_ref = len(self._values)
        self._values.append(self._make_from_state(state))
        self._state_bank[state] = state_ref
        return (state_ref, None)

    def ensure_addon(self, state: State) -> int:
        """Get or create an addon entry for ``state``, without requiring an Obj.

        Used when the content for a mob is already registered (via ``insert``)
        but the mob has moved to a new position that hasn't been seen yet.

        post: 0 <= __return__ < len(self)
        post: self._addon_bank[state] == __return__
        """
        existing = self._addon_bank.get(state)
        if existing is not None:
            return existing
        ref = len(self._values)
        self._values.append(self._make_from_state(state))
        self._addon_bank[state] = ref
        return ref

    def insert_raw(self, value: Val) -> int:
        """Append ``value`` unconditionally — no keying, no dedup.

        Escape hatch for synthetic values (VGroup subpath states) that cannot
        be captured in a hashable ``State`` container.

        post: __return__ == len(self) - 1
        post: self.get_by_id(__return__) == value
        """
        state_id = len(self._values)
        self._values.append(value)
        return state_id

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, obj: Obj) -> int | None:
        """Return the main ref for obj, or None if not yet registered.

        For content objects: looks up by the extracted Content value.
        For state-only objects: looks up by the extracted State value.

        post: implies(__return__ is not None, 0 <= __return__ < len(self))
        """
        content = self._extract_content(obj)
        if content is not None:
            return self._content_bank.get(content)
        state = self._extract_state(obj)
        if state is not None:
            return self._state_bank.get(state)
        return None

    def get_addon(self, obj: Obj) -> int | None:
        """Return the addon ref for obj, or None.

        Non-None only for objects where both extracts return non-None and the
        current state has been registered via ``insert``.

        post: implies(__return__ is not None, 0 <= __return__ < len(self))
        """
        content = self._extract_content(obj)
        if content is None:
            return None
        state = self._extract_state(obj)
        if state is None:
            return None
        return self._addon_bank.get(state)

    def get_content_ref(self, content: Content) -> int | None:
        """Return the content_ref for ``content`` if already registered, else None.

        Used by ``extract_state`` implementations that need the content_ref to
        build a derived state key (e.g. ``{"from": content_ref, "points": ...}``).

        post: implies(__return__ is not None, 0 <= __return__ < len(self))
        """
        return self._content_bank.get(content)

    def get_by_id(self, state_id: int) -> Val:
        """Return stored value for ``state_id``.

        pre: 0 <= state_id < len(self)
        """
        return self._values[state_id]

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def as_list(self) -> list[Val]:
        """All stored values in insertion order."""
        return list(self._values)

    def __len__(self) -> int:
        return len(self._values)
