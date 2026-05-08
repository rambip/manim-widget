from manim import MathTex

from manim_widget import ManimWidget


class MathTexAddOnly(ManimWidget):
    def construct(self):
        tex = MathTex("x=1")
        self.add(tex)
