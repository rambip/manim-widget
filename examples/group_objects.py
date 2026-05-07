import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    from manim import (
        Circle,
        FadeIn,
        Group,
        RIGHT,
    )
    from manim_widget import patch_tex

    patch_tex()


@app.cell
def _(ManimWidget):
    class GroupTwoObjectsScene(ManimWidget):
        def construct(self):
            c1 = Circle()
            c2 = Circle().shift(RIGHT)
            group = Group(c1, c2)
            self.play(FadeIn(group))

    return (GroupTwoObjectsScene,)


@app.cell
def _(GroupTwoObjectsScene):
    GroupTwoObjectsScene()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
