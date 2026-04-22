# ManimWidget Examples

Marimo notebooks demonstrating the ManimWidget capabilities.

## Running the Examples

```bash
# From the project root
uv run marimo examples/swap_demo.py
uv run marimo examples/cyclic_replace_demo.py
```

## Examples

### swap_demo.py

Demonstrates the `Swap` animation with three colored circles:
- Three circles (red, green, blue) at different positions
- Swap animations: 1↔2, 2↔3, 1↔3

### cyclic_replace_demo.py

Demonstrates the `CyclicReplace` animation with three colored circles:
- Three circles (red, green, blue) at different positions
- Each circle moves to the next position in sequence
- Two cycles to show the pattern continuing
