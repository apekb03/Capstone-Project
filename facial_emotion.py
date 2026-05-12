"""
Webcam facial expression → game emotion labels (FEAR, ANGRY, …).

Uses DeepFace when available (pip install opencv-python deepface tensorflow).
Runs in a daemon thread and writes to MultiInputReceiver._latest_emotion only while
game_state.input_mode is EMOTION.

Also pushes mirrored RGB frames to game_state for the in-game PiP preview.
"""

from __future__ import annotations

import os
import threading
import time

import game_state as gs
from game_types import InputMode

# Seconds between DeepFace runs (balance CPU vs responsiveness)
ANALYZE_INTERVAL = 0.42
# Webcam index (0 = default camera)
CAMERA_INDEX = int(os.environ.get("FACIAL_CAMERA_INDEX", "0"))
# Scale frame down before inference
FRAME_SCALE = float(os.environ.get("FACIAL_FRAME_SCALE", "0.38"))
# PiP resolution (BGR resize before RGB upload)
PIP_W = int(os.environ.get("FACIAL_PIP_W", "200"))
PIP_H = int(os.environ.get("FACIAL_PIP_H", "150"))


def _dominant_to_label(dominant: str) -> str:
	d = (dominant or "neutral").strip().upper()
	aliases = {
		"ANGRY": "ANGRY",
		"DISGUST": "DISGUST",
		"FEAR": "FEAR",
		"HAPPY": "HAPPY",
		"SAD": "SAD",
		"SURPRISE": "SURPRISE",
		"NEUTRAL": "NEUTRAL",
	}
	return aliases.get(d, "NEUTRAL")


def _loop(receiver) -> None:
	try:
		import cv2
		from deepface import DeepFace
	except ImportError as e:
		print("[facial] Missing dependency:", e)
		print("[facial] Install: pip install opencv-python deepface tensorflow")
		return

	cap = cv2.VideoCapture(CAMERA_INDEX)
	if not cap.isOpened():
		print(f"[facial] Could not open camera {CAMERA_INDEX}. Emotion mode stays NEUTRAL unless UDP sends labels.")
		return

	preview = os.environ.get("FACIAL_PREVIEW", "").lower() in ("1", "true", "yes")
	last_analyze = 0.0
	print("[facial] Webcam emotion thread running (DeepFace). Use mode 2 in game.")

	while True:
		if gs.input_mode != InputMode.EMOTION:
			with gs.webcam_lock:
				gs.webcam_rgb = None
				gs.webcam_wh = (0, 0)
			time.sleep(0.15)
			continue

		ok, frame = cap.read()
		if ok:
			try:
				pip = cv2.resize(frame, (PIP_W, PIP_H), interpolation=cv2.INTER_AREA)
				pip = cv2.flip(pip, 1)
				rgb = cv2.cvtColor(pip, cv2.COLOR_BGR2RGB)
				data = rgb.tobytes()
				with gs.webcam_lock:
					gs.webcam_rgb = data
					gs.webcam_wh = (rgb.shape[1], rgb.shape[0])
			except Exception:
				pass
		else:
			time.sleep(0.02)
			continue

		now = time.time()
		if now - last_analyze < ANALYZE_INTERVAL:
			if preview:
				cv2.imshow("facial_emotion (preview)", frame)
				cv2.waitKey(1)
			time.sleep(0.028)
			continue
		last_analyze = now

		h, w = frame.shape[:2]
		small = frame
		if 0 < FRAME_SCALE < 1.0:
			small = cv2.resize(frame, (int(w * FRAME_SCALE), int(h * FRAME_SCALE)))

		try:
			kwargs = dict(
				img_path=small,
				actions=["emotion"],
				enforce_detection=False,
				detector_backend="opencv",
			)
			try:
				result = DeepFace.analyze(**kwargs, silent=True)
			except TypeError:
				result = DeepFace.analyze(**kwargs)
		except Exception:
			if preview:
				cv2.imshow("facial_emotion (preview)", frame)
				cv2.waitKey(1)
			time.sleep(0.02)
			continue

		if isinstance(result, list):
			result = result[0] if result else {}
		dominant = result.get("dominant_emotion") or "neutral"
		label = _dominant_to_label(str(dominant))

		with receiver._lock:
			receiver._latest_emotion = label

		if preview:
			cv2.putText(
				frame,
				label,
				(12, 36),
				cv2.FONT_HERSHEY_SIMPLEX,
				1.0,
				(0, 220, 0),
				2,
				cv2.LINE_AA,
			)
			cv2.imshow("facial_emotion (preview)", frame)
			cv2.waitKey(1)


def start(receiver) -> None:
	threading.Thread(target=_loop, args=(receiver,), daemon=True, name="FacialEmotion").start()
