#Created 2/2/2026 11:02PM
#Original Coder James Musick
#3D version of rageBait Version 0.5
import pygame
import json
import sys
import asyncio
import socket
import threading
import os
import random
import time

from bleak import BleakClient
HR_CHAR = "00002a37-0000-1000-8000-00805f9b34fb"
from dataclasses import dataclass
from pulsoid_heartrate import get_heart_rate, validate_token
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

_GAME_DIR = os.path.dirname(os.path.abspath(__file__))


def asset_path(*parts: str) -> str:
	"""Resolve paths relative to this script so the game runs from any cwd."""
	return os.path.normpath(os.path.join(_GAME_DIR, *parts))


pygame.init()
pygame.font.init()

import config
import facial_emotion
import firebase_service as fb
import game_state as gs
from game_types import InputMode

import ui_draw as ui
from menu_screens import (
	LeaderboardScreen,
	LevelSelection,
	MainMenu,
	ModeSelection,
	PauseMenu,
	TitleScreen,
)

PULSOID_TOKEN = os.environ.get("PULSOID_TOKEN")

SCREEN = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
ui.set_screen(SCREEN)
ui.sync_frame_dimensions()

SCREEN_WIDTH = config.SCREEN_WIDTH
SCREEN_HEIGHT = config.SCREEN_HEIGHT
WHITE = config.WHITE
BLACK = config.BLACK

begin_2d = ui.begin_2d
end_2d = ui.end_2d
draw_text = ui.draw_text
draw_text_centered = ui.draw_text_centered
draw_menu_backdrop = ui.draw_menu_backdrop
draw_menu_button = ui.draw_menu_button
draw_webcam_pip = ui.draw_webcam_pip
FONT = ui.FONT
FONT_TITLE = ui.FONT_TITLE
FONT_SUB = ui.FONT_SUB
UI_ACCENT = ui.UI_ACCENT
UI_ACCENT_DIM = ui.UI_ACCENT_DIM
UI_PANEL = ui.UI_PANEL
UI_PANEL_BORDER = ui.UI_PANEL_BORDER
UI_BTN_BG = ui.UI_BTN_BG
UI_BTN_HOVER = ui.UI_BTN_HOVER
UI_BTN_BORDER = ui.UI_BTN_BORDER
UI_MUTED_TEXT = ui.UI_MUTED_TEXT

glViewport(0, 0, ui.frame_w(), ui.frame_h())
pygame.display.set_caption("Heart Beat Devil")

#OpenGL Matrixs and setups----
glMatrixMode(GL_PROJECTION)
glLoadIdentity()
gluPerspective(90, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, 1000.0)
glMatrixMode(GL_MODELVIEW)
glEnable(GL_DEPTH_TEST)
glEnable(GL_BLEND)
glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
glClearColor(0, 0, 0, 1)

clock = pygame.time.Clock()


def _leaderboard_name_for_autosubmit():
	u = gs.current_user or {}
	name = (u.get("display_name") or "").strip()
	return name if name else "Player"


def _complete_level_to_leaderboard(level_name, finish_time, deaths, next_level):
	player = _leaderboard_name_for_autosubmit()
	ok, err = fb.submit_score(level_name, player, finish_time, deaths, source="game")
	last_run = {
		"player": player,
		"time": float(finish_time),
		"deaths": int(deaths),
		"saved": ok,
	}
	return LeaderboardScreen(
		level_name, next_level, upload_ok=ok, upload_err=err, last_run=last_run
	)


def draw_screen_effects(player):
	intensity = player.get_intensity()

	if intensity <= 0:
		return

	pulse = math.sin(pygame.time.get_ticks() * 0.02 * (player.bpm / 60))
	pulse = (pulse + 1) / 2

	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

	dim_alpha = intensity * pulse * 0.6 #change for tuning

	glColor4f(0.0, 0.0, 0.0, dim_alpha)

	glBegin(GL_QUADS)
	glVertex2f(0, 0)
	glVertex2f(SCREEN_WIDTH, 0)
	glVertex2f(SCREEN_WIDTH, SCREEN_HEIGHT)
	glVertex2d(0, SCREEN_HEIGHT)
	glEnd()

	layers = 8 #changes vignette smoothness

	for i in range(layers):
		t = i /layers
		alpha = intensity * (t ** 2) * 0.8

		margin_x = int(SCREEN_WIDTH * 0.5 * t)
		margin_y = int(SCREEN_HEIGHT * 0.5 * t)

		glColor4f(0.0, 0.0, 0.0, alpha)

		glBegin(GL_QUADS)
		glVertex2f(margin_x, margin_y)
		glVertex2f(SCREEN_WIDTH - margin_x, margin_y)
		glVertex2f(SCREEN_WIDTH - margin_x, SCREEN_HEIGHT - margin_y)
		glVertex2f(margin_x, SCREEN_HEIGHT - margin_y)
		glEnd()


def draw_gameplay_jump_hint():
	"""Small footer hint; uses frame size so it stays correct after resize."""
	draw_text_centered(
		"Hold Shift when you jump for extra height",
		ui.frame_w() // 2,
		ui.frame_h() - 36,
		font=FONT_SUB,
		color=UI_MUTED_TEXT,
	)


#Platform arguments  [x, y, z] X controls the - = left and + = right, Y is ground.
#z controls forward and backward  with + = forward and - = backward
#PLATFORM_POS = [5, 2, 0]

#pyramid Vertices
pyramid_vertices = [
	(0, 1, 0),
	(-1, -1, -1),
	(1, -1, -1),
	(1, -1, 1),
	(-1, -1, 1)
]

pyramid_faces = [
	(0, 1, 2),
	(0, 2, 3),
	(0, 3, 4),
	(0, 4, 1),
	(1, 2, 3, 4)
]

#Cube Vertices points in space and lines connecting them together
vertices = [
	(1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, -1),
	(1, -1, 1), (1, 1, 1), (-1, -1, 1), (-1, 1, 1)
]

