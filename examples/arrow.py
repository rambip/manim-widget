import marimo

__generated_with = "0.13.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import math
    from manim import Arrow, Transform, Rotate, AnimationGroup, GrowArrow, ORIGIN
    from manim_widget import ManimWidget

    return (
        AnimationGroup,
        Arrow,
        GrowArrow,
        ManimWidget,
        Rotate,
        Transform,
        math,
        mo,
        ORIGIN,
    )


@app.cell
def _(AnimationGroup, Arrow, GrowArrow, ManimWidget, Rotate, Transform, math, ORIGIN):
    N = 12
    RADIUS = 2.6
    COLOR = "#7dd3fc"
    STROKE = 3
    TIP_LENGTH = 0.28

    def make_arrow(radius, angle):
        return Arrow(
            ORIGIN,
            [radius * math.cos(angle), radius * math.sin(angle), 0],
            buff=0,
            color=COLOR,
            stroke_width=STROKE,
            tip_length=TIP_LENGTH,
            max_tip_length_to_length_ratio=1,
        )

    class ArrowDance(ManimWidget):
        def construct(self):
            arrows = [make_arrow(RADIUS, 2 * math.pi * i / N) for i in range(N)]

            # Grow one-by-one
            for arrow in arrows:
                self.play(GrowArrow(arrow), run_time=0.32)

            self.wait(0.25)

            # Shift all outward together
            targets = []
            for i, arrow in enumerate(arrows):
                angle = 2 * math.pi * i / N
                t = Arrow(
                    [math.cos(angle), math.sin(angle), 0],
                    [(RADIUS + 1) * math.cos(angle), (RADIUS + 1) * math.sin(angle), 0],
                    buff=0,
                    color=COLOR,
                    stroke_width=STROKE,
                    tip_length=TIP_LENGTH,
                    max_tip_length_to_length_ratio=1,
                )
                targets.append(t)
            self.play(*[Transform(a, t, run_time=1.2) for a, t in zip(arrows, targets)])

            # Scale down together
            self.play(*[arrow.animate.scale(0.5) for arrow in arrows], run_time=0.9)

            # Tip recolor staggered
            self.play(
                AnimationGroup(
                    *[
                        arrow.submobjects[-1].animate.set_color("#ffeb3b")
                        for arrow in arrows
                    ],
                    lag_ratio=0.33,
                    run_time=0.15 * N,
                )
            )

            # Rotate 180° staggered
            self.play(
                AnimationGroup(
                    *[Rotate(arrow, math.pi) for arrow in arrows],
                    lag_ratio=0.33,
                    run_time=0.5 * N,
                )
            )

            # Pinwheel: arrange tangentially around perimeter
            chord = 2 * RADIUS * math.sin(math.pi / N)
            pinwheel = []
            for i, arrow in enumerate(arrows):
                angle = 2 * math.pi * i / N
                cx, cy = RADIUS * math.cos(angle), RADIUS * math.sin(angle)
                tx, ty = -math.sin(angle), math.cos(angle)
                half = chord / 2
                t = Arrow(
                    [cx - half * tx, cy - half * ty, 0],
                    [cx + half * tx, cy + half * ty, 0],
                    buff=0,
                    color=COLOR,
                    stroke_width=STROKE,
                    tip_length=TIP_LENGTH,
                    max_tip_length_to_length_ratio=1,
                )
                pinwheel.append(Transform(arrow, t, run_time=0.6))
            self.play(*pinwheel)

    ArrowDance(fps=15)
