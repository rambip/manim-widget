"""Hypothesis strategies for generating random-but-valid ManimWidget scenes.

Architecture
------------
Hypothesis controls the *description* of a scene (spec dataclasses), not the
Manim objects themselves.  Manim objects are stateful and cannot be shared
across calls, so they are instantiated fresh inside each ``construct`` run.

The generation pipeline is:

  MobjectSpec  ──►  ``_instantiate``  ──►  live Manim mobject
  CommandSpec  ──►  ``_execute``      ──►  self.play(…) / self.add(…)

``construct_script`` produces a ``(list[MobjectSpec], list[CommandSpec])``
pair that is guaranteed to be *valid*: no command references a mobject that
has not yet been added to the scene, and no Transform reuses the same index
for source and target.

``make_scene_class(mob_specs, commands, *, fps, camera_move)`` wraps the pair
in a concrete ``ManimWidget`` subclass ready to run.

Flags
-----
``allow_groups``     Include VGroup specs (recursive, bounded by ``max_depth``).
``allow_transform``  Include Transform between two live mobjects.
``allow_fadeout``    Include FadeOut (removes the mob from the live set).
``allow_updaters``   Include a ValueTracker + add_updater pair so the play()
                     call goes through _play_data_path.
``camera_move``      Set camera phi/theta before the first play() so the
                     section camera snapshot reflects a non-default pose.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Mobject specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CircleSpec:
    radius: float = 1.0
    fill_opacity: float = 0.0


@dataclass(frozen=True)
class SquareSpec:
    side_length: float = 1.0


@dataclass(frozen=True)
class DotSpec:
    pass


@dataclass(frozen=True)
class VGroupSpec:
    children: tuple  # tuple[MobjectSpec, ...]


@dataclass(frozen=True)
class ArrowSpec:
    pass


MobjectSpec = CircleSpec | SquareSpec | DotSpec | VGroupSpec | ArrowSpec

# ---------------------------------------------------------------------------
# Command specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CreateCmd:
    mob_idx: int


@dataclass(frozen=True)
class FadeInCmd:
    mob_idx: int


@dataclass(frozen=True)
class TransformCmd:
    src_idx: int
    tgt_idx: int  # must differ from src_idx


@dataclass(frozen=True)
class ShiftCmd:
    mob_idx: int
    dx: float
    dy: float


@dataclass(frozen=True)
class FadeOutCmd:
    mob_idx: int


@dataclass(frozen=True)
class UpdaterCmd:
    """One play() driven by a ValueTracker updater (routes to _play_data_path)."""

    mob_idx: int  # the mobject that moves
    end_value: float
    run_time: float


@dataclass(frozen=True)
class GrowArrowCmd:
    mob_idx: int  # must be an ArrowSpec mob


@dataclass(frozen=True)
class AnimateSubmobCmd:
    """Animate arrow.submobjects[-1] directly — exercises the submob-lookup fix."""

    mob_idx: int  # must be a live ArrowSpec mob
    dx: float
    dy: float


CommandSpec = (
    CreateCmd
    | FadeInCmd
    | TransformCmd
    | ShiftCmd
    | FadeOutCmd
    | UpdaterCmd
    | GrowArrowCmd
    | AnimateSubmobCmd
)

# ---------------------------------------------------------------------------
# Individual mobject strategies
# ---------------------------------------------------------------------------

_small_float = st.floats(0.3, 2.5, allow_nan=False, allow_infinity=False)
_shift_float = st.floats(-2.0, 2.0, allow_nan=False, allow_infinity=False)


@st.composite
def circle_spec(draw) -> CircleSpec:
    return CircleSpec(
        radius=draw(_small_float),
        fill_opacity=draw(st.floats(0.0, 1.0, allow_nan=False)),
    )


@st.composite
def square_spec(draw) -> SquareSpec:
    return SquareSpec(side_length=draw(_small_float))


def dot_spec() -> st.SearchStrategy[DotSpec]:
    return st.just(DotSpec())


@st.composite
def leaf_mob_spec(draw, *, allow_arrows: bool = False) -> MobjectSpec:
    options = [circle_spec(), square_spec(), dot_spec()]
    if allow_arrows:
        options.append(st.just(ArrowSpec()))
    return draw(st.one_of(*options))


def mob_spec(
    max_depth: int = 2, *, allow_arrows: bool = False
) -> st.SearchStrategy[MobjectSpec]:
    """Possibly-recursive mobject spec (VGroup if depth allows)."""
    if max_depth == 0:
        return leaf_mob_spec(allow_arrows=allow_arrows)
    return st.recursive(
        base=leaf_mob_spec(allow_arrows=allow_arrows),
        extend=lambda inner: st.builds(
            lambda kids: VGroupSpec(children=tuple(kids)),
            st.lists(inner, min_size=1, max_size=3),
        ),
        max_leaves=6,
    )


# ---------------------------------------------------------------------------
# Scene script strategy
# ---------------------------------------------------------------------------


@st.composite
def construct_script(
    draw,
    *,
    min_mobs: int = 1,
    max_mobs: int = 4,
    min_plays: int = 1,
    max_plays: int = 5,
    allow_groups: bool = True,
    allow_transform: bool = True,
    allow_fadeout: bool = True,
    allow_updaters: bool = False,
    allow_arrows: bool = False,
) -> tuple[list[MobjectSpec], list[CommandSpec]]:
    """Generate a valid (mob_specs, commands) pair.

    Validity guarantee: every command only references mob indices that are
    currently live (added but not faded-out), and TransformCmd always uses
    two distinct indices.

    post: forall(commands, lambda c: _mob_idx(c) < len(mob_specs))
    post: forall(commands, lambda c: not isinstance(c, TransformCmd)
                                     or c.src_idx != c.tgt_idx)
    """
    depth = 2 if allow_groups else 0
    n_mobs = draw(st.integers(min_mobs, max_mobs))
    mob_specs = [
        draw(mob_spec(depth, allow_arrows=allow_arrows)) for _ in range(n_mobs)
    ]

    commands: list[CommandSpec] = []
    live: set[int] = set()  # indices of mobs currently in the scene
    live_arrows: set[int] = set()  # subset of live that are ArrowSpec

    def _intro_cmd(idx: int) -> st.SearchStrategy[CommandSpec]:
        if isinstance(mob_specs[idx], ArrowSpec):
            return st.just(GrowArrowCmd(mob_idx=idx))
        return st.one_of(
            st.just(CreateCmd(mob_idx=idx)),
            st.just(FadeInCmd(mob_idx=idx)),
        )

    n_plays = draw(st.integers(min_plays, max_plays))

    for _ in range(n_plays):
        if not live:
            # Nothing in scene yet — must introduce something.
            idx = draw(st.integers(0, n_mobs - 1))
            cmd: CommandSpec = draw(_intro_cmd(idx))
            commands.append(cmd)
            live.add(idx)
            if isinstance(mob_specs[idx], ArrowSpec):
                live_arrows.add(idx)
            continue

        # Build the menu of valid commands given current live set.
        options: list[st.SearchStrategy[CommandSpec]] = []

        # Introduce a new mob (if any not yet live).
        not_live = [i for i in range(n_mobs) if i not in live]
        if not_live:
            new_idx = draw(st.sampled_from(not_live))
            options.append(_intro_cmd(new_idx))

        # Shift a live mob.
        live_list = sorted(live)
        shift_idx = draw(st.sampled_from(live_list))
        options.append(
            st.builds(
                lambda dx, dy: ShiftCmd(mob_idx=shift_idx, dx=dx, dy=dy),
                _shift_float,
                _shift_float,
            )
        )

        # Transform between two live mobs.
        if allow_transform and len(live) >= 2:
            pair = draw(
                st.lists(
                    st.sampled_from(live_list), min_size=2, max_size=2, unique=True
                )
            )
            options.append(st.just(TransformCmd(src_idx=pair[0], tgt_idx=pair[1])))

        # FadeOut a live mob.
        if allow_fadeout:
            fo_idx = draw(st.sampled_from(live_list))
            options.append(st.just(FadeOutCmd(mob_idx=fo_idx)))

        # Updater-driven play().
        if allow_updaters:
            up_idx = draw(st.sampled_from(live_list))
            options.append(
                st.builds(
                    lambda v, rt: UpdaterCmd(mob_idx=up_idx, end_value=v, run_time=rt),
                    st.floats(0.1, 3.0, allow_nan=False, allow_infinity=False),
                    st.floats(0.1, 0.5, allow_nan=False, allow_infinity=False),
                )
            )

        # Animate a submobject of a live arrow directly.
        if live_arrows:
            arrow_idx = draw(st.sampled_from(sorted(live_arrows)))
            options.append(
                st.builds(
                    lambda dx, dy: AnimateSubmobCmd(mob_idx=arrow_idx, dx=dx, dy=dy),
                    _shift_float,
                    _shift_float,
                )
            )

        chosen = draw(st.one_of(*options))
        commands.append(chosen)

        if isinstance(chosen, FadeOutCmd):
            live.discard(chosen.mob_idx)
            live_arrows.discard(chosen.mob_idx)
        elif isinstance(chosen, (GrowArrowCmd,)) and isinstance(
            mob_specs[chosen.mob_idx], ArrowSpec
        ):
            live.add(chosen.mob_idx)
            live_arrows.add(chosen.mob_idx)

    return mob_specs, commands


# ---------------------------------------------------------------------------
# Instantiation helpers
# ---------------------------------------------------------------------------


def _instantiate(spec: MobjectSpec):
    """Create a fresh live Manim mobject from a spec."""
    from manim import Arrow, Circle, Dot, Square, VGroup

    if isinstance(spec, CircleSpec):
        return Circle(radius=spec.radius, fill_opacity=spec.fill_opacity)
    if isinstance(spec, SquareSpec):
        return Square(side_length=spec.side_length)
    if isinstance(spec, DotSpec):
        return Dot()
    if isinstance(spec, VGroupSpec):
        return VGroup(*[_instantiate(c) for c in spec.children])
    if isinstance(spec, ArrowSpec):
        return Arrow(buff=0)
    msg = f"Unknown MobjectSpec type: {type(spec)}"
    raise TypeError(msg)


def _execute(self, mobs: list, cmd: CommandSpec) -> None:
    """Execute a single command against a live scene."""
    from manim import Create, FadeIn, FadeOut, GrowArrow, Transform, ValueTracker

    if isinstance(cmd, CreateCmd):
        self.play(Create(mobs[cmd.mob_idx]))
    elif isinstance(cmd, FadeInCmd):
        self.play(FadeIn(mobs[cmd.mob_idx]))
    elif isinstance(cmd, TransformCmd):
        self.play(Transform(mobs[cmd.src_idx], mobs[cmd.tgt_idx]))
    elif isinstance(cmd, ShiftCmd):
        self.play(mobs[cmd.mob_idx].animate.shift((cmd.dx, cmd.dy, 0)))
    elif isinstance(cmd, FadeOutCmd):
        self.play(FadeOut(mobs[cmd.mob_idx]))
    elif isinstance(cmd, UpdaterCmd):
        vt = ValueTracker(0)
        mob = mobs[cmd.mob_idx]
        mob.add_updater(lambda m: m.move_to((vt.get_value(), 0, 0)))
        self.add(vt)
        self.play(vt.animate.set_value(cmd.end_value), run_time=cmd.run_time)
        mob.clear_updaters()
    elif isinstance(cmd, GrowArrowCmd):
        self.play(GrowArrow(mobs[cmd.mob_idx]))
    elif isinstance(cmd, AnimateSubmobCmd):
        self.play(mobs[cmd.mob_idx].submobjects[-1].animate.shift((cmd.dx, cmd.dy, 0)))
    else:
        msg = f"Unknown CommandSpec type: {type(cmd)}"
        raise TypeError(msg)


# ---------------------------------------------------------------------------
# Scene class factory
# ---------------------------------------------------------------------------


def make_scene_class(
    mob_specs: list[MobjectSpec],
    commands: list[CommandSpec],
    *,
    fps: int = 10,
    camera_move: bool = False,
):
    """Return a ManimWidget subclass whose construct() runs the given script.

    Parameters
    ----------
    camera_move:
        If True, set a non-default camera pose before the first play() so the
        section snapshot reflects a custom camera position.
    """
    from manim_widget.widget import ManimWidget

    def construct(self):
        if camera_move:
            self.camera.set_phi(0.4)
            self.camera.set_theta(-1.2)

        live_mobs = [_instantiate(spec) for spec in mob_specs]
        for cmd in commands:
            _execute(self, live_mobs, cmd)

    return type(
        "GeneratedScene",
        (ManimWidget,),
        {"construct": construct, "_fps": fps},
    )


def run_generated_scene(
    mob_specs: list[MobjectSpec],
    commands: list[CommandSpec],
    *,
    fps: int = 10,
    camera_move: bool = False,
) -> dict:
    """Convenience: build and run a generated scene, return scene_data."""
    cls = make_scene_class(mob_specs, commands, fps=fps, camera_move=camera_move)
    return cls(fps=fps).scene_data