faces = [
	(0, 1, 2, 3), #backside
	(4, 5, 7, 6), #frontFace
	(0, 1, 5, 4), #rightface
	(2, 3, 6, 7), #Left Face
	(1, 2, 7, 5), #Top face
	(0, 3, 6, 4) #Bottom face
]

def draw_cube(base_color = (1, 1, 1)):
	glBegin(GL_QUADS) #tell OpenGL to draw the lines
	shading = [0.6, 0.7, 0.8, 0.8, 1.0, 0.5]

	for i, face in enumerate(faces):
		shade = shading[i]
		glColor3f(
			base_color[0] * shade,
			base_color[1] * shade,
			base_color[2] * shade
		)
		for vertex in face:
			glVertex3fv(vertices[vertex]) # communicates with the gpu for a 3D point
	glEnd()

def draw_object(position, scale_x, scale_y, scale_z, color=(1, 1, 1)):
        glPushMatrix() # this saves the current transformation state
        glTranslatef(position[0], position[1], position[2]) # moved into position
        glScalef(scale_x, scale_y, scale_z) # resizeing the object
        glColor3f(*color)
        draw_cube(color)
        glPopMatrix() #restores previous state

def draw_pyramid(color=(1, 0, 0)):
	glBegin(GL_TRIANGLES)
	#sides render
	for i in range(4):
		glColor3f(color[0], color[1] * 0.8, color[2] * 0.8)
		for vertex in pyramid_faces[i]:
			glVertex3fv(pyramid_vertices[vertex])

	glEnd()
	#base render
	glBegin(GL_QUADS)
	glColor3f(color[0] * 0.6, color[1] * 0.6, color[2] * 0.6)
	for vertex in pyramid_faces[4]:
		glVertex3fv(pyramid_vertices[vertex])
	glEnd()

def draw_pyramid_object(position, sx, sy, sz, color=(1, 0, 0)):
	glPushMatrix()
	glTranslatef(position[0], position[1], position[2])
	glScalef(sx, sy, sz)
	draw_pyramid(color)
	glPopMatrix()

#Below is the multi-input reciver class and variable related to running the heart beat
#================================================================================
def clamp(val, min_val, max_val):
	return max(min_val, min(max_val, val))


def emotion_visual_stress(emotion: str) -> float:
	"""Screen shake / dim in emotion mode. FEAR = none (easier when scared)."""
	e = (emotion or "NEUTRAL").strip().upper()
	if e == "FEAR":
		return 0.0
	tab = {
		"ANGRY": 0.78,
		"SURPRISE": 0.58,
		"DISGUST": 0.48,
		"SAD": 0.35,
		"HAPPY": 0.06,
		"NEUTRAL": 0.0,
	}
	return max(0.0, min(1.0, tab.get(e, 0.2)))


def emotion_enemy_stress(emotion: str) -> float:
	"""Enemy / platform speed factor input (0–1). Lower = easier. FEAR is very low."""
	e = (emotion or "NEUTRAL").strip().upper()
	if e == "FEAR":
		return 0.06
	tab = {
		"ANGRY": 0.78,
		"SURPRISE": 0.58,
		"DISGUST": 0.48,
		"SAD": 0.35,
		"HAPPY": 0.06,
		"NEUTRAL": 0.0,
	}
	return max(0.0, min(1.0, tab.get(e, 0.2)))

UDP_BIND_IP = "0.0.0.0"
UDP_PORT = 5005
UDP_TIMEOUT = 0.5

