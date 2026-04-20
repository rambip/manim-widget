# PR #4696: Unconfuse fontsize calculation

**Status:** Open  
**Changes:** +94 / -42 lines across 5 files

## Overview

This PR refactors the font size calculation logic in Manim to make it clearer and more understandable. It addresses issue #4690.

## Key Changes

### 1. `manim/constants.py`
- Adds new constant `DEFAULT_FONT_SIZE_IN_WORLD_SPACE = 0.5` with documentation explaining it's the length of an 'EM' character (like em dash '—') in manim space
- Adds aliases for backwards compatibility: `DEFAULT_FONTSIZE_IN_WORLD_SPACE` and `DEFAULT_FONT_SIZE_IN_WOLRD_SPACE` (typo preserved for compat)
- Redefines `SCALE_FACTOR_PER_FONT_POINT` with clear formula instead of magic number `1/960`, now marked as legacy

### 2. `manim/mobject/text/tex_mobject.py`
- Adds constants `TEX_SVG_UNITS_PER_PT = 1` and `TEX_DEFAULT_FONT_SIZE_PT = 10` with documentation
- Renames `_font_size` → `initial_font_size` for clarity
- Simplifies font size scaling logic with explicit step-by-step comments:
  1. LaTeX outputs SVG in points
  2. Convert to "fontsize"/"EM" units  
  3. Then to world space
- Simplifies `font_size` getter to: `height / initial_height * initial_font_size`

### 3. `manim/mobject/text/text_mobject.py`
- Replaces magic constants `TEXT_MOB_SCALE_FACTOR = 0.05` and `TEXT2SVG_ADJUSTMENT_FACTOR = 4.8` with documented constants
- Adds `PANGO_SVG_UNITS_PER_PT = 4/3` (Pango outputs 4/3 svg units per point)
- Adds `TEXT_FONT_SIZE_PT = 10` (font size used for unscaled SVG rendering)
- Renames `_font_size` → `initial_font_size` consistently
- Rewrites scaling logic with explicit conversion chain comments
- Simplifies `font_size` getter to same formula as tex_mobject

### 4. Tests
- `test_texmobject.py`: Adds test verifying em dash width equals `DEFAULT_FONT_SIZE_IN_WORLD_SPACE`
- `test_text_mobject.py`: Adds similar test for Text class using Arial/Liberation Sans fonts

## Technical Summary

The core insight is that both TeX and Pango render text to SVG, but with different units:
- **TeX**: 1 SVG unit = 1 point (72 DPI)
- **Pango**: 1 SVG unit = 4/3 pixels (1 point = 4/3 px at 72 DPI)

The new code makes the scaling chain explicit:

```
SVG output → pt units → EM/fontsize units → world space
```

This replaces the previous opaque magic numbers with documented conversion factors.

## Benefits

1. **Clarity**: Future contributors can reason about font size calculations
2. **Documentation**: Each constant explains its purpose and origin
3. **Consistency**: Same approach used in both tex_mobject and text_mobject
4. **Testability**: New tests verify the DEFAULT_FONT_SIZE_IN_WORLD_SPACE constant is accurate
