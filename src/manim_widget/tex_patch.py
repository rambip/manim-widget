import numpy as np
from manim import DOWN, LEFT, Mobject, RIGHT, UP


class PatchedMathTex(Mobject):
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

        # Mobject does not accept many MathTex styling kwargs directly.
        color = kwargs.pop("color", None) or kwargs.pop("fill_color", None)
        _ = kwargs.pop("fill_opacity", None)
        _ = kwargs.pop("stroke_opacity", None)

        Mobject.__init__(self)
        if color is not None and hasattr(self, "set_color"):
            self.set_color(color)

        scale = float(font_size) / 48.0
        self.points = np.array(
            [
                (np.array(LEFT) + np.array(UP)) * scale,
                (np.array(RIGHT) + np.array(UP)) * scale,
                (np.array(RIGHT) + np.array(DOWN)) * scale,
                (np.array(LEFT) + np.array(DOWN)) * scale,
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