class MultiInputReceiver:
	def __init__(self, bind_ip = UDP_BIND_IP, port = UDP_PORT, pulsoid_token=None, ble_address=None):
		self.bind_ip = bind_ip
		self.port = port
		self._latest_bpm = None
		self._latest_emotion = "NEUTRAL"
		self._lock = threading.Lock()
		self._stop = threading.Event()
		self._thread = None
		self.pulsoid_token = pulsoid_token

		self.ble_address = ble_address
		self._ble_thread = None
		self._ble_loop = None
		self._last_ble_update = 0

	def start(self):
		if self._thread and self._thread.is_alive():
			return
		self._stop.clear()
		self._thread = threading.Thread(target = self._run, daemon = True)
		self._thread.start()

		if self.ble_address:
			self._ble_thread = threading.Thread(target = self._run_ble, daemon=True)
			self._ble_thread.start()

	def stop(self):
		self._stop.set()
		if self._thread:
			self._thread.join()

	def get_data(self):
		with self._lock:
			return self._latest_bpm, self._latest_emotion

	def _parse_bpm(self, msg: str):
		try: 
			if msg.startswith("{") and "bpm" in msg.lower():
				obj = json.loads(msg)
				return int(float(obj.get("bpm", 0)))
			if ":" in msg:
				for part in msg.split(":")[::-1]:
					clean = "".join(c for c in part if c.isdigit() or c == ".")
					if clean:
						return int(float(clean))
			clean = "".join(c for c in msg if c.isdigit() or c == ".")
			if clean:
				return int(float(clean))
		except Exception:
			pass
		return None

	def _run(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(UDP_TIMEOUT)
		try:
			sock.bind((self.bind_ip, self.port))
		except OSError:
			print(f"UDP Port {self.port} busy. UDP input disabled")

		while not self._stop.is_set():
			if self.pulsoid_token:
				bpm = get_heart_rate(self.pulsoid_token)
				if bpm:
					with self._lock:
						self._latest_bpm = bpm


			try:
				data, _addr = sock.recvfrom(512)
				msg = data.decode("utf-8", errors="ignore").strip().upper()

				valid_emotions = [
					"FEAR",
					"SURPRISE",
					"DISGUST",
					"HAPPY",
					"ANGRY",
					"SAD",
					"NEUTRAL",
				]
				found_emotion = False
				for emo in valid_emotions:
					if emo in msg:
						with self._lock:
							self._latest_emotion = emo
						found_emotion = True
						break
				if not found_emotion:
					bpm = self._parse_bpm(msg)
					if bpm is not None:
						bpm = max(40, min(180, bpm))
						with self._lock:
							self._latest_bpm = bpm
			except socket.timeout:
				continue
			except Exception as e:
				continue

	def _run_ble(self):
		while not self._stop.is_set():
			try:
				asyncio.run(self._ble_main())
			except Exception as e:
				print("[BLE] crashed:", e)

			if not self._stop.is_set():
				print("[BLE] retrying in 2 seconds...")
				time.sleep(2)

	async def _ble_main(self):
		print("[BLE] trying to connect...")

		try:
			async with BleakClient(self.ble_address) as client:
				if not client.is_connected:
					raise Exception("Connection failed")
				print("[BLE] connected to Heartix")

				await client.start_notify(HR_CHAR, self._ble_handler)

				while not self._stop.is_set():
					await asyncio.sleep(1)

		except Exception as e:
			print("[BLE] connection error:", e)
			raise


	def _ble_handler(self, sender, data):
		try:
			flags = data[0]

			if flags & 0x01:
				bpm = int.from_bytes(data[1:3], "little")
			else:
				bpm = data[1]

			with self._lock:
				self._latest_bpm = max(40, min(200, bpm))
				self.last_ble_update = time.time()
		except:
			pass
receiver = MultiInputReceiver(pulsoid_token = PULSOID_TOKEN, ble_address="F7:0F:C7:B2:51:BB")
receiver.start()
facial_emotion.start(receiver)
#================================================================
#.obj loader to import 3D models
# If you are trying to import a model you need to go to each lvls __init__ and add ->
# <self.my_model = OBJModel("filepath/obj")> the self.my_model can be changed to what you need
# you will also have to upadte the draw functions  with draw_obj(self.my_model, position=(0, 2, 10), scale=1)
class OBJModel:
	def __init__(self, filename):
		self.vertices = []
		self.normals = []
		self.texcoords = []
		self.faces = []
		self.materials = {}
		self.current_material = None

		with open(filename, "r") as f:
			for line in f:
				if line.startswith("mtllib"):
					base_dir = os.path.dirname(filename)
					mtl_file = line.split()[1]
					mtl_path = os.path.join(base_dir, mtl_file)

					print("OBJ file:", filename)
					print("Resolved MTL path:", mtl_path)
					print("Resovled base dir:", base_dir)
					if os.path.exists(mtl_path):
						self.materials = load_mtl(mtl_path)
					else:
						print("MTL NOT FOUND", mtl_path)

				elif line.startswith("usemtl"):
					self.current_material = line.split()[1]

				elif line.startswith("v "):
					parts = line.strip().split()
					self.vertices.append(tuple(map(float, parts[1:4])))

				elif line.startswith("vn "):
					parts = line.strip().split()
					self.normals.append(tuple(map(float, parts[1:4])))

				elif line.startswith("vt "):
					self.texcoords.append(tuple(map(float, line.split()[1:3])))

				elif line.startswith("f "):
					parts = line.strip().split()[1:]
					face = []

					for p in parts:
						vals = p.split("/")
						v_idx = int(vals[0]) - 1 if vals[0] else None
						vt_idx = int(vals[1]) - 1 if len(vals) > 1 and vals[1] else None
						vn_idx = int(vals[2]) - 1 if len(vals) > 2 and vals[2] else None
						face.append((v_idx, vt_idx, vn_idx)) #order matters v_idx, vt_idx, vn_idx
					self.faces.append((face, self.current_material))

#======================================================================



def draw_obj(model, position=(0,0,0), scale=1, color=(1,1,1)):
	glPushMatrix()
	glTranslatef(*position)
	glScalef(scale, scale, scale)

	glEnable(GL_TEXTURE_2D)

	for face, material in model.faces:
		if material and material in model.materials:
			tex = model.materials[material].get("texture")
			if tex:
				glBindTexture(GL_TEXTURE_2D, tex)

		glBegin(GL_POLYGON) #GL_POLYGON will work for small mesh/porps but be warned that bigger objects will cause performance issues
		for v_idx, vt_idx, vn_idx in face:
			if vt_idx is not None:
				glTexCoord2fv(model.texcoords[vt_idx])
			if vn_idx is not None:
				glNormal3fv(model.normals[vn_idx])

			glVertex3fv(model.vertices[v_idx])
		glEnd()

	glDisable(GL_TEXTURE_2D)
	glPopMatrix()

def load_mtl(filename):
	print("Loading MTL:", filename)

	materials = {}
	current = None
	basse_dir = os.path.dirname(os.path.abspath(filename))

	with open(filename, "r") as f:
		for line in f:
			if line.startswith("newmtl"):
				current = line.split()[1]
				materials[current] = {}
			elif line.startswith("map_Kd") and current:
				base_dir = os.path.dirname(filename)

				texture_file = line.split()[1]
				texture_file = os.path.join(base_dir, texture_file)
				print("Loading Textures:", texture_file)

				materials[current]["texture"] = load_texture(texture_file)
	return materials

def load_texture(image_path):
	surface = pygame.image.load(image_path)
	image = pygame.image.tostring(surface, "RGBA", True)
	width, height = surface.get_size()

	tex_id = glGenTextures(1)
	glBindTexture(GL_TEXTURE_2D, tex_id)

	glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image)

	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
	glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

	return tex_id
