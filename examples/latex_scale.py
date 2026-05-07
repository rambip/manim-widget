import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from manim_widget import ManimWidget, patch_tex

    patch_tex()
    from manim import MathTex


@app.class_definition
class LatexScale(ManimWidget):
    def construct(self):
        # Grid to see coordinates
        # grid = NumberPlane()
        # self.add(grid)

        # Start with a zero glyph
        zero = MathTex("0", stroke_opacity=1, fill_opacity=1)
        self.add(zero)
        print(zero.get_center())
        self.add(zero.scale(2))

        # Transform to 3x bigger
        # big_zero = MathTex("0", stroke_opacity=1, fill_opacity=1, font_size=144)
        # self.play(Create(zero.scale(2)))


@app.cell
def _():
    LatexScale()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
