import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim import (
        BLUE,
        GREEN,
        ORANGE,
        PURPLE,
        RED,
        RIGHT,
        UP,
        Circle,
        Create,
        CyclicReplace,
        FadeIn,
        FadeOut,
        Swap,
        Text,
    )
    from manim_widget import ManimWidget


@app.class_definition
class PermutationDemo(ManimWidget):
    def construct(self):
        colors = [RED, ORANGE, GREEN, BLUE, PURPLE]
        circles = [
            Circle(radius=0.5, color=c, fill_opacity=0.8).shift(RIGHT * (i - 2) * 1.4)
            for i, c in enumerate(colors)
        ]

        def show(text, anim):
            label = Text(text, font_size=28).shift(UP * 2.2)
            self.play(FadeIn(label))
            self.play(anim)
            self.play(FadeOut(label))

        self.play(*[Create(c) for c in circles])

        show("0 ↔ 4", Swap(circles[0], circles[4]))
        show("1 ↔ 3", Swap(circles[1], circles[3]))
        show("0→1→2→3→4", CyclicReplace(*circles))
        show("0→1→2→3→4", CyclicReplace(*circles))
        show("0→1→2→3→4", CyclicReplace(*circles))


@app.cell
def _():
    PermutationDemo()
    return


@app.function(hide_code=True)
def test_permutation_demo(runner):
    r = runner.check(PermutationDemo)
    r.assert_ok()
    assert len(r.scene_ids(0)) == 5


if __name__ == "__main__":
    app.run()