#=================================================================
class Player:
	def __init__(self, spawn_pos = [0, 2, 35]):
		self.spawn_pos = list(spawn_pos)
		self.pos = list(spawn_pos)
		self.deaths = 0

		self.vel_x = 0
		self.vel_y = 0
		self.vel_z = 0

		self.speed = 40
		self.sprintSpeed = 80
		self.gravity = -13
		self.jump = False

		self.yaw = 90
		self.pitch = -30
		self.sens = 0.1 # sens stands for Sensitivity

		self.bpm = 80
		self.emotion = "NEUTRAL"

		self.shake_intensity = 0
		self.shake_timer = 0
		self.dim_intensity = 0

		self.grappling = False
		self.grapple_point = None
		self.grapple_speed = 25

	def mouse(self):
		dx, dy = pygame.mouse.get_rel()

		self.yaw -= dx*self.sens
		self.pitch -= dy*self.sens
		self.pitch = max(-90,min(90, self.pitch))

	def front(self):
		fx = math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
		fy = math.sin(math.radians(self.pitch))
		fz = -math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))

		l = math.sqrt(fx*fx + fy*fy + fz*fz)
		return [fx/l, fy/l, fz/l]

	def move(self, keys, dt):
		f = self.front()
		flat = [f[0], 0, f[2]]
		l = math.sqrt(flat[0]**2 + flat[2]**2)
		if l != 0:
			flat = [flat[0]/l, 0, flat[2]/l]

		right= [flat[2], 0, -flat[0]]
		sprintSpeed = self.sprintSpeed * dt
		speed = self.speed * dt

		if gs.input_mode == InputMode.EMOTION and (self.emotion or "").upper() == "FEAR":
			ease = 1.1
			sprintSpeed *= ease
			speed *= ease

		sprinting = keys[K_LSHIFT] or keys[K_RSHIFT]
		current_speed = sprintSpeed if sprinting else speed

		if keys[K_w]:
			self.vel_x += flat[0]*current_speed
			self.vel_z += flat[2]*current_speed

		if keys[K_s]:
			self.vel_x -= flat[0]*current_speed
			self.vel_z -= flat[2]*current_speed

		if keys[K_d]:
			self.vel_x -= right[0]*current_speed
			self.vel_z -= right[2]*current_speed

		if keys[K_a]:
			self.vel_x += right[0]*current_speed
			self.vel_z += right[2]*current_speed

		if keys[K_SPACE] and not self.jump:
			self.vel_y = 15 if sprinting else 10
			self.jump = True

	def gravity_apply(self, dt):

		self.vel_y += self.gravity*dt

		self.pos[0] += self.vel_x*dt
		self.pos[1] += self.vel_y*dt
		self.pos[2] += self.vel_z*dt

		#creates friction
		self.vel_x *= 0.90
		self.vel_z *= 0.90

	def start_grapple(self, point):
		self.grappling = True
		self.grapple_point = point

	def stop_grapple(self):
		self.grappling = False
		self.grapple_point = None

	def update_grapple(self, dt):
		if not self.grappling:
			return

		gx, gy, gz = self.grapple_point
		px, py, pz = self.camera_pos()

		dx = gx - px
		dy = gy - py
		dz = gz - pz

		dist = math.sqrt(dx*dx + dy*dy + dz*dz)

		if dist < 1:
			return

		dx /= dist
		dy /= dist
		dz /= dist

		pull_strength = 40 #the pull strength of the rope

		self.vel_x += dx * pull_strength * dt
		self.vel_y += dy * pull_strength * dt
		self.vel_z += dz * pull_strength * dt

		rope_length = 25 #the distance you can grab onto the grapple point

		if dist > rope_length:
			correction = dist - rope_length

			self.pos[0] += dx * correction
			self.pos[1] += dy * correction
			self.pos[2] += dz * correction

	def try_grapple(self, grapple_points):
		px, py, pz = self.camera_pos()
		fx, fy, fz = self.front()

		best_point = None
		best_dot = 0.96

		for point in grapple_points:
			dx = point[0] - px
			dy = point[1] - py
			dz = point[2] - pz

			dist = math.sqrt(dx*dx + dy*dy + dz*dz)

			if dist > 40:
				continue

			dx /= dist
			dy /= dist
			dz /= dist

			dot = dx*fx + dy*fy + dz*fz
			if dot > best_dot:
				best_dot = dot
				best_point = point

		if best_point:
			self.start_grapple(best_point)

	def camera(self):
		x, y, z = self.pos[0], self.pos[1] +1.5, self.pos[2]
		f = self.front()

		shake_x = 0
		shake_y = 0

		if self.shake_timer > 0:
			pulse = math.sin(pygame.time.get_ticks() * 0.02 * (self.bpm / 60))
			shake_x = pulse * self.shake_intensity
			shake_y = pulse * self.shake_intensity

		gluLookAt(x + shake_x, y + shake_y, z, x+f[0], y+f[1], z+f[2], 0, 1, 0)

	def camera_pos(self):
		return (self.pos[0], self.pos[1] + 1.5, self.pos[2])

#THIS CHANGES THE THRESHOLD OF WHEN EFFECTS START
	def get_intensity(self):
		if gs.input_mode == InputMode.EMOTION:
			return emotion_visual_stress(self.emotion)

		threshold = 90 
#		threshold = 60
		max_bpm = 180

		if self.bpm <= threshold:
			return 0

		intensity = (self.bpm - threshold) / (max_bpm - threshold)
		return max(0, min(1, intensity))

	def update_effects(self, dt):
		intensity = self.get_intensity()

		#Shake
		if intensity > 0:
			self.shake_intensity = intensity * 0.5 #Change this for dif intensity
			self.shake_timer = 0.1
		else: 
			self.shake_intensity = 0

		#Dim
		self.dim_intensity = intensity

	def get_bpm_factor(self):
		if gs.input_mode == InputMode.EMOTION:
			t = emotion_enemy_stress(self.emotion)
			return 0.7 + t * 1.3

		min_bpm = 60
		max_bpm = 180

		bpm = max(min_bpm, min(max_bpm, self.bpm))

		t = (bpm - min_bpm) / (max_bpm - min_bpm)

		return 0.7 + t * 1.3

	def respawn(self):
		self.deaths += 1

		self.pos = list(self.spawn_pos)
		self.vel_y = 0
		self.jump = False
#=========================================================================
class Door:
	def __init__(self, pos, size, targetLevel):
		self.pos = pos
		self.size = size
		self.targetLevel = targetLevel

	def draw(self):
		draw_object(self.pos, self.size[0], self.size[1], self.size[2], (0, 0, 1))

	def check_collision(self, player):
		# Use camera / upper body position — feet-only (player.pos) often sat just outside
		# the door's strict Y slab while the player clearly crossed the finish volume.
		px, py, pz = player.camera_pos()
		dx, dy, dz = self.pos
		sx, sy, sz = self.size

		margin = 0.4
		in_xz = (
			abs(px - dx) < (sx * 0.5 + margin) and
			abs(pz - dz) < (sz * 0.5 + margin)
		)

		in_y = abs(py - dy) < (sy * 0.5 + margin)

		return in_xz and in_y

