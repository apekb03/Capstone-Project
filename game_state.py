"""Mutable session state shared by the game loop, levels, and menus."""

import threading
from typing import Any, Optional

current_user: Optional[dict] = None
input_mode: Any = None  # game_types.InputMode or None
training_mode: bool = False

# Latest webcam frame for PiP (RGB bytes + size), written by facial_emotion thread
webcam_lock = threading.Lock()
webcam_rgb: Optional[bytes] = None
webcam_wh: tuple[int, int] = (0, 0)
