from __future__ import annotations


class _VTKey(tuple):
    """State key for ValueTracker: (value,)."""

    __slots__ = ()

    def __new__(cls, value: float) -> "_VTKey":
        return super().__new__(cls, (value,))

    @property
    def value(self) -> float:
        return self[0]


class _MathTexKey(tuple):
    """State key for PatchedMathTex: (latex, pts, color)."""

    __slots__ = ()

    def __new__(cls, latex: str, pts: tuple, color: str | None) -> "_MathTexKey":
        return super().__new__(cls, (latex, pts, color))

    @property
    def latex(self) -> str:
        return self[0]

    @property
    def pts(self) -> tuple:
        return self[1]

    @property
    def color(self) -> str | None:
        return self[2]


class _ImgKey(tuple):
    """State key for ImageMobject derived state: (content_ref, corners)."""

    __slots__ = ()

    def __new__(cls, content_ref: int, corners: tuple) -> "_ImgKey":
        return super().__new__(cls, (content_ref, corners))

    @property
    def content_ref(self) -> int:
        return self[0]

    @property
    def corners(self) -> tuple:
        return self[1]


class _PMobjectKey(tuple):
    """State key for a point-cloud PMobject: (points, colors, opacities, stroke_width).

    All three are hashable tuples parallel by index; a single Point is just a
    one-element cloud.
    """

    __slots__ = ()

    def __new__(
        cls,
        points: tuple,
        colors: tuple | None,
        opacities: tuple | None,
        stroke_width: float | None,
    ) -> "_PMobjectKey":
        return super().__new__(cls, (points, colors, opacities, stroke_width))

    @property
    def points(self) -> tuple:
        return self[0]

    @property
    def colors(self) -> tuple | None:
        return self[1]

    @property
    def opacities(self) -> tuple | None:
        return self[2]

    @property
    def stroke_width(self) -> float | None:
        return self[3]


class _GroupKey(tuple):
    """State key for a group: (child_refs,)."""

    __slots__ = ()

    def __new__(cls, child_refs: tuple) -> "_GroupKey":
        return super().__new__(cls, (child_refs,))

    @property
    def child_refs(self) -> tuple:
        return self[0]


class _VMobKey(tuple):
    """State key for plain VMobject."""

    __slots__ = ()

    def __new__(
        cls,
        contours: tuple,
        holes: tuple,
        fill_color: str | None,
        stroke_color: str | None,
        fill_opacity: float | None,
        stroke_width: float | None,
        stroke_opacity: float | None,
        z_index: float | None,
    ) -> "_VMobKey":
        return super().__new__(
            cls,
            (
                contours,
                holes,
                fill_color,
                stroke_color,
                fill_opacity,
                stroke_width,
                stroke_opacity,
                z_index,
            ),
        )

    @property
    def contours(self) -> tuple:
        return self[0]

    @property
    def holes(self) -> tuple:
        return self[1]

    @property
    def fill_color(self) -> str | None:
        return self[2]

    @property
    def stroke_color(self) -> str | None:
        return self[3]

    @property
    def fill_opacity(self) -> float | None:
        return self[4]

    @property
    def stroke_width(self) -> float | None:
        return self[5]

    @property
    def stroke_opacity(self) -> float | None:
        return self[6]

    @property
    def z_index(self) -> float | None:
        return self[7]