#=======================================================================
class SpikeTrap:
	def __init__(self, pos, size):
		self.pos = pos
		self.size = size

	def draw(self, model):
		draw_obj(model, position = self.pos, scale = self.size[0])

	def check_collision(self, player):
		px, py, pz = player.pos
		sx, sy, sz = self.pos
		size_x, size_y, size_z = self.size

		player_half = 0.5

		if py < sy or py > sy + size_y + player_half:
			return False

		h = (py - sy) / size_y

		max_radius_x = size_x * (1 - h)
		max_radius_z = size_z * (1 - h)

		dx = abs(px - sx)
		dz = abs(pz - sz)
		return dx < (max_radius_x + player_half) and dz < (max_radius_z + player_half)

#=======================================================================
class MovingPlatform:
	def __init__(self, start_pos, size, axis="x", range=5, speed=2):
		self.start_pos = list(start_pos)
		self.pos = list(start_pos)
		self.size = size

		self.axis = axis
		self.range = range
		self.base_speed = speed
		self.speed = speed

		self.time = 0
		self.prev_pos = list(start_pos)

	def update(self, dt):
		self.time += dt * self.speed

		self.prev_pos = list(self.pos)
		offset = math.sin(self.time) * self.range

		if self.axis == "x":
			self.pos[0] = self.start_pos[0] + offset
		elif self.axis == "y":
			self.pos[1] = self.start_pos[1] + offset
		elif self.axis == "z":
			self.pos[2] = self.start_pos[2] + offset

	def update_bpm(self, bpm_factor):
		self.speed = self.base_speed * bpm_factor

	def delta(self):
		return [
			self.pos[0] - self.prev_pos[0],
			self.pos[1] - self.prev_pos[1],
			self.pos[2] - self.prev_pos[2],
		]

	def draw(self):
		draw_object(self.pos, self.size[0], self.size[1], self.size[2], (0, 0.5, 1))
#===================================================================
class Enemy:
	def __init__(self, pos, speed=3):

		self.spawn_pos = list(pos)
		self.pos = list(pos)

		self.speed = speed
		self.size = 1.2

		self.color = (0.8, 0.1, 0.1)

		self.aggro_distance = 60
		self.attack_distance = 1.5
		self.yaw = 0

	def update(self, player, dt):
		bpm_factor = player.get_bpm_factor()
		actual_speed = self.speed * bpm_factor

		px, py, pz = player.camera_pos()
		ex, ey, ez = self.pos

		dx = px - ex
		dy = py - ey
		dz = pz - ez

		dist = math.sqrt(dx*dx + dz*dz)

		if dist < self.aggro_distance and dist > 0.01:
			self.yaw = math.degrees(math.atan2(-dz, dx))

			dx /= dist
			dy /= dist
			dz /= dist

			self.pos[0] += dx * actual_speed * dt
			self.pos[1] += dy * actual_speed * dt
			self.pos[2] += dz * actual_speed * dt

	def check_collision(self, player):
		px, py, pz = player.camera_pos()
		ex, ey, ez = self.pos

		dx = px - ex
		dy = py - ey
		dz = pz - ez

		dist = math.sqrt(dx*dx + dy*dy + dz*dz)

		return dist < (self.size * 1.5)

	def reset(self):
		self.pos = list(self.spawn_pos)
		self.yaw = 0


	def draw(self):
		glPushMatrix()
		glTranslatef(*self.pos)
		glRotatef(self.yaw, 0, 1, 0)
		glScalef(self.size, self.size, self.size)
		draw_cube(self.color)
		glPopMatrix()


class Lvl:
	def __init__(self, grounds=None, platforms=None, spikes=None):
			#x  y,  z, scale_x, scale_y, scale_z
		self.GROUNDS = grounds if grounds is not None else[]
		self.PLATFORMS_POS = platforms if platforms is not None else[]
		self.moving_platforms = []

		#Platforms have x,y,z  (z is -forward, +back. Y +up & -down. X -left to +Right)

		self.player_half = 1
		self.DEATH_Y = -20
		self.ground_half = [5, 40] # when you make the ground bigger this needs to change to match it for collision purpose
		self.plat_half = [1, 0.25, 1]

	def collide(self, p): # the p stands for player
		for g in self.GROUNDS: #g stands for ground
			gx, gy, gz, sx, sy, sz = g #ground x,y,z and scale x,y,z
			if abs(p.pos[0] - gx) < sx + self.player_half and \
		   	   abs(p.pos[2] - gz) < sz + self.player_half:

				if p.pos[1] <= gy + self.player_half:
					p.pos[1] = gy + self.player_half
					p.vel_y = 0
					p.jump = False
#-----------Platfrom collision ------------

		for plat in self.PLATFORMS_POS:
			dx = p.pos[0] - plat[0]
			dz = p.pos[2] - plat[2]

			overlap_x = (self.plat_half[0] + self.player_half) - abs(dx)
			overlap_z = (self.plat_half[2] + self.player_half) - abs(dz)

			if overlap_x > 0 and overlap_z > 0:
				top = plat[1] + self.plat_half[1]
				landing_tolerance = 0.3

				#top side collision
				if p.vel_y <= 0 and p.pos[1] >= top and p.pos[1] <= top + self.player_half:
					p.pos[1] = top + self.player_half
					p.vel_y = 0
					p.jump = False

				elif not p.jump:
					if overlap_x < overlap_z:
						if dx > 0:
							p.pos[0] += overlap_x
						else:
							p.pos[0] -= overlap_x
					else:
						if dz > 0:
							p.pos[2] += overlap_z
						else:
							p.pos[2] -= overlap_z

#----------Moving Platform collision-------------

		for plat in self.moving_platforms:
			px, py, pz = p.pos
			x, y, z = plat.pos
			sx, sy, sz = plat.size

			dx = px - x
			dz = pz - z

			overlap_x = (sx + self.player_half) - abs(dx)
			overlap_z = (sz + self.player_half) - abs(dz)

			if overlap_x > 0 and overlap_z > 0:
				top = y + sy
				landing_tolerance = 0.3

