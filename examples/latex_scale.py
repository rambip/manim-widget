import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")


with app.setup:
    import manim as mn
    import marimo as mo
    from manim_widget import ManimWidget, patch_tex
    patch_tex()
    from manim import MathTex, Create, Transform, NumberPlane, LEFT, RIGHT, UP, DOWN


@app.cell
def _(ManimWidget):
    class LatexScale(ManimWidget):
        def construct(self):
            # Grid to see coordinates
            grid = NumberPlane()
            self.add(grid)
            
            # Start with a zero glyph
            zero = MathTex("0", stroke_opacity=1, fill_opacity=1)
            self.play(Create(zero))
            
            # Transform to 3x bigger
            big_zero = MathTex("0", stroke_opacity=1, fill_opacity=1, font_size=144)
            self.play(Transform(zero, big_zero))

    return (LatexScale,)


@app.cell
def _(LatexScale):
    LatexScale()
    return


if __name__ == "__main__":
    app.run()
