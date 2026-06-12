from __future__ import annotations

import uuid


class SharedCamera:
    """Coordination token that links multiple ManimWidget instances to a shared camera.

    Pass the same SharedCamera instance to several ManimWidget constructors.
    The JS side uses the stable camera_id to wire a window-level signal so that
    when one scene moves its camera the others update immediately, with no
    Python round-trip in the hot path.
    """

    def __init__(self) -> None:
        self.camera_id = str(uuid.uuid4())