#----------------------- Top Collision --------
				if p.vel_y <= 0 and py >= top and py <= top + self.player_half:
					p.pos[1] = top + self.player_half
					p.vel_y = 0
					p.jump = False

					move_dx, move_dy, move_dz = plat.delta()
					p.pos[0] += move_dx
					p.pos[2] += move_dz
				elif not p.jump:
					if overlap_x < overlap_z:
						if dx > 0:
							p.pos[0] += overlap_x
						else:
							p.pos[0] -= overlap_x
					else:
						if dz > 0:
							p.pos[2] += overlap_z
						else:
							p.pos[2] -= overlap_z

	def draw(self):
		for g in self.GROUNDS:
			draw_object([g[0], g[1], g[2]], g[3], g[4], g[5], (1,0,0))
#		draw_object([0, self.GROUND_Y -1, 0], 5,1,40, (1,0,0)) #Change length of ground by changing the (5, 1, 40)
		for p in self.PLATFORMS_POS:
			draw_object(p, 2, 0.5, 2, (0.6, 0.4, 0.2))

#================================================================================
class LvlOne:
	def __init__(self):
		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		self.player= Player()

		self.start_time = time.time()
		self.finish_time = None

		self.spike_model = OBJModel(asset_path("models", "SpikeTrap.obj"))

	#Below is how you generate individual spikes
		#self.spikes = [
		#	SpikeTrap([0, 0, 20], [0.7, 1.5, 0.7]),
		#	SpikeTrap([1, 0, 20], [0.7, 1.5, 0.7]),
		#	SpikeTrap([-1, 0, 20], [0.7, 1.5, 0.7])
	#	]
		self.spikes = [
			SpikeTrap([0, 0, 20], [14, 2, 5])
		]

	#	Below is how to create spikes in a row
	#	for x in range(-4, 5, 1): #spikes start at(#, go upto #, steped by # that controls spacing)
	#		self.spikes.append(
	#			SpikeTrap([x, 1.5, 20], [0.7, 1.5, 0.7]) 
	#		)

		self.level= Lvl(
			grounds=[
			[0, -1, 25, 4, 1, 15], #arguments[position x,y,z scale x,y,z]
			[0, -1, -40, 4, 1, 15]
		],
			platforms=[
			[-3, 1, 2],
			[-1, 3, -7],
			[3, 4, -17]
		],

	)

		self.door = Door([0, 2, -50], [1, 2, 1], "level2") #This is the line you change to move the door

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				pygame.mouse.set_visible(True)
				pygame.event.set_grab(False)
				return PauseMenu(self)
	def on_enter(self):
		self.next_state = None

		self.start_time = time.time()
		self.finish_time = None

		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		pygame.mouse.get_rel()

	def update(self, dt):
	#	print("Player:", self.player.pos, "Door:", self.door.pos)

		bpm, emotion = receiver.get_data() #this needs to be added to every update method for the levels

		if gs.input_mode == InputMode.HEART_RATE:
			if bpm is not None:
				self.player.bpm = bpm

		elif gs.input_mode == InputMode.EMOTION:
			self.player.emotion = emotion #====

		self.player.mouse()

		keys = pygame.key.get_pressed()
		self.player.move(keys, dt)
		self.player.gravity_apply(dt)
		self.player.update_effects(dt)

		if self.door.check_collision(self.player) and self.finish_time is None:
			self.finish_time = time.time() - self.start_time
			self.next_state = _complete_level_to_leaderboard(
				"Level 1", self.finish_time, self.player.deaths, self.door.targetLevel
			)

		self.level.collide(self.player)

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()



		for spike in self.spikes:
			if spike.check_collision(self.player):
				self.player.respawn()


	def draw(self):
		glClearColor(0.5, 0.7, 1.0, 1)
		glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
		glLoadIdentity()

		self.player.camera()

		self.level.draw()
		self.door.draw() #every draw needs this line to make the door appear in the level

		for spike in self.spikes:
			spike.draw(self.spike_model)

		begin_2d()

		elapsed = time.time() - self.start_time
		fps = clock.get_fps()

		mode_text = "None"
		if gs.input_mode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"

		elif gs.input_mode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if gs.training_mode else "OFF"

		draw_text("Level One", 20, 40) #Debugging purpose
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)

		draw_text(f"BPM: {self.player.bpm}", 20, 120)
		draw_text(f"Emotion: {self.player.emotion}", 20, 140)
		draw_text(f"Time: {elapsed:.2f}s", 20, 160)
		if self.finish_time is not None:
			draw_text(f"Completed In: {self.finish_time:.2f}s", 20, 200)
		draw_screen_effects(self.player)

		draw_webcam_pip()
		draw_gameplay_jump_hint()

		draw_text(f"FPS: {int(fps)}", SCREEN_WIDTH - 120, 20)

		end_2d()
