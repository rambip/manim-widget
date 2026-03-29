import marimo

__generated_with = "0.21.1"
app = marimo.App(width="columns")


@app.cell
def _():
    from manim_widget import ManimWidget
    import manim as mn

    return ManimWidget, mn


@app.cell
def _(ManimWidget, mn):
    class Foo(ManimWidget):
        def construct(self):
            circle = mn.Circle()  # create a circle
            circle.set_fill(mn.PINK, opacity=0.5)  # set the color and transparency

            square = mn.Square()  # create a square
            square.set_fill(mn.BLUE, opacity=0.5)  # set the color and transparency

            square.next_to(circle, mn.RIGHT, buff=0.5)  # set the position
            self.square = square
            self.play(mn.Create(circle), mn.Create(square))  # show the shapes on screen


    return (Foo,)


@app.cell
def _(Foo):
    foo = Foo()
    foo
    return


if __name__ == "__main__":
    app.run()
