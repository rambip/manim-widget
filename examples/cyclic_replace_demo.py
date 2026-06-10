import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim import BLUE, Circle, Create, CyclicReplace, GREEN, LEFT, RED, RIGHT
    from manim_widget import ManimWidget


@app.class_definition
class CyclicReplaceDemo(ManimWidget):
    def construct(self):
        c1 = Circle(color=RED, fill_opacity=0.8).shift(LEFT * 2)
        c2 = Circle(color=GREEN, fill_opacity=0.8)
        c3 = Circle(color=BLUE, fill_opacity=0.8).shift(RIGHT * 2)
        self.play(Create(c1), Create(c2), Create(c3))
        self.play(CyclicReplace(c1, c2, c3))
        self.play(CyclicReplace(c1, c2, c3))


@app.cell
def _():
    CyclicReplaceDemo()
    return


def test(runner):
    r = runner.check(CyclicReplaceDemo)
    r.assert_ok()
    assert len(r.scene_ids(0)) == 3


if __name__ == "__main__":
    app.run()
