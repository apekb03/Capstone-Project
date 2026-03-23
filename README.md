# Capstone-Project

Architectural Diagram

+-------------------+
|    launcher.py    |
| (auto-reload dev) |
+---------+---------+
          |
          v
+---------------------------+
|         main.py           |
|   (Pygame game engine)    |
+-------------+-------------+
              |
              v
     +------------------+
     | Biometric Inputs |
     +------------------+
      /        |         \
     v         v          v
+---------+ +--------+ +----------------------+
| Pulsoid | |  UDP   | | Webcam + DeepFace    |
| API     | | stream | | emotion (optional)   |
+----+----+ +---+----+ +----------+-----------+
     |          |                  |
     +----------+------------------+
                v
      +-----------------------+
      | BiometricController   |
      | - HR/Emotion mode     |
      | - maps to states:     |
      |   normal/stress/panic |
      +-----------+-----------+
                  |
                  v
      +-----------------------+
      | Gameplay Modifiers    |
      | speed/jump/vision/FX  |
      | traps pressure, etc.  |
      +-----------+-----------+
                  |
                  v
      +-----------------------+
      | HUD + Rendering       |
      | Heart value + source  |
      | (PULSOID/UDP/SIM)     |
      +-----------------------+