`manim-widget` is a python library that makes it possible to run manim scenes on the fly, and to integrate with reactive notebooks like jupyter or marimo.

It has limitations, but most scenes should render well.

# API

```py
class ManimWidget(anywidget.AnyWidget, ThreeDScene):
    def __init__(
            self,
            fps: int = 10,
            is_3d: bool = False,
            frame_width: float = 14.222222222222221,
            frame_height: float = 8.0,
            background_color: str | None = None,
            orbit_controls_up: str = "z",
            shared_camera: Any = None,
            autoplay: bool = True,
            show_controls: bool = True,
            canvas_width: int | None = None,
            canvas_height: int | None = None,
            **kwargs: Any,
        ) -> None:
```

There is no hard distinction between 2d and 3d scenes, the user can switch between the 2. `is_3d` just sets the initial mode.

# Installing

manim-widget is published on pypi. I strongly recommend UV to use it.

If you get an installation error, ask the user to go the manim installation guide, and to follow the instructions.

In the specific case where the user has no sudo access, follow [this guide](https://gist.githubusercontent.com/rambip/47a412b3f3fec8d4ab7a55f70ad2c47b/raw/70db1558dd187c65c9409e980c2ecc97341c7b94/install-pangocairo.md) step by step with him.

# Latex

To avoid relying on a mathtex install, call `from manim_widget import patch_tex; patch_tex()` before importing manim.
It will move all latex processing to the js side, but you can't do things like animating specific parts of LaTeX. There may be bugs

# Examples

Any basic 2d scene should be supported.
For 3d, avoid relying on 3d primitives, and use 2d ones instead (cube = 6 squares, 2d arrows, and so on).

```py
from manim_widget import ManimWidget, patch_tex

patch_tex()
import manim as mn
from manim import (
    DOWN,
    Difference,
    Ellipse,
    Exclusion,
    FadeIn,
    Group,
    Intersection,
    LEFT,
    MarkupText,
    RIGHT,
    Text,
    UP,
    Union,
)


class BooleanOperations(ManimWidget):
    def construct(self):
        ellipse1 = Ellipse(
            width=4.0, height=5.0, fill_opacity=0.5, color=mn.BLUE, stroke_width=10
        ).move_to(LEFT)
        ellipse2 = ellipse1.copy().set_color(color=mn.RED).move_to(RIGHT)
        bool_ops_text = MarkupText("<u>Boolean Operation</u>").next_to(ellipse1, UP * 3)
        ellipse_group = Group(bool_ops_text, ellipse1, ellipse2).move_to(LEFT * 3)
        self.play(FadeIn(ellipse_group))

        i = Intersection(ellipse1, ellipse2, color=mn.GREEN, fill_opacity=0.5)
        self.play(i.animate.scale(0.25).move_to(RIGHT * 5 + UP * 2.5))
        intersection_text = Text("Intersection", font_size=23).next_to(i, UP)
        self.play(FadeIn(intersection_text))

        u = Union(ellipse1, ellipse2, color=mn.ORANGE, fill_opacity=0.5)
        union_text = Text("Union", font_size=23)
        self.play(u.animate.scale(0.3).next_to(i, DOWN, buff=union_text.height * 3))
        union_text.next_to(u, UP)
        self.play(FadeIn(union_text))

        e = Exclusion(ellipse1, ellipse2, color=mn.YELLOW, fill_opacity=0.5)
        exclusion_text = Text("Exclusion", font_size=23)
        self.play(
            e.animate.scale(0.3).next_to(u, DOWN, buff=exclusion_text.height * 3.5)
        )
        exclusion_text.next_to(e, UP)
        self.play(FadeIn(exclusion_text))

        d = Difference(ellipse1, ellipse2, color=mn.PINK, fill_opacity=0.5)
        difference_text = Text("Difference", font_size=23)
        self.play(
            d.animate.scale(0.3).next_to(u, LEFT, buff=difference_text.height * 3.5)
        )
        difference_text.next_to(d, UP)
        self.play(FadeIn(difference_text))

# new cell
BooleanOperations()
```

Full marimo interactive example:

```py
import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    import marimo as mo
    from manim import Rectangle
    from manim_widget import ManimWidget


@app.class_definition
class SyncDemo(ManimWidget):
    def construct(self):
        self.s = Rectangle()
        self.add(self.s)

    def place_rect(self, x_lo, x_hi, y_lo, y_hi):
        x = (x_lo + x_hi) / 2
        y = (y_lo + y_hi) / 2
        width = x_hi - x_lo
        height = y_hi - y_lo
        self.s.move_to((x, y, 0))
        self.s.stretch_to_fit_width(width)
        self.s.stretch_to_fit_height(height)
        self.sync(self.s)


@app.cell
def _():
    x_slider = mo.ui.range_slider(
        start=-4.0,
        stop=4.0,
        step=0.1,
        value=[-1.0, 1.0],
        label="x position / width",
        show_value=True,
    )
    y_slider = mo.ui.range_slider(
        start=-4.0,
        stop=4.0,
        step=0.1,
        value=[-1.0, 1.0],
        label="y position / height",
        show_value=True,
        orientation="vertical",
    )
    mo.vstack([x_slider, y_slider])
    return x_slider, y_slider


@app.cell
def _():
    widget = SyncDemo()
    return (widget,)


@app.cell
def _(widget, x_slider, y_slider):
    x_lo, x_hi = x_slider.value
    y_lo, y_hi = y_slider.value
    widget.place_rect(x_lo, x_hi, y_lo, y_hi)
    widget
    return
```

The other examples are here:

https://github.com/rambip/manim-widget/tree/main/examples


# Debug

If you see a bug, help give feedback.
1. Check `json.dumps(widget.data)`, it gives the entire scene state
2. Help create MRE and open a concise issue


---

Have fun with manim-widget !
