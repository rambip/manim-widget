import numpy as np
from manim import DOWN, LEFT, Mobject, RIGHT, UP, VMobject


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

        # Mobject does not accept many MathTex styling kwargs directly.
        color = kwargs.pop("color", None) or kwargs.pop("fill_color", None)
        fill_opacity = kwargs.pop("fill_opacity", 1.0)
        stroke_opacity = kwargs.pop("stroke_opacity", 1.0)
        stroke_width = kwargs.pop("stroke_width", 0.0)

        # VMobject.init_colors() is called during Mobject.__init__ via MRO and
        # expects VMobject style attributes to already exist.
        self.fill_opacity = float(fill_opacity)
        self.stroke_opacity = float(stroke_opacity)
        self.stroke_width = float(stroke_width)
        self.background_stroke_color = "#000000"
        self.background_stroke_opacity = 1.0
        self.background_stroke_width = 0.0
        self.sheen_factor = 0.0
        self.sheen_direction = np.array([-1.0, 1.0, 0.0])
        self.n_points_per_cubic_curve = 4
        self._bezier_t_values = np.linspace(0, 1, self.n_points_per_cubic_curve)

        # Must be a VMobject subtype so it can be added to VGroup, but avoid
        # VMobject.__init__() heavy setup/normalization here.
        Mobject.__init__(self)

        # Set color after base Mobject init so submobjects container exists.
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

    def get_points_defining_boundary(self):
        return self.points

    def __getitem__(self, key):
        raise NotImplementedError("Tex parts not supported")

    def get_part_by_tex(self, tex, **kwargs):
        raise NotImplementedError("Tex parts not supported")


class PatchedTex(PatchedMathTex):
    pass


_original_classes = {}


def _patched_brace_get_text(self, *text, **kwargs):
    from manim import Text

    return Text(" ".join(text)).next_to(self, DOWN)


def _patched_brace_get_tex(self, *tex, **kwargs):
    mob = PatchedMathTex(*tex)
    mob.next_to(self, DOWN)
    return mob


def patch_tex():
    import manim

    _original_classes["MathTex"] = manim.MathTex
    _original_classes["Tex"] = manim.Tex
    manim.MathTex = PatchedMathTex
    manim.Tex = PatchedTex

    from manim.mobject.svg.brace import Brace

    Brace.get_text = _patched_brace_get_text
    Brace.get_tex = _patched_brace_get_tex
