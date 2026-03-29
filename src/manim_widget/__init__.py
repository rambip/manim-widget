import traitlets
from anywidget import AnyWidget
from manim import Animation, Scene, SceneFileWriter
from manim.typing import PixelArray


class CustomRenderer:
    def __init__(self, file_writer_class=SceneFileWriter, skip_animations=False):
        # Initialize renderer attributes
        self.time = 0
        pass

    def init_scene(self, scene: Scene) -> None:
        # Initialize the scene, create file writer
        pass

    def play(self, scene: "ManimWidget", *animations: Animation, **kwargs) -> None:
        print(animations)
        scene.info = str(animations)
        # Play animations on the scene
        pass

    def update_frame(self, scene: Scene, moving_mobjects=None) -> None:
        # Update the current frame
        pass

    def get_frame(self) -> PixelArray:
        # Get current frame as pixel array
        pass

    def scene_finished(self, scene: Scene) -> None:
        # Clean up when scene is finished
        pass


class ManimWidget(AnyWidget, Scene):
    scene_data = traitlets.List([]).tag(sync=True)
    info = traitlets.Unicode("Info").tag(sync=True)

    def __init__(self):
        AnyWidget.__init__(self)
        Scene.__init__(self, renderer=CustomRenderer())
        self.construct()

    # TODO: rewrite this from scratch, it was just a demo
    _esm = """
        const { Scene, Circle, Create } = await import("https://esm.sh/manim-web@0.3.16/dist/index.js");

        async function render({ model, el }) {
            el.innerHTML = `
                <div id="container"></div>
                <span id="info"></span>
            `;

            const container = el.querySelector('#container');
            const info = el.querySelector('#info');

            async function draw() {
                info.innerHTML=model.get("info");
                container.innerHTML = '';
                const scene = new Scene(container, { width: 600, height: 400 });
                const circle = new Circle({ radius:1 });
                await scene.play(new Create(circle));
            }

            model.on("change:info", draw);

            await draw();

        }
        export default {render}
        """
