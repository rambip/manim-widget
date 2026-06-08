"""Animation compatibility helpers for the capture renderer.

Some Manim animations cannot execute their Python-side interpolation loop when
the widget renderer runs a scene dry. The canonical example is
``Transform(img_a, img_b)`` where the two ImageMobjects have different pixel
array shapes: Manim asserts equal shapes before blending, so ``begin()``
raises immediately.

The widget renderer does not need Python-side interpolation — the JS player
replays every animation from the captured start/end states. When
``begin()`` fails the renderer falls back to ``force_end_state``, which
directly copies the target mobject's geometry and pixel data onto the source.

This is intentionally *not* a silent swallow: the caller is expected to emit
a ``UserWarning`` so users know their scene would not play back in plain Manim.
"""

from __future__ import annotations

import numpy as np
from manim.animation.animation import Animation
from manim.mobject.types.image_mobject import AbstractImageMobject


def force_end_state(anim: Animation) -> None:
    """Copy the animation's target state directly onto its source mobject.

    Replaces the ``begin() → interpolate(t) → finish()`` lifecycle for
    animations that cannot interpolate Python-side. After this call the source
    mobject reflects the geometry and pixel data of the target, making
    subsequent serialisations correct.

    ``AbstractImageMobject`` (Manim's base for ``ImageMobject`` and
    ``ImageMobjectFromCamera``) carries a ``pixel_array`` that is copied in
    addition to ``points``. No other mobject types need special handling
    because geometry is fully described by ``points``.

    Raises
    ------
    AttributeError
        If *anim* does not carry ``mobject`` or ``target_mobject`` — i.e. it
        is not a transform-style animation. Callers should guard with
        ``hasattr`` or catch this explicitly if needed.
    """
    src = anim.mobject
    tgt = anim.target_mobject  # raises AttributeError for non-transform anims

    src.points = (
        tgt.points.copy() if hasattr(tgt.points, "copy") else np.array(tgt.points)
    )

    if isinstance(src, AbstractImageMobject) and isinstance(tgt, AbstractImageMobject):
        src.pixel_array = tgt.pixel_array.copy()
