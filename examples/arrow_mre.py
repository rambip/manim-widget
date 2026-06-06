import marimo

__generated_with = "0.23.0"
app = marimo.App(width="medium")

with app.setup:
    from manim import Arrow, ORIGIN, GrowArrow
    from manim_widget import ManimWidget


@app.class_definition
class ArrowMRE(ManimWidget):
    def construct(self):
        arrow = Arrow(ORIGIN, [2, 0, 0], buff=0, color="#7dd3fc")
        self.play(GrowArrow(arrow))
        self.play(arrow.submobjects[-1].animate.set_color("#ffeb3b"))


@app.cell
def _():
    s = ArrowMRE(fps=10)
    s
    return (s,)


@app.cell
def _(s):
    s.scene_data
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
