import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    from io import BytesIO
    from urllib.request import urlopen

    import numpy as np
    from PIL import Image
    from manim import (
        ImageMobject,
        Rectangle,
        VGroup,
        RIGHT,
        LEFT,
        UP,
        OUT,
        IN,
        PI,
        FadeIn,
        Create,
        GrowArrow,
        Arrow,
    )

    from manim_widget import ManimWidget


@app.cell
def _():
    IMAGE_URL = "https://storage.googleapis.com/kaggle-datasets-images/6175990/10028340/a0b959a027a7dd839dccfd847af56177/dataset-card.jpg"

    def load_image_array(url: str) -> np.ndarray:
        with urlopen(url) as response:
            data = response.read()
        img = Image.open(BytesIO(data)).convert("RGBA")
        return np.array(img)

    # 3D solids are unsupported; emulate a cuboid with 6 flat rectangles.
    def cnn_block(y_size=2.0, z_size=2.4, x_thickness=0.35):
        style = dict(stroke_opacity=0.85, stroke_width=2)

        # Faces perpendicular to x-axis (YZ planes)
        front = Rectangle(width=z_size, height=y_size, fill_color="#60A5FA", fill_opacity=0.40, **style)
        front.rotate(PI / 2, axis=UP)
        front.shift(RIGHT * (x_thickness / 2))

        back = Rectangle(width=z_size, height=y_size, fill_color="#1D4ED8", fill_opacity=0.22, **style)
        back.rotate(PI / 2, axis=UP)
        back.shift(LEFT * (x_thickness / 2))

        # Faces perpendicular to z-axis (XY planes)
        left_face = Rectangle(width=x_thickness, height=y_size, fill_color="#3B82F6", fill_opacity=0.32, **style)
        left_face.shift(IN * (z_size / 2))

        right_face = Rectangle(width=x_thickness, height=y_size, fill_color="#3B82F6", fill_opacity=0.50, **style)
        right_face.shift(OUT * (z_size / 2))

        # Faces perpendicular to y-axis (XZ planes)
        top = Rectangle(width=x_thickness, height=z_size, fill_color="#93C5FD", fill_opacity=0.45, **style)
        top.rotate(PI / 2, axis=RIGHT)
        top.shift(UP * (y_size / 2))

        bottom = Rectangle(width=x_thickness, height=z_size, fill_color="#1E40AF", fill_opacity=0.18, **style)
        bottom.rotate(PI / 2, axis=RIGHT)
        bottom.shift(UP * (-y_size / 2))

        block = VGroup(back, bottom, left_face, right_face, top, front)
        return block

    class ZYImageCNN(ManimWidget):
        def construct(self):
            self.camera.phi = 1.5
            self.camera.theta = -0.8
            self.camera.distance = 10
            img = ImageMobject(load_image_array(IMAGE_URL))
            img.height = 3.0
            img.apply_matrix([
                [0, 0, 1],
                [1, 0, 0],
                [0, 1, 0],
            ])

            block1 = cnn_block(y_size=2.2, z_size=2.8, x_thickness=0.28)
            block1.next_to(img, RIGHT, buff=2.0)

            block2 = cnn_block(y_size=1.8, z_size=2.0, x_thickness=0.20)
            block2.next_to(block1, RIGHT, buff=2)

            a1 = Arrow(img.get_right(), block1.get_left(), buff=0.12, stroke_width=4).rotate(PI/2, RIGHT)
            a2 = Arrow(block1.get_right(), block2.get_left(), buff=0.12, stroke_width=4).rotate(PI/2, RIGHT)

            self.add(img)
            self.play(Create(block1), GrowArrow(a1))
            self.play(Create(block2), GrowArrow(a2))
            self.play(img.animate.shift(RIGHT*2))
            self.play(img.animate.shift(RIGHT*2))

    return (ZYImageCNN,)


@app.cell
def _(ZYImageCNN):
    scene = ZYImageCNN()
    scene
    return (scene,)


@app.cell
def _(scene):
    scene.scene_data
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
