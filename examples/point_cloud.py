import marimo

__generated_with = "0.23.0"
app = marimo.App(width="columns")

with app.setup:
    import numpy as np
    from manim_widget import ManimWidget, patch_tex

    patch_tex()
    from manim import (
        BLUE,
        FadeIn,
        GRAY,
        GREEN,
        Line,
        PMobject,
        RED,
        ThreeDAxes,
        Transform,
        VGroup,
        MathTex,
        RIGHT,
        PI,
    )


@app.function
def sample_blobs(centers, n_per, std, rng):
    """Stack ``n_per`` gaussian samples around each center into one (N, 3) array."""
    return np.concatenate(
        [np.asarray(c) + rng.normal(0.0, std, size=(n_per, 3)) for c in centers],
        axis=0,
    )


@app.function
def make_cloud(coords, point_colors):
    """Build a point-cloud PMobject; each point keeps its color (and identity by
    index) so a Transform between two clouds morphs point-to-point."""
    cloud = PMobject()
    for point, color in zip(coords, point_colors):
        cloud.add_points([point], color=color)
    return cloud


@app.function
def edge(a, b):
    """A faint connector line between two cloud points."""
    return Line(a, b, color=GRAY, stroke_width=3)


@app.function
def proximity_edge_animations(coords0, coords1, epsilon):
    """Classify every point pair by whether it is within ``epsilon`` before and
    after the morph, and build the edge mobjects plus their animations.

    Returns ``(start_edges, born_edges, edge_anims, breaking)``:
      - persists (close in both): Transform the edge to follow its endpoints.
      - breaks (close only at start): Transform to the end position while fading
        to opacity 0, then remove — the connection slides apart and vanishes.
      - born (close only at end): Transform from the start position (opacity 0)
        to the end position at full opacity — a new connection slides in.
    """
    start_edges = VGroup()
    born_edges = VGroup()
    edge_anims = []
    breaking = []
    n = len(coords0)
    for i in range(n):
        for j in range(i + 1, n):
            in0 = np.linalg.norm(coords0[i] - coords0[j]) < epsilon
            in1 = np.linalg.norm(coords1[i] - coords1[j]) < epsilon
            if in0 and in1:
                line = edge(coords0[i], coords0[j])
                start_edges.add(line)
                edge_anims.append(Transform(line, edge(coords1[i], coords1[j])))
            elif in0:
                line = edge(coords0[i], coords0[j])
                start_edges.add(line)
                target = edge(coords1[i], coords1[j]).set_opacity(0)
                edge_anims.append(Transform(line, target))
                breaking.append(line)
            elif in1:
                line = edge(coords0[i], coords0[j]).set_opacity(0)
                born_edges.add(line)
                edge_anims.append(Transform(line, edge(coords1[i], coords1[j])))
    return start_edges, born_edges, edge_anims, breaking


@app.class_definition
class PointCloud(ManimWidget):
    # Two states for the same cloud. Start: three blobs spread out. End: the
    # blobs drift toward the origin (and re-scatter), so the proximity graph
    # changes — some edges persist, some break, some are born.
    CENTERS0 = np.array([[-3.0, -3.0, 0.0], [3.0, 0.0, 1.0], [0.0, 3.0, -1.0]])
    CENTERS1 = np.array([[-1.0, -1.0, 0.0], [1.0, 0.0, 0.3], [0.0, 1.0, -0.3]])
    COLORS = [RED, GREEN, BLUE]
    N_PER = 30  # points per blob
    STD = 0.9  # blob spread
    EPSILON = 1.0  # max distance for two points to be connected by an edge

    def construct(self):
        self.move_camera(phi=1, theta=-1.4, zoom=2)
        self.add(ThreeDAxes())
        self.add(
            *[
                MathTex(f"x_{i}").move_to(1.2 * p).rotate(PI / 2, axis=RIGHT)
                for i, p in enumerate(self.CENTERS0)
            ]
        )

        rng = np.random.default_rng(42)
        coords0 = sample_blobs(self.CENTERS0, self.N_PER, self.STD, rng)
        coords1 = sample_blobs(self.CENTERS1, self.N_PER, self.STD, rng)
        point_colors = [color for color in self.COLORS for _ in range(self.N_PER)]

        cloud = make_cloud(coords0, point_colors)
        cloud_end = make_cloud(coords1, point_colors)
        start_edges, born_edges, edge_anims, breaking = proximity_edge_animations(
            coords0, coords1, self.EPSILON
        )

        # Reveal the start state, then play the cloud morph and every edge
        # animation together so the graph visibly reorganizes. Born edges start
        # invisible at their endpoints' start positions, so add them up front.
        self.play(FadeIn(cloud), FadeIn(start_edges), run_time=1.5)
        self.wait(0.5)
        self.add(born_edges)
        self.play(Transform(cloud, cloud_end), *edge_anims, run_time=2.5)
        # Broken edges have followed their endpoints to opacity 0; drop them.
        self.remove(*breaking)
        self.wait()


@app.cell
def _():
    PointCloud(is_3d=True)
    return


@app.function(hide_code=True)
def test(runner):
    # js=False: the MathTex labels need a local LaTeX install the headless JS
    # bundle can't provide; this still serializes + schema-validates the scene.
    runner.check(PointCloud, js=False).assert_ok()


if __name__ == "__main__":
    app.run()
