import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from io import BytesIO
    from urllib.request import urlopen

    import numpy as np
    from PIL import Image
    from manim import FadeIn, ImageMobject, Transform
    from manim_widget import ManimWidget


@app.cell
def _():
    def _gradient(color1, color2, w=64, h=64, vertical=False):
        data = np.zeros((h, w, 3), dtype=np.uint8)
        t = np.linspace(0, 1, h if vertical else w)
        for ch in range(3):
            ramp = (color1[ch] * (1 - t) + color2[ch] * t).astype(np.uint8)
            if vertical:
                data[:, :, ch] = ramp[:, None]
            else:
                data[:, :, ch] = ramp[None, :]
        alpha = np.full((h, w, 1), 255, dtype=np.uint8)
        return np.concatenate([data, alpha], axis=2)

    grad1 = _gradient([255, 255, 255], [0, 100, 255])  # white→blue (horizontal)
    grad2 = _gradient(
        [255, 50, 50], [50, 255, 50], vertical=True
    )  # red→green (vertical)
    return grad1, grad2


@app.cell
def _():
    _url = (
        "https://raw.githubusercontent.com/ManimCommunity/manim/main/logo/cropped.png"
    )
    with urlopen(_url) as _r:
        manim_logo = np.array(Image.open(BytesIO(_r.read())).convert("RGBA"))
    return (manim_logo,)


# grad1, grad2, manim_logo are defined in marimo cells above and injected into
# this class body at runtime. Ruff cannot see cell-scoped names statically, so
# we suppress F821 ("undefined name") on each reference.
@app.class_definition
class ImageTransformDemo(ManimWidget):
    def construct(self):
        # 1. Fade in small white-to-blue gradient
        image = ImageMobject(grad1)  # noqa: F821
        image.height = 1.5
        self.play(FadeIn(image))
        self.wait(0.3)

        # 2. Morph to red-to-green gradient, 2× bigger
        image2 = ImageMobject(grad2)  # noqa: F821
        image2.height = 3
        self.play(Transform(image, image2))
        self.wait(0.3)

        # 3. Rotate 180° + scale down
        image3 = ImageMobject(grad2)  # noqa: F821
        image3.height = 3
        image3.rotate(np.pi)
        image3.scale(0.5)
        self.play(Transform(image, image3))
        self.wait(0.3)

        # 4. Morph to manim logo
        logo = ImageMobject(manim_logo)  # noqa: F821
        logo.width = 6
        self.play(Transform(image, logo))
        self.wait(0.5)

        # 5. Pure translation: same logo shifted right by 3 units
        logo2 = ImageMobject(manim_logo)  # noqa: F821
        logo2.width = 6
        logo2.shift((3, 0, 0))
        self.play(Transform(image, logo2))
        self.wait(0.5)


@app.cell
def _(grad1, grad2, manim_logo):
    scene = ImageTransformDemo()
    scene
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
