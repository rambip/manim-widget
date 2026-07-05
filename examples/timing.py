import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim import (
        BLACK,
        BLUE,
        DOWN,
        GREEN,
        LEFT,
        ORANGE,
        PURPLE,
        RED,
        RIGHT,
        WHITE,
        YELLOW,
        AnimationGroup,
        Create,
        Dot,
        Line,
        Rectangle,
        Text,
        exponential_decay,
        lingering,
        running_start,
        slow_into,
        smooth,
        there_and_back_with_pause,
    )
    from manim_widget import ManimWidget

    def running_start_minus_02(t):
        return running_start(t, -0.2)

    running_start_minus_02.__name__ = "running_start"
    running_start_minus_02._manim_widget_rate_func_params = {"pull_factor": -0.2}

    def there_and_back_with_pause_default(t):
        return there_and_back_with_pause(t)

    there_and_back_with_pause_default.__name__ = "there_and_back_with_pause"

    def exponential_decay_default(t):
        return exponential_decay(t)

    exponential_decay_default.__name__ = "exponential_decay"


@app.class_definition
class RateFunctionComparison(ManimWidget):
    def construct(self):
        self.camera.background_color = BLACK

        rate_functions = [
            ("smooth", smooth, BLUE),
            ("runningStart", running_start_minus_02, RED),
            ("thereAndBackWithPause", there_and_back_with_pause_default, GREEN),
            ("lingering", lingering, YELLOW),
            ("exponentialDecay", exponential_decay_default, PURPLE),
            ("slowInto", slow_into, ORANGE),
        ]

        top_y = 2.4
        row_spacing = 0.85
        start_x = -1.5
        shift_distance = 5.5
        shift_direction = shift_distance * RIGHT

        dots = []
        for i, (name, _rate_func, color) in enumerate(rate_functions):
            y = top_y - i * row_spacing
            track_line = Line(
                start=[start_x, y, 0],
                end=[start_x + shift_distance, y, 0],
                color="#333333",
                stroke_width=1,
            )
            label = Text(name, font_size=28, color=WHITE)
            label.next_to(track_line, LEFT, buff=0.2)
            dot = Dot(point=[start_x, y, 0], radius=0.1, color=color)

            self.add(label, track_line, dot)
            dots.append(dot)

        animations = [
            dot.animate(rate_func=rate_func, run_time=3).shift(shift_direction)
            for dot, (_name, rate_func, _color) in zip(dots, rate_functions)
        ]
        self.play(AnimationGroup(*animations))


@app.cell
def _():
    RateFunctionComparison(fps=20)
    return


@app.class_definition
class DelayedRectangleTiming(ManimWidget):
    def construct(self):
        self.camera.background_color = BLACK

        colors = [BLUE, RED, GREEN, YELLOW, PURPLE, ORANGE]
        bottom_y = -2.7
        initial_height = 0.18
        anchor = [0, bottom_y, 0]
        bars = []
        for i in range(12):
            x = -3.0 + i * 0.55
            bar = Rectangle(
                width=0.18,
                height=initial_height,
                color=colors[i % len(colors)],
                fill_color=colors[i % len(colors)],
                fill_opacity=0.85,
                stroke_width=1,
            )
            bar.move_to([x, bottom_y + initial_height / 2, 0])
            bars.append(bar)

        self.play(
            AnimationGroup(
                *[Create(bar, run_time=0.35) for bar in bars],
                lag_ratio=0.08,
                run_time=1.2,
            )
        )

        def grow(bar, height, rate_func, run_time):
            return (
                bar.animate(run_time=run_time, rate_func=rate_func)
                .stretch_to_fit_height(height)
                .align_to(anchor, DOWN)
            )

        # Phase 1: smooth, with slow bass-like bars and quick transient bars.
        self.play(
            *[
                grow(
                    bar,
                    1.2 + (i % 4) * 0.6,
                    smooth,
                    1.8 if i % 3 == 0 else 0.45,
                )
                for i, bar in enumerate(bars)
            ]
        )

        # Phase 2: running start, all bars share the same rate function.
        self.play(
            AnimationGroup(
                *[
                    grow(
                        bar,
                        4.8 - (i % 3) * 0.45,
                        running_start_minus_02,
                        1.6,
                    )
                    for i, bar in enumerate(bars)
                ],
                lag_ratio=0.0,
                run_time=1.6,
            )
        )

        # Phase 3: one-by-one updates, like samples arriving serially.
        for i, bar in enumerate(bars):
            self.play(grow(bar, 1.0 + (i % 5) * 0.45, lingering, 0.16))

        # Phase 4: there-and-back pause, staggered AnimationGroup wave.
        self.play(
            AnimationGroup(
                *[
                    grow(
                        bar,
                        4.2 if i % 2 == 0 else 2.0,
                        there_and_back_with_pause_default,
                        0.9,
                    )
                    for i, bar in enumerate(bars)
                ],
                lag_ratio=0.12,
                run_time=2.1,
            )
        )


@app.cell
def _():
    DelayedRectangleTiming(fps=20)
    return


@app.function(hide_code=True)
def test(runner):
    runner.check_data(RateFunctionComparison().data).assert_ok()

    delayed = DelayedRectangleTiming()
    runner.check_data(delayed.data).assert_ok()
    timestamped = [
        anim
        for cmd in delayed.data.sections[0].animate_commands()
        for anim in cmd.animations
        if anim.start is not None and anim.end is not None
    ]
    assert timestamped
    assert any(anim.start > 0 for anim in timestamped)


if __name__ == "__main__":
    app.run()