#=========================================================================================================
class LvlTwo:
	def __init__(self):
		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		self.player = Player()

		self.start_time = time.time()
		self.finish_time = None

		self.level = Lvl(
			grounds=[
			[0, -1, 30, 3, 1, 15],
			[0, -1, -80, 3, 1, 15]
		],
			platforms=[
			[-3, 1, 7], #1 [x,y,z]
			[0, 2, -3], #2 [x,y,z]
			[4, 6, -45], #3 [x,y,z]
			[0, 4, -55] #4 [x,y,z]
		]
	)

		self.level.moving_platforms = [
			MovingPlatform([0, 2, -15], [2, 0.5, 2], axis="x", range=5, speed=2),
			MovingPlatform([3, 4, -30], [2, 0.5, 2], axis="z", range=6, speed=1.5)
		]

		self.door = Door([0, 2, -90], [1, 2, 1], "level3")

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				pygame.mouse.set_visible(True)
				pygame.event.set_grab(False)
				return PauseMenu(self)
	def on_enter(self):
		self.next_state = None

		self.start_time = time.time()
		self.finish_time = None

		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		pygame.mouse.get_rel()

	def update(self, dt):
		bpm, emotion = receiver.get_data() #this needs to be added to every update method for the levels

		if gs.input_mode == InputMode.HEART_RATE:
			if bpm is not None:
				self.player.bpm = bpm

		elif gs.input_mode == InputMode.EMOTION:
			self.player.emotion = emotion #====

		self.player.mouse()

		keys = pygame.key.get_pressed()
		self.player.move(keys, dt)
		self.player.gravity_apply(dt)
		self.player.update_effects(dt)

		bpm_factor = self.player.get_bpm_factor()

		for plat in self.level.moving_platforms:
			plat.update_bpm(bpm_factor)
			plat.update(dt)

		if self.door.check_collision(self.player) and self.finish_time is None:
			self.finish_time = time.time() - self.start_time
			self.next_state = _complete_level_to_leaderboard(
				"Level 2", self.finish_time, self.player.deaths, self.door.targetLevel
			)

		self.level.collide(self.player)

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()

	def draw(self):
		glClearColor(0.5, 0.7, 1.0, 1)
		glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
		glLoadIdentity()

		self.player.camera()
		self.level.draw()
		self.door.draw()

		for plat in self.level.moving_platforms:
			plat.draw()

		begin_2d()

		elapsed = time.time() - self.start_time
		fps = clock.get_fps()

		mode_text = "None"
		if gs.input_mode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"
		elif gs.input_mode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if gs.training_mode else "OFF"

		draw_text("Level Two", 20, 40)
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)

		draw_text(f"BPM: {self.player.bpm}", 20, 120)
		draw_text(f"Emotion: {self.player.emotion}", 20, 140)
		draw_text(f"Time: {elapsed:.2f}s", 20, 160)
		if self.finish_time is not None:
			draw_text(f"Completed In: {self.finish_time:.2f}s", 20, 200)
		draw_screen_effects(self.player)

		draw_webcam_pip()
		draw_gameplay_jump_hint()

		draw_text(f"FPS: {int(fps)}", SCREEN_WIDTH - 120, 20)

		end_2d()
#========================================================================================
class LvlThree():
	def __init__(self):
		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		self.player = Player()

		self.start_time = time.time()
		self.finish_time = None

		self.spike_model = OBJModel(asset_path("models", "SpikeTrap.obj"))
		self.spikes = [
			SpikeTrap([0, -2, -70], [14, 2, 5]),
			SpikeTrap([0, -2, -80], [14, 2, 5])
#			SpikeTrap([0, -2, -90], [14, 2, 5])
		]


		self.level = Lvl(
			grounds=[
			[0, -3, 25, 3, 1, 15],
			[0, -3, -75, 5, 1, 10],
			[0, -3, -300, 3, 1, 15]
		],
			platforms=[
			[-5, 0.5, 0],
			[5, 3, -18],
			[0, 3, -40]
		]
	)

		self.enemies = [
			Enemy([20, 2, -25], speed = 10),
			Enemy([-20, 2, -40], speed = 10),
			Enemy([20, 2, -60], speed = 10),
			Enemy([-20, 2, -70], speed = 10),
			Enemy([-20, 10, -200], speed = 10),
			Enemy([20, 10, -210], speed = 10)
		]
		#make sure to add grapple points to other level that will use them
		self.grapple_points = [
			(-2, 15, -55),
			(2, 15, -90),
			(4, 15, -170),
			(-2, 15, -240)
		]

		self.level.moving_platforms = [
			MovingPlatform([4, 3, -105], [2, 0.5, 2], axis="x", range=5, speed=2),
			MovingPlatform([-4, 3, -125], [2, 0.5, 2], axis="x", range=5, speed=2)
		]

		self.door = Door([0, 0, -310], [1, 2, 1], "level4")

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				pygame.mouse.set_visible(True)
				pygame.event.set_grab(False)
				return PauseMenu(self)
			#to add the grapple to other lvls need this and to draw them and to add it to update
			if event.type == pygame.MOUSEBUTTONDOWN:
				if event.button == 3: #Mouse button are 1=LClick, 2=MClick, 3=RClick
					self.player.try_grapple(self.grapple_points)

			if event.type == pygame.MOUSEBUTTONUP:
				if event.button == 3:
					self.player.stop_grapple()
	def on_enter(self):
		self.next_state = None
		self.start_time = time.time()
		self.finish_time = None
		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		pygame.mouse.get_rel()

	def update(self, dt):
		bpm, emotion = receiver.get_data()

		if gs.input_mode == InputMode.HEART_RATE:
			if bpm is not None:
				self.player.bpm = bpm
		elif gs.input_mode == InputMode.EMOTION:
			self.player.emotion = emotion

		self.player.mouse()

		keys = pygame.key.get_pressed()

		self.player.move(keys, dt)
		self.player.gravity_apply(dt)
		self.player.update_grapple(dt)

		self.player.update_effects(dt)

		for enemy in self.enemies: #enemy collision against the player
			enemy.update(self.player, dt)
			if enemy.check_collision(self.player):
				self.player.respawn()

				for e in self.enemies:
					e.reset()

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()

			for enemy in self.enemies:
				enemy.reset()

		for spike in self.spikes:
			if spike.check_collision(self.player):
				self.player.respawn()

		bpm_factor = self.player.get_bpm_factor()

		for plat in self.level.moving_platforms:
			plat.update_bpm(bpm_factor)
			plat.update(dt)

		if self.door.check_collision(self.player) and self.finish_time is None:
			self.finish_time = time.time() - self.start_time
			self.next_state = _complete_level_to_leaderboard(
				"Level 3", self.finish_time, self.player.deaths, self.door.targetLevel
			)

		self.level.collide(self.player)

	def draw_rope(self):
		if not (self.player.grappling and self.player.grapple_point):
			return

		px, py, pz = self.player.camera_pos()
		gx, gy, gz = self.player.grapple_point

		# direction vector
		dx = gx - px
		dy = gy - py
		dz = gz - pz

		length = math.sqrt(dx*dx + dy*dy + dz*dz)
		if length < 0.001:
			return

		dx /= length
		dy /= length
		dz /= length

		# pick an up vector (avoid parallel issues)
		upx, upy, upz = 0, 1, 0

		# perpendicular vectors (rope basis)
		rx = dy * upz - dz * upy
		ry = dz * upx - dx * upz
		rz = dx * upy - dy * upx

		rlen = math.sqrt(rx*rx + ry*ry + rz*rz)
		if rlen < 0.0001:
			upx, upy, upz = 1, 0, 0
			rx = dy * upz - dz * upy
			ry = dz * upx - dx * upz
			rz = dx * upy - dy * upx
			rlen = math.sqrt(rx*rx + ry*ry + rz*rz)

		rx /= rlen
		ry /= rlen
		rz /= rlen

		# second perpendicular
		sx = dy * rz - dz * ry
		sy = dz * rx - dx * rz
		sz = dx * ry - dy * rx

		slen = math.sqrt(sx*sx + sy*sy + sz*sz)
		sx /= slen
		sy /= slen
		sz /= slen
	
		# rope thickness (increase here)
		thickness = 0.010

		segments = 10  # smoothness

		glPushAttrib(GL_ENABLE_BIT | GL_DEPTH_BUFFER_BIT)
		glDisable(GL_DEPTH_TEST)
		glDisable(GL_CULL_FACE)

		glColor3f(1, 0, 0)

		glBegin(GL_QUADS)

		for i in range(segments):
			a0 = (i / segments) * 2 * math.pi
			a1 = ((i + 1) / segments) * 2 * math.pi

			c0 = math.cos(a0) * thickness
			s0 = math.sin(a0) * thickness
			c1 = math.cos(a1) * thickness
			s1 = math.sin(a1) * thickness

			# ring offset directions
			ox0 = rx * c0 + sx * s0
			oy0 = ry * c0 + sy * s0
			oz0 = rz * c0 + sz * s0

			ox1 = rx * c1 + sx * s1
			oy1 = ry * c1 + sy * s1
			oz1 = rz * c1 + sz * s1

			# segment quad
			glVertex3f(px + ox0, py + oy0, pz + oz0)
			glVertex3f(px + ox1, py + oy1, pz + oz1)
			glVertex3f(gx + ox1, gy + oy1, gz + oz1)
			glVertex3f(gx + ox0, gy + oy0, gz + oz0)
	
		glEnd()

		glPopAttrib()

	def draw(self):
		glClearColor(0.5, 0.7, 1.0, 1)
		glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)

		glMatrixMode(GL_MODELVIEW)
		glLoadIdentity()

		self.player.camera()
		self.level.draw()
		

		for enemy in self.enemies:
			enemy.draw()

		for spike in self.spikes:
			spike.draw(self.spike_model)

		for point in self.grapple_points:
			draw_object(point, 0.3, 0.3, 0.3, (1, 1, 0))
		self.door.draw()
		self.draw_rope()

		for plat in self.level.moving_platforms:
			plat.draw()

		begin_2d()

		elapsed = time.time() - self.start_time
		fps = clock.get_fps()

		mode_text = "None"
		if gs.input_mode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"
		elif gs.input_mode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if gs.training_mode else "OFF"

		draw_text("Level Three (WIP)", 20, 40)
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)
		draw_text(f"BPM: {self.player.bpm}", 20, 120)
		draw_text(f"Emotion: {self.player.emotion}", 20, 140)
		draw_text(f"Time: {elapsed:.2f}s", 20, 160)
		if self.finish_time is not None:
			draw_text(f"Completed In: {self.finish_time:.2f}s", 20, 200)
		draw_screen_effects(self.player)

		draw_webcam_pip()
		draw_gameplay_jump_hint()

		draw_text(f"FPS: {int(fps)}", SCREEN_WIDTH - 120, 20)

		end_2d()

