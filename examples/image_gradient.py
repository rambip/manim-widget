import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    import numpy as np
    import marimo as mo
    from manim import FadeIn, ImageMobject
    from manim_widget import ManimWidget


@app.class_definition
class ImageGradientDemo(ManimWidget):
    def construct(self):
        h, w = 96, 128
        data = np.zeros((h, w, 4), dtype=np.uint8)

        # RGBA gradient: red increases left->right, green increases top->bottom
        data[..., 0] = np.tile(np.linspace(20, 255, w, dtype=np.uint8), (h, 1))
        data[..., 1] = np.tile(np.linspace(20, 255, h, dtype=np.uint8)[:, None], (1, w))
        data[..., 2] = 140
        data[..., 3] = 255

        img = ImageMobject(data)
        img.height = 3.2

        #self.add((img))
        self.play(FadeIn(img))
        #self.play(img.animate.scale(1.35))


@app.cell
def _():
    scene = ImageGradientDemo()
    scene
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
