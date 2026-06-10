import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim import BLUE, Circle, Create, GREEN, LEFT, RED, RIGHT, Swap
    from manim_widget import ManimWidget


@app.class_definition
class SwapDemo(ManimWidget):
    def construct(self):
        c1 = Circle(color=RED, fill_opacity=0.8).shift(LEFT * 3)
        c2 = Circle(color=GREEN, fill_opacity=0.8)
        c3 = Circle(color=BLUE, fill_opacity=0.8).shift(RIGHT * 3)
        self.play(Create(c1), Create(c2), Create(c3))
        self.play(Swap(c1, c2))
        self.play(Swap(c2, c3))
        self.play(Swap(c1, c3))


@app.cell
def _():
    SwapDemo()
    return


@app.function(hide_code=True)
def test(runner):
    runner.check(SwapDemo).assert_ok()


if __name__ == "__main__":
    app.run()
