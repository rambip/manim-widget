import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns", css_file="style.css")

with app.setup:
    import marimo as mo
    import numpy as np
    from manim import Circle, FadeIn, TAU
    from manim_widget import ManimWidget


@app.class_definition
class PaletteScene(ManimWidget):
    def __init__(self, colors: list[str], **kwargs):
        self._colors = colors
        self.circles = []
        super().__init__(**kwargs)

    def construct(self):
        n = len(self._colors)
        for i, color in enumerate(self._colors):
            angle = i * TAU / n + TAU / 4
            pos = np.array([2.5 * np.cos(angle), 2.5 * np.sin(angle), 0])
            circle = Circle(
                radius=0.75,
                fill_color=color,
                fill_opacity=1.0,
                stroke_width=0,
            )
            circle.move_to(pos)
            self.circles.append(circle)
            self.play(FadeIn(circle), run_time=0.3)

    def set_colors(self, colors: list[str], background_color: str) -> None:
        from manim.utils.color import ManimColor

        for circle, color in zip(self.circles, colors):
            circle.set_fill(color, opacity=1.0)
        self.camera.background_color = ManimColor(background_color)
        self.sync(*self.circles)


@app.cell
def _():
    mo.callout(
        mo.md(
            "**Custom control bar style**: you can set `--mw-controls-bg` in your custom css file to change the color of the widget control bar"
        ),
        "info",
    )
    return


@app.cell
def _():
    PALETTES = {
        "Observable": {
            "background": "#ffffff",
            "colors": [
                "#4269d0",
                "#efb118",
                "#ff725c",
                "#6cc5b0",
                "#3ca951",
                "#ff8ab7",
            ],
        },
        "Tableau": {
            "background": "#f5f5f5",
            "colors": [
                "#1f77b4",
                "#ff7f0e",
                "#2ca02c",
                "#d62728",
                "#9467bd",
                "#8c564b",
            ],
        },
        "Nord": {
            "background": "#2e3440",
            "colors": [
                "#88c0d0",
                "#81a1c1",
                "#5e81ac",
                "#bf616a",
                "#d08770",
                "#ebcb8b",
            ],
        },
        "Solarized": {
            "background": "#002b36",
            "colors": [
                "#268bd2",
                "#2aa198",
                "#859900",
                "#b58900",
                "#cb4b16",
                "#dc322f",
            ],
        },
        "Pastel": {
            "background": "#fef6e4",
            "colors": [
                "#f78c6b",
                "#ffd166",
                "#06d6a0",
                "#118ab2",
                "#ef476f",
                "#073b4c",
            ],
        },
        "Blue": {
            "background": "#0a1628",
            "colors": [
                "#cce5ff",
                "#99caff",
                "#66b0ff",
                "#3395ff",
                "#007bff",
                "#0056b3",
            ],
        },
    }
    palette_dropdown = mo.ui.dropdown(
        options=list(PALETTES.keys()),
        value="Observable",
        label="Color palette",
    )
    palette_dropdown
    return PALETTES, palette_dropdown


@app.cell
def _(PALETTES):
    _p0 = PALETTES["Observable"]
    widget = PaletteScene(
        colors=_p0["colors"], background_color=_p0["background"], fps=15
    )
    return (widget,)


@app.cell
def _(PALETTES, palette_dropdown, widget):
    _p = PALETTES[palette_dropdown.value]
    widget.set_colors(_p["colors"], _p["background"])
    widget
    return


@app.function(hide_code=True)
def test_palette_scene(runner):
    class _TestScene(PaletteScene):
        def __init__(self, **kwargs):
            super().__init__(
                colors=[
                    "#4269d0",
                    "#efb118",
                    "#ff725c",
                    "#6cc5b0",
                    "#3ca951",
                    "#ff8ab7",
                ],
                background_color="#ffffff",
                **kwargs,
            )

    runner.check(_TestScene).assert_ok()


if __name__ == "__main__":
    app.run()
