from manim import (
    BLUE,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    Circle,
    Create,
    Rotate,
    Square,
    Transform,
    Triangle,
    VGroup,
)
from manim.animation.transform import ReplacementTransform

from manim_widget import ManimWidget


class DebugScene(ManimWidget):
    def construct(self):
        self.camera.background_color = "#ece6e2"
        logo_green = "#87c2a5"
        logo_blue = "#525893"
        logo_red = "#e07a5f"
        circle = Circle(color=logo_green, fill_opacity=1).shift(LEFT)
        square = Square(color=logo_blue, fill_opacity=1).shift(UP)
        triangle = Triangle(color=logo_red, fill_opacity=1).shift(RIGHT)
        logo = VGroup(circle, square, triangle)
        logo.move_to(ORIGIN)
        self.play(Create(logo))
        self.play(ReplacementTransform(logo, logo.copy().scale(2).shift(LEFT)))
