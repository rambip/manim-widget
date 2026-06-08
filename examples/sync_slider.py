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


if __name__ == "__main__":
    app.run()
