import numpy as np
from manim import ORIGIN, RIGHT, UP, VMobject


class PatchedMathTex(VMobject):
    def __init__(
        self,
        *tex_strings: str,
        font_size: float = 48,
        arg_separator: str = " ",
        substrings_to_isolate=None,
        tex_to_color_map=None,
        tex_environment: str | None = "align*",
        tex_template=None,
        **kwargs,
    ):
        self.tex_string = arg_separator.join(tex_strings)
        self.font_size = font_size
        VMobject.__init__(self, **kwargs)
        self.points = np.array(
            [
                np.array(ORIGIN),
                np.array(RIGHT),
                np.array(UP),
                np.array(RIGHT) + np.array(UP),
            ],
            dtype=np.float64,
        )

    def interpolate_color(self, mobject1, mobject2, alpha):
        pass

    def get_tex_string(self) -> str:
        return self.tex_string

    def __getitem__(self, key):
        raise NotImplementedError("Tex parts not supported")

    def get_part_by_tex(self, tex, **kwargs):
        raise NotImplementedError("Tex parts not supported")


class PatchedTex(PatchedMathTex):
    pass


_original_classes = {}


def patch_tex():
    import manim

    _original_classes["MathTex"] = manim.MathTex
    _original_classes["Tex"] = manim.Tex
    manim.MathTex = PatchedMathTex
    manim.Tex = PatchedTex