#=============================================================================================================
def resolve_state(name):
	if name == "level1":
		return LvlOne()

	elif name == "level2":
		return LvlTwo()

	elif name == "level3":
		return LvlThree()

	elif name == "main_menu":
		return MainMenu()

	elif name == "lvlSelection":
		return LevelSelection()

	elif name == "start":
		return ModeSelection()

	return None

def apply_state_change(currentState, new_state):
	if new_state == "quit":
		pygame.quit()
		sys.exit()

	if isinstance(new_state, str):
		resolved = resolve_state(new_state)
		if resolved:
			if hasattr(resolved, "on_enter"):
				resolved.on_enter()
			return resolved
		print("unknown state:", new_state)
		return currentState

	if isinstance(new_state, tuple):
		menu_target, level = new_state
		if menu_target == "start":
			ms = ModeSelection()
			ms.target_level = level
			if hasattr(ms, "on_enter"):
				ms.on_enter()
			return ms

	if hasattr(new_state, "draw"):
		if hasattr(new_state, "on_enter"):
			new_state.on_enter()
		return new_state

	print("Invalid state:", type(new_state))
	return currentState

def main_menu():
	game_start = time.time()
	currentState = TitleScreen()

	if hasattr(currentState, "on_enter"):
		currentState.on_enter()

	menu = True
	while menu:
		dt = clock.tick(60) / 1000
		fps = clock.get_fps()

		events = pygame.event.get()

		global paused

		for event in events:
			if event.type == pygame.QUIT:
				pygame.quit()
				return
			if event.type == pygame.VIDEORESIZE:
				ui.sync_frame_dimensions()

		if hasattr(currentState, "handleEvents"):
			result = currentState.handleEvents(events)

			if result == "quit":
				pygame.quit()
				return

			if result is not None:
				currentState = apply_state_change(currentState, result)

		if hasattr(currentState, "next_state") and currentState.next_state is not None:
			currentState = apply_state_change(currentState, currentState.next_state)
			currentState.next_state = None

		if hasattr(currentState, "update"):
			currentState.update(dt)

		if hasattr(currentState, "draw"):
			currentState.draw()


		pygame.display.flip()

	pygame.quit()
if __name__ == "__main__":
	main_menu()
