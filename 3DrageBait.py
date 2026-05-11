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

import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import exceptions as fb_exceptions

from bleak import BleakClient
HR_CHAR = "00002a37-0000-1000-8000-00805f9b34fb"
from enum import Enum
from dataclasses import dataclass
from pulsoid_heartrate import get_heart_rate, validate_token
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

pygame.init()
pygame.font.init()

db = None
if os.path.isfile("firebase_key.json"):
	try:
		cred = credentials.Certificate("firebase_key.json")
		firebase_admin.initialize_app(cred)
		db = firestore.client()
	except Exception as e:
		print(f"Firebase init failed: {e}")
else:
	print("firebase_key.json not found — leaderboard disabled.")

inputMode = None
trainingMode = False

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = pygame.font.Font(None, 36)
PULSOID_TOKEN = os.environ.get("PULSOID_TOKEN")

SCREEN = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
glViewport(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
pygame.display.set_caption("Heart Beat Devil")

class InputMode(Enum):
	HEART_RATE = 1
	EMOTION = 2

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

#2D UI Render Layer
def begin_2d():
	glMatrixMode(GL_PROJECTION)
	glPushMatrix()
	glLoadIdentity()
	glOrtho(0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, -1, 1)

	glMatrixMode(GL_MODELVIEW)
	glPushMatrix()
	glLoadIdentity()
	glDisable(GL_DEPTH_TEST)

def end_2d():
	glEnable(GL_DEPTH_TEST)
	glPopMatrix()
	glMatrixMode(GL_PROJECTION)
	glPopMatrix()
	glMatrixMode(GL_MODELVIEW)

def draw_text(text, x, y):
	"""renders text to OpenGL with the use of glDrawPixels"""
	surface = FONT.render(text, True, WHITE)
	text_data = pygame.image.tostring(surface, "RGBA", True)
	glRasterPos2f(x, y)
	glDrawPixels(surface.get_width(), surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

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

				valid_emotions = ["HAPPY", "NEUTRAL", "ANGRY"]
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
#=================================================================
def submit_score(level_name, player_name, time_seconds, deaths):
	if db is None:
		return
	try:
		db.collection("leaderboards").add({
			"level": level_name,
			"player": player_name,
			"time": round(time_seconds, 2),
			"deaths": deaths,
			"timestamp": firestore.SERVER_TIMESTAMP
		})
	except Exception as e:
		print("Firebase submit error:", e)

def get_top_scores(level_name, limit=5):
	if db is None:
		return []
	try:
		query = (
			db.collection("leaderboards")
			.where("level", "==", level_name)
			.order_by("time")
			.limit(limit)
		)

		scores = []

		for doc in query.stream():
			scores.append(doc.to_dict())

		return scores
	except Exception as e:
		print("Leaderboard fetch error:", e)
		return []
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

		current_speed = sprintSpeed if keys[K_LSHIFT] else speed

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
			self.vel_y = 10
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
		px, py, pz = player.pos
		dx, dy, dz = self.pos
		sx, sy, sz = self.size

		player_half = 1

		in_xz = (
			abs(px - dx) < (sx * 0.5 + player_half) and
			abs(pz - dz) < (sz * 0.5 + player_half)
		)

		in_y = abs(py - dy) < (sy * 0.5)

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

#===================================================================
class LevelSelection:
	_LEVELS = [
		("Level 1", "level1", "Platform jumps  ·  Spike traps"),
		("Level 2", "level2", "Moving platforms  ·  Greater heights"),
		("Level 3  [WIP]", "level3", "Enemies  ·  Grapple hook  ·  Boss?"),
	]
	_BW, _BH, _BGAP = 480, 80, 20

	def __init__(self):
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self._bg = _MenuBG(55)
		self._ht = [0.0] * len(self._LEVELS)
		cx = SCREEN_WIDTH // 2
		base_y = 420
		self._rects = []
		for i in range(len(self._LEVELS)):
			r = pygame.Rect(0, 0, self._BW, self._BH)
			r.center = (cx, base_y + i * (self._BH + self._BGAP))
			self._rects.append(r)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				return MainMenu()
			if event.type == MOUSEBUTTONDOWN and event.button == 1:
				for i, rect in enumerate(self._rects):
					if rect.collidepoint(event.pos):
						return ("start", self._LEVELS[i][1])

	def update(self, dt):
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		for i, rect in enumerate(self._rects):
			t = 1.0 if rect.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*C_BG, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()

		cx = SCREEN_WIDTH // 2
		_blit_centered(HEADING_FONT, "SELECT LEVEL", C_RED_BRIGHT, cx, 140)

		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 240, 215); glVertex2f(cx + 240, 215)
		glEnd()
		_blit_centered(LABEL_FONT, "Choose your challenge", C_TEXT_DIM, cx, 230)
		_blit_centered(SMALL_FONT, "ESC  ←  Main Menu", C_TEXT_DIM, cx, SCREEN_HEIGHT - 30)

		for i, (label, _, desc) in enumerate(self._LEVELS):
			rect = self._rects[i]
			ht = self._ht[i]
			_ui_button(rect, "", ht)
			# Level number badge
			badge_w = 50
			badge_col = _lerp_color(C_RED_DIM, C_RED_BRIGHT, ht)
			_draw_gl_rect(rect.left + 3, rect.top + 3,
			              badge_w, rect.height - 6,
			              badge_col[0]/255, badge_col[1]/255, badge_col[2]/255, 0.25)
			_blit_centered(HEADING_FONT, str(i + 1),
			               _lerp_color((160, 60, 60), C_WHITE, ht),
			               rect.left + 28, rect.top + 14)
			# Label + description
			_blit_left(MENU_FONT,  label, _lerp_color((160, 155, 165), C_WHITE, ht),
			           rect.left + 70, rect.top + 10)
			_blit_left(SMALL_FONT, desc,  C_TEXT_DIM, rect.left + 70, rect.top + 50)

		end_2d()
#=======================================================================================
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

		self.spike_model = OBJModel("models/SpikeTrap.obj")

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

		if inputMode == InputMode.HEART_RATE:
			if bpm is not None:
				self.player.bpm = bpm

		elif inputMode == InputMode.EMOTION:
			self.player.emotion = emotion #====

		self.player.mouse()

		keys = pygame.key.get_pressed()
		self.player.move(keys, dt)
		self.player.gravity_apply(dt)
		self.player.update_effects(dt)
		self.level.collide(self.player)

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()

		if self.door.check_collision(self.player): #This line checks for the collision between player and door object
			self.finish_time = time.time() - self.start_time

			self.next_state = NameEntryScreen("Level 1", self.finish_time, self.player.deaths, self.door.targetLevel)



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
		if inputMode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"

		elif inputMode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if trainingMode else "OFF"

		draw_text("Level One", 20, 40) #Debugging purpose
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)

		draw_text(f"BPM: {self.player.bpm}", 20, 120)
		draw_text(f"Emotion: {self.player.emotion}", 20, 140)
		draw_text(f"Time: {elapsed:.2f}s", 20, 160)
		if self.finish_time is not None:
			draw_text(f"Completed In: {self.finish_time:.2f}s", 20, 200)
		draw_screen_effects(self.player)

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

		if inputMode == InputMode.HEART_RATE:
			if bpm is not None:
				self.player.bpm = bpm

		elif inputMode == InputMode.EMOTION:
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

		self.level.collide(self.player)

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()

		if self.door.check_collision(self.player):
			self.finish_time = time.time() - self.start_time

			self.next_state = NameEntryScreen("Level 2", self.finish_time, self.player.deaths, self.door.targetLevel)

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
		if inputMode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"
		elif inputMode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if trainingMode else "OFF"

		draw_text("Level Two", 20, 40)
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)

		draw_text(f"BPM: {self.player.bpm}", 20, 120)
#		draw_text(f"Emotion: {self.player.emotion}", 20, 140) 
		draw_text(f"Time: {elapsed:.2f}s", 20, 160)
		if self.finish_time is not None:
			draw_text(f"Completed In: {self.finish_time:.2f}s", 20, 200)
		draw_screen_effects(self.player)

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

		self.spike_model = OBJModel("models/SpikeTrap.obj")
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
		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		pygame.mouse.get_rel()

	def update(self, dt):
		bpm, emotion = receiver.get_data()

		if inputMode == InputMode.HEART_RATE:
			if bpm is not None:
				self.player.bpm = bpm
		elif inputMode == InputMode.EMOTION:
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
		if self.door.check_collision(self.player):
			self.finish_time = time.time() - self.start_time
			
			self.next_state = NameEntryScreen("Level 3", self.finish_time,
			self.player.deaths, self.door.targetLevel)

		for spike in self.spikes:
			if spike.check_collision(self.player):
				self.player.respawn()

		bpm_factor = self.player.get_bpm_factor()

		for plat in self.level.moving_platforms:
			plat.update_bpm(bpm_factor)
			plat.update(dt)

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
		if inputMode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"
		elif inputMode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if trainingMode else "OFF"

		draw_text("Level Three (WIP)", 20, 40)
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)
		draw_text(f"BPM: {self.player.bpm}", 20, 120)
		draw_text(f"Time: {elapsed:.2f}s", 20, 160)
		if self.finish_time is not None:
			draw_text(f"Completed In: {self.finish_time:.2f}s", 20, 200)
#		draw_text(f"Emotion: {self.player.emotion}", 20, 140)
		draw_screen_effects(self.player)
		
		draw_text(f"FPS: {int(fps)}", SCREEN_WIDTH - 120, 20)

		end_2d()

#========================================================================================
# ── Shared UI system ────────────────────────────────────────────────────────────────
TITLE_FONT    = pygame.font.Font(None, 110)
HEADING_FONT  = pygame.font.Font(None, 72)
MENU_FONT     = pygame.font.Font(None, 48)
LABEL_FONT    = pygame.font.Font(None, 34)
SMALL_FONT    = pygame.font.Font(None, 26)

# Palette
C_BG         = (0.03, 0.03, 0.05)   # near-black navy
C_PANEL      = (8,  10,  18)         # dark navy panel
C_RED        = (220, 40,  40)
C_RED_DIM    = (120, 20,  20)
C_RED_BRIGHT = (255, 80,  80)
C_ACCENT     = (255, 200, 60)        # gold accent for ranks/labels
C_TEXT       = (210, 210, 220)
C_TEXT_DIM   = (100, 105, 120)
C_WHITE      = (255, 255, 255)

def _lerp(a, b, t):
	return a + (b - a) * t

def _lerp_color(c1, c2, t):
	return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def _draw_gl_rect(x, y, w, h, r, g, b, a=1.0):
	glColor4f(r, g, b, a)
	glBegin(GL_QUADS)
	glVertex2f(x,     y)
	glVertex2f(x + w, y)
	glVertex2f(x + w, y + h)
	glVertex2f(x,     y + h)
	glEnd()

def _draw_gl_border(x, y, w, h, r, g, b, a=1.0, lw=1.0):
	glColor4f(r, g, b, a)
	glLineWidth(lw)
	glBegin(GL_LINE_LOOP)
	glVertex2f(x,     y)
	glVertex2f(x + w, y)
	glVertex2f(x + w, y + h)
	glVertex2f(x,     y + h)
	glEnd()
	glLineWidth(1.0)

def draw_text_surface(surface, x, y):
	# y is screen-space top-left (y=0 is top). glDrawPixels draws upward from raster pos,
	# so we place raster at the bottom edge (y + h) and flip the surface vertically.
	flipped = pygame.transform.flip(surface, False, True)
	text_data = pygame.image.tostring(flipped, "RGBA", False)
	sh = surface.get_height()
	glRasterPos2f(x, y + sh)
	glDrawPixels(surface.get_width(), sh, GL_RGBA, GL_UNSIGNED_BYTE, text_data)

# All _blit helpers take screen-space y (y=0 is top of screen).
def _blit_centered(font, text, color, cx, y, max_alpha=255):
	surf = font.render(text, True, color)
	if max_alpha < 255:
		surf.set_alpha(max_alpha)
	sw, sh = surf.get_size()
	draw_text_surface(surf, cx - sw // 2, y)

def _blit_left(font, text, color, x, y):
	surf = font.render(text, True, color)
	draw_text_surface(surf, x, y)

def _blit_right(font, text, color, right_x, y):
	surf = font.render(text, True, color)
	sw, sh = surf.get_size()
	draw_text_surface(surf, right_x - sw, y)

# Shared animated background: dark navy + slow red grid + drifting particles
class _MenuBG:
	def __init__(self, n_particles=60):
		self._p = [self._new() for _ in range(n_particles)]
		self._time = 0.0

	def _new(self):
		return {
			"x": random.uniform(0, SCREEN_WIDTH),
			"y": random.uniform(0, SCREEN_HEIGHT),
			"vy": random.uniform(8, 35),
			"alpha": random.uniform(0.04, 0.18),
			"size": random.uniform(1, 2.5),
		}

	def update(self, dt):
		self._time += dt
		for p in self._p:
			p["y"] += p["vy"] * dt
			if p["y"] > SCREEN_HEIGHT + 4:
				p["y"] = -4
				p["x"] = random.uniform(0, SCREEN_WIDTH)

	def draw(self):
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		# Base
		_draw_gl_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, *C_BG)

		# Vignette
		for i in range(10):
			t = i / 10
			mx, my = SCREEN_WIDTH * 0.5, SCREEN_HEIGHT * 0.5
			rx = SCREEN_WIDTH  * (0.05 + t * 0.5)
			ry = SCREEN_HEIGHT * (0.05 + t * 0.5)
			alpha = (1 - t) * 0.35
			_draw_gl_rect(mx - rx, my - ry, rx * 2, ry * 2,
			              0.28, 0.0, 0.02, alpha)

		# Animated grid
		t = self._time
		grid_alpha = 0.06
		glColor4f(0.6, 0.05, 0.05, grid_alpha)
		glLineWidth(1.0)
		step = 80
		for gx in range(0, SCREEN_WIDTH + step, step):
			glBegin(GL_LINES)
			glVertex2f(gx, 0)
			glVertex2f(gx, SCREEN_HEIGHT)
			glEnd()
		for gy in range(0, SCREEN_HEIGHT + step, step):
			glBegin(GL_LINES)
			glVertex2f(0, gy)
			glVertex2f(SCREEN_WIDTH, gy)
			glEnd()

		# Horizontal sweep line
		sweep_y = (SCREEN_HEIGHT * ((t * 0.12) % 1.0))
		for i in range(3):
			a = 0.18 - i * 0.06
			glColor4f(0.8, 0.1, 0.1, a)
			glBegin(GL_LINES)
			glVertex2f(0, sweep_y + i * 2)
			glVertex2f(SCREEN_WIDTH, sweep_y + i * 2)
			glEnd()

		# Particles
		glPointSize(2.0)
		glBegin(GL_POINTS)
		for p in self._p:
			glColor4f(1.0, 0.2, 0.2, p["alpha"])
			glVertex2f(p["x"], p["y"])
		glEnd()
		glPointSize(1.0)

# Shared button renderer — used by all menus
def _ui_button(rect, label, hover_t, font=None):
	if font is None:
		font = MENU_FONT
	x, y, w, h = rect.left, rect.top, rect.width, rect.height

	# Glass panel bg
	bg = _lerp_color(C_PANEL, (25, 6, 6), hover_t)
	_draw_gl_rect(x, y, w, h, bg[0]/255, bg[1]/255, bg[2]/255, 0.92)

	# Inner highlight strip at top
	_draw_gl_rect(x + 2, y + 1, w - 4, 2,
	              1.0, 1.0, 1.0, 0.04 + hover_t * 0.08)

	# Animated left bar
	bar_h = int(h * _lerp(0.35, 1.0, hover_t))
	bar_y = y + (h - bar_h) // 2
	bar_c = _lerp_color(C_RED_DIM, C_RED_BRIGHT, hover_t)
	_draw_gl_rect(x, bar_y, 3, bar_h,
	              bar_c[0]/255, bar_c[1]/255, bar_c[2]/255)

	# Border
	bc = _lerp_color((45, 20, 20), (200, 50, 50), hover_t)
	_draw_gl_border(x, y, w, h, bc[0]/255, bc[1]/255, bc[2]/255,
	                0.7 + hover_t * 0.3, 1.0 + hover_t)

	# Hover fill flash
	if hover_t > 0.01:
		_draw_gl_rect(x + 3, y + 1, w - 3, h - 2,
		              0.9, 0.15, 0.15, hover_t * 0.07)

	# Label
	tc = _lerp_color((160, 155, 165), C_WHITE, hover_t)
	lsurf = font.render(label, True, tc)
	lw, lh = lsurf.get_size()
	sc = 1.0 + hover_t * 0.03
	if sc > 1.005:
		lsurf = pygame.transform.smoothscale(lsurf,
		                                      (int(lw * sc), int(lh * sc)))
		lw, lh = lsurf.get_size()
	draw_text_surface(lsurf,
	                  rect.centerx - lw // 2,
	                  rect.centery - lh // 2)

class MainMenu:
	_BW, _BH, _BGAP = 360, 64, 16
	_BUTTONS = [("Start Game", "start"), ("Level Select", "lvlSelection"), ("Quit", "quit")]

	def __init__(self):
		self.next_state = None
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self._bg = _MenuBG(70)
		self._ht = [0.0] * len(self._BUTTONS)
		cx = SCREEN_WIDTH // 2
		base_y = 520
		self._rects = []
		for i in range(len(self._BUTTONS)):
			r = pygame.Rect(0, 0, self._BW, self._BH)
			r.center = (cx, base_y + i * (self._BH + self._BGAP))
			self._rects.append(r)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				for i, rect in enumerate(self._rects):
					if rect.collidepoint(event.pos):
						return self._BUTTONS[i][1]

	def update(self, dt):
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		for i, rect in enumerate(self._rects):
			t = 1.0 if rect.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)

	def draw(self):
		ticks = pygame.time.get_ticks()
		pulse = (math.sin(ticks * 0.0018) + 1) * 0.5

		glClearColor(*C_BG, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		self._bg.draw()

		cx = SCREEN_WIDTH // 2

		# ── Title glow layers ────────────────────────────────────────
		for off, sz, ga in [(8, 118, 30), (4, 112, 50)]:
			g = pygame.font.Font(None, sz).render("HEART BEAT DEVIL", True, C_RED)
			g.set_alpha(int(ga + pulse * 22))
			gw, gh = g.get_size()
			draw_text_surface(g, cx - gw // 2, 160 - off)

		tc = _lerp_color((215, 30, 30), (255, 95, 95), pulse)
		_blit_centered(TITLE_FONT, "HEART BEAT DEVIL", tc, cx, 155)

		# ── Divider + tagline ────────────────────────────────────────
		div_y = 285
		glColor4f(0.65, 0.10, 0.10, 0.55)
		glLineWidth(1.0)
		glBegin(GL_LINES)
		glVertex2f(cx - 280, div_y); glVertex2f(cx + 280, div_y)
		glEnd()

		ds = 5
		glColor4f(0.9, 0.2, 0.2, 0.85)
		glBegin(GL_QUADS)
		glVertex2f(cx,      div_y - ds)
		glVertex2f(cx + ds, div_y)
		glVertex2f(cx,      div_y + ds)
		glVertex2f(cx - ds, div_y)
		glEnd()

		_blit_centered(LABEL_FONT, "FEEL THE BEAT  ·  SURVIVE THE DEVIL", C_TEXT_DIM, cx, 300)

		# ── Buttons ──────────────────────────────────────────────────
		for i, (label, _) in enumerate(self._BUTTONS):
			_ui_button(self._rects[i], label, self._ht[i])

		_blit_centered(SMALL_FONT, "ESC to quit", C_TEXT_DIM, cx, SCREEN_HEIGHT - 30)
		_blit_right(SMALL_FONT, "v0.5", C_TEXT_DIM, SCREEN_WIDTH - 24, SCREEN_HEIGHT - 30)

		end_2d()
#================================================================
class LvlComplete:
	def __init__(self, level_name, finish_time, deaths, next_level):
		self.level_name = level_name
		self.finish_time = finish_time
		self.deaths = deaths
		self.next_level = next_level
		self.next_state = None
		self._cont_ht = 0.0
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.scores = get_top_scores(level_name)
		self.CONTINUE_RECT = pygame.Rect(0, 0, 300, 58)
		self.CONTINUE_RECT.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN:
				if self.CONTINUE_RECT.collidepoint(event.pos):
					self.next_state = self.next_level

	def update(self, dt):
		t = 1.0 if self.CONTINUE_RECT.collidepoint(pygame.mouse.get_pos()) else 0.0
		self._cont_ht += (t - self._cont_ht) * min(1.0, dt * 12)

	def draw(self):
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		# Dark overlay over game world
		_draw_gl_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0, 0.78)

		cx = SCREEN_WIDTH // 2
		cy = SCREEN_HEIGHT // 2 - 140

		# Floating panel
		pw, ph = 500, 320
		px, py = cx - pw // 2, cy
		_draw_gl_rect(px, py, pw, ph, C_PANEL[0]/255, C_PANEL[1]/255, C_PANEL[2]/255, 0.95)
		_draw_gl_border(px, py, pw, ph, 0.6, 0.1, 0.1, 0.6)
		_draw_gl_rect(px, py, pw, 3, 0.8, 0.15, 0.15, 1.0)

		_blit_centered(HEADING_FONT, "LEVEL COMPLETE", C_RED_BRIGHT, cx, cy + 30)

		glColor4f(0.5, 0.08, 0.08, 0.35)
		glBegin(GL_LINES)
		glVertex2f(px + 30, cy + 90); glVertex2f(px + pw - 30, cy + 90)
		glEnd()

		col_l = cx - 100
		col_r = cx + 100
		_blit_centered(SMALL_FONT, "TIME",   C_TEXT_DIM, col_l, cy + 120)
		_blit_centered(MENU_FONT,  f"{self.finish_time:.2f}s", C_ACCENT, col_l, cy + 155)
		_blit_centered(SMALL_FONT, "DEATHS", C_TEXT_DIM, col_r, cy + 120)
		_blit_centered(MENU_FONT,  str(self.deaths), C_RED_BRIGHT, col_r, cy + 155)

		_ui_button(self.CONTINUE_RECT, "Continue", self._cont_ht)
		end_2d()

#================================================================
class PauseMenu:
	_BW, _BH, _BGAP = 320, 58, 16
	_BUTTONS = [("Resume", None), ("Main Menu", "menu"), ("Quit Game", "quit")]

	def __init__(self, previous_state):
		self.previous_state = previous_state
		self._ht = [0.0] * len(self._BUTTONS)
		cx = SCREEN_WIDTH // 2
		base_y = SCREEN_HEIGHT // 2 + 30
		self._rects = []
		for i in range(len(self._BUTTONS)):
			r = pygame.Rect(0, 0, self._BW, self._BH)
			r.center = (cx, base_y + i * (self._BH + self._BGAP))
			self._rects.append(r)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				return self.previous_state
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				if self._rects[0].collidepoint(event.pos):
					return self.previous_state
				if self._rects[1].collidepoint(event.pos):
					return MainMenu()
				if self._rects[2].collidepoint(event.pos):
					return "quit"

	def update(self, dt):
		mp = pygame.mouse.get_pos()
		for i, rect in enumerate(self._rects):
			t = 1.0 if rect.collidepoint(mp) else 0.0
			self._ht[i] += (t - self._ht[i]) * min(1.0, dt * 12)

	def draw(self):
		self.previous_state.draw()
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		# Full-screen blur overlay
		_draw_gl_rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0, 0.72)

		# Thin red horizontal rule across middle
		cy = SCREEN_HEIGHT // 2 - 80
		glColor4f(0.7, 0.1, 0.1, 0.4)
		glLineWidth(1.0)
		glBegin(GL_LINES)
		glVertex2f(0, cy); glVertex2f(SCREEN_WIDTH, cy)
		glEnd()

		cx = SCREEN_WIDTH // 2

		# Panel behind content
		pw, ph = 420, 340
		px, py = cx - pw // 2, cy - 30
		_draw_gl_rect(px, py, pw, ph, 0.04, 0.04, 0.08, 0.88)
		_draw_gl_border(px, py, pw, ph, 0.6, 0.1, 0.1, 0.5, 1.0)

		# "PAUSED" heading
		_blit_centered(HEADING_FONT, "PAUSED", C_RED_BRIGHT, cx, cy - 20)

		# Small rule under heading
		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 100, cy + 50); glVertex2f(cx + 100, cy + 50)
		glEnd()

		for i, (label, _) in enumerate(self._BUTTONS):
			_ui_button(self._rects[i], label, self._ht[i])

		end_2d()

#===================================================================================
class NameEntryScreen:
	def __init__(self, level_name, finish_time, deaths, next_level):
		self.level_name = level_name
		self.finish_time = finish_time
		self.deaths = deaths
		self.next_level = next_level
		self.next_state = None
		self.player_name = ""
		self._bg = _MenuBG(40)
		self._submit_ht = 0.0
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.SUBMIT_RECT = pygame.Rect(0, 0, 300, 58)
		self.SUBMIT_RECT.center = (SCREEN_WIDTH // 2, 660)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					return MainMenu()
				if event.key == pygame.K_BACKSPACE:
					self.player_name = self.player_name[:-1]
				elif event.key == pygame.K_RETURN:
					if self.player_name.strip():
						return self._submit()
				else:
					if len(self.player_name) < 16 and event.unicode.isprintable():
						self.player_name += event.unicode
			if event.type == pygame.MOUSEBUTTONDOWN:
				if self.SUBMIT_RECT.collidepoint(event.pos) and self.player_name.strip():
					return self._submit()

	def _submit(self):
		submit_score(self.level_name, self.player_name, self.finish_time, self.deaths)
		return LeaderboardScreen(self.level_name, self.next_level)

	def update(self, dt):
		self._bg.update(dt)
		t = 1.0 if self.SUBMIT_RECT.collidepoint(pygame.mouse.get_pos()) else 0.0
		self._submit_ht += (t - self._submit_ht) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*C_BG, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()

		cx = SCREEN_WIDTH // 2

		# Panel
		pw, ph = 560, 420
		px, py = cx - pw // 2, 220
		_draw_gl_rect(px, py, pw, ph, C_PANEL[0]/255, C_PANEL[1]/255, C_PANEL[2]/255, 0.92)
		_draw_gl_border(px, py, pw, ph, 0.55, 0.08, 0.08, 0.6)
		# Top accent bar on panel
		_draw_gl_rect(px, py, pw, 3, 0.8, 0.15, 0.15, 0.9)

		_blit_centered(HEADING_FONT, "LEVEL COMPLETE", C_RED_BRIGHT, cx, 245)

		# Stats row
		glColor4f(0.5, 0.08, 0.08, 0.35)
		glBegin(GL_LINES)
		glVertex2f(px + 30, 335); glVertex2f(px + pw - 30, 335)
		glEnd()

		col_l = cx - 120
		col_r = cx + 120
		_blit_centered(SMALL_FONT, "TIME", C_TEXT_DIM, col_l, 360)
		_blit_centered(MENU_FONT,  f"{self.finish_time:.2f}s", C_ACCENT, col_l, 395)
		_blit_centered(SMALL_FONT, "DEATHS", C_TEXT_DIM, col_r, 360)
		_blit_centered(MENU_FONT,  str(self.deaths), C_RED_BRIGHT, col_r, 395)

		glColor4f(0.5, 0.08, 0.08, 0.35)
		glBegin(GL_LINES)
		glVertex2f(px + 30, 450); glVertex2f(px + pw - 30, 450)
		glEnd()

		_blit_centered(LABEL_FONT, "ENTER YOUR NAME", C_TEXT_DIM, cx, 475)

		# Input box
		iw, ih = 380, 56
		ix, iy = cx - iw // 2, 510
		_draw_gl_rect(ix, iy, iw, ih, 0.06, 0.06, 0.10, 1.0)
		_draw_gl_border(ix, iy, iw, ih, 0.6, 0.12, 0.12, 0.7)
		# cursor blink
		show_cursor = (pygame.time.get_ticks() // 530) % 2 == 0
		display_name = self.player_name + ("|" if show_cursor else " ")
		_blit_centered(MENU_FONT, display_name, C_WHITE, cx, iy + 36)

		_ui_button(self.SUBMIT_RECT, "Submit Score", self._submit_ht)
		end_2d()
#========================================================
class LeaderboardScreen:
	_RANK_COLORS = [(255, 200, 40), (180, 180, 195), (200, 130, 60)]

	def __init__(self, level_name, next_level):
		self.level_name = level_name
		self.next_level = next_level
		self.next_state = None
		self._bg = _MenuBG(45)
		self._cont_ht = 0.0
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.scores = get_top_scores(level_name)
		self.CONTINUE_RECT = pygame.Rect(0, 0, 300, 58)
		self.CONTINUE_RECT.center = (SCREEN_WIDTH // 2, 920)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
				return MainMenu()
			if event.type == pygame.MOUSEBUTTONDOWN:
				if self.CONTINUE_RECT.collidepoint(event.pos):
					return self.next_level

	def update(self, dt):
		self._bg.update(dt)
		t = 1.0 if self.CONTINUE_RECT.collidepoint(pygame.mouse.get_pos()) else 0.0
		self._cont_ht += (t - self._cont_ht) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*C_BG, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		self._bg.draw()

		cx = SCREEN_WIDTH // 2

		_blit_centered(HEADING_FONT, "LEADERBOARD", C_RED_BRIGHT, cx, 90)
		_blit_centered(LABEL_FONT, self.level_name.upper(), C_TEXT_DIM, cx, 155)

		# Divider
		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 300, 175); glVertex2f(cx + 300, 175)
		glEnd()

		if not self.scores:
			_blit_centered(LABEL_FONT, "No scores yet. Be the first!", C_TEXT_DIM, cx, 320)
		else:
			# Column headers
			_blit_left (SMALL_FONT, "RANK", C_TEXT_DIM, cx - 280, 210)
			_blit_left (SMALL_FONT, "PLAYER",   C_TEXT_DIM, cx - 180, 210)
			_blit_right(SMALL_FONT, "TIME",      C_TEXT_DIM, cx + 80,  210)
			_blit_right(SMALL_FONT, "DEATHS",    C_TEXT_DIM, cx + 280, 210)

			glColor4f(0.4, 0.08, 0.08, 0.3)
			glBegin(GL_LINES)
			glVertex2f(cx - 280, 230); glVertex2f(cx + 280, 230)
			glEnd()

			for i, score in enumerate(self.scores):
				row_y_top = 240 + i * 70
				row_y_mid = row_y_top + 38

				# Row bg alternating
				row_a = 0.06 if i % 2 == 0 else 0.0
				_draw_gl_rect(cx - 285, row_y_top, 570, 62, 1, 1, 1, row_a)

				rank_col = self._RANK_COLORS[i] if i < 3 else C_TEXT_DIM
				_blit_left(MENU_FONT,  f"#{i+1}", rank_col, cx - 280, row_y_mid)
				_blit_left(MENU_FONT,  score.get("player", "???"), C_TEXT, cx - 180, row_y_mid)
				_blit_right(MENU_FONT, f"{score['time']:.2f}s", C_ACCENT, cx + 80,  row_y_mid)
				_blit_right(LABEL_FONT,str(score['deaths']),     C_RED,    cx + 280, row_y_mid)

		_ui_button(self.CONTINUE_RECT, "Continue", self._cont_ht)
		end_2d()
#=========================================================
class ModeSelection:
	_BW, _BH, _BGAP = 420, 90, 16

	def __init__(self):
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)
		self.training_mode = False
		self.next_state = None
		self.target_level = "level1"
		self._bg = _MenuBG(50)
		self._ht = [0.0, 0.0, 0.0]

		cx = SCREEN_WIDTH // 2
		base_y = 420
		self.MODE1_RECT = pygame.Rect(0, 0, self._BW, self._BH)
		self.MODE1_RECT.center = (cx, base_y)
		self.MODE2_RECT = pygame.Rect(0, 0, self._BW, self._BH)
		self.MODE2_RECT.center = (cx, base_y + self._BH + self._BGAP)
		self.TRAIN_RECT = pygame.Rect(0, 0, self._BW, 52)
		self.TRAIN_RECT.center = (cx, base_y + 2 * (self._BH + self._BGAP) + 24)

	def handleEvents(self, events):
		global inputMode, trainingMode
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_ESCAPE:
					return MainMenu()
				if event.key == pygame.K_1:
					inputMode = InputMode.HEART_RATE
					trainingMode = self.training_mode
					return self.target_level
				if event.key == pygame.K_2:
					inputMode = InputMode.EMOTION
					trainingMode = self.training_mode
					return self.target_level
				if event.key == pygame.K_t:
					self.training_mode = not self.training_mode
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				mp = event.pos
				if self.MODE1_RECT.collidepoint(mp):
					inputMode = InputMode.HEART_RATE
					trainingMode = self.training_mode
					return self.target_level
				elif self.MODE2_RECT.collidepoint(mp):
					inputMode = InputMode.EMOTION
					trainingMode = self.training_mode
					return self.target_level
				elif self.TRAIN_RECT.collidepoint(mp):
					self.training_mode = not self.training_mode

	def update(self, dt):
		self._bg.update(dt)
		mp = pygame.mouse.get_pos()
		self._ht[0] += ((1.0 if self.MODE1_RECT.collidepoint(mp) else 0.0) - self._ht[0]) * min(1.0, dt * 12)
		self._ht[1] += ((1.0 if self.MODE2_RECT.collidepoint(mp) else 0.0) - self._ht[1]) * min(1.0, dt * 12)
		self._ht[2] += ((1.0 if self.TRAIN_RECT.collidepoint(mp) else 0.0) - self._ht[2]) * min(1.0, dt * 12)

	def draw(self):
		glClearColor(*C_BG, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		begin_2d()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

		self._bg.draw()
		cx = SCREEN_WIDTH // 2

		_blit_centered(HEADING_FONT, "SELECT MODE", C_RED_BRIGHT, cx, 140)

		# Divider
		glColor4f(0.6, 0.1, 0.1, 0.4)
		glBegin(GL_LINES)
		glVertex2f(cx - 220, 215); glVertex2f(cx + 220, 215)
		glEnd()
		_blit_centered(LABEL_FONT, "Choose how your body controls the game", C_TEXT_DIM, cx, 230)
		_blit_centered(SMALL_FONT, "ESC  ←  Main Menu", C_TEXT_DIM, cx, SCREEN_HEIGHT - 30)

		# Mode 1 card
		_ui_button(self.MODE1_RECT, "", self._ht[0])
		_blit_centered(MENU_FONT,  "Heart Rate  [BPM]", C_TEXT, cx, self.MODE1_RECT.top + 12)
		_blit_centered(SMALL_FONT, "Connect a heart-rate monitor  ·  press 1",
		               C_TEXT_DIM, cx, self.MODE1_RECT.top + 52)

		# Mode 2 card
		_ui_button(self.MODE2_RECT, "", self._ht[1])
		_blit_centered(MENU_FONT,  "Facial Emotion", C_TEXT, cx, self.MODE2_RECT.top + 12)
		_blit_centered(SMALL_FONT, "Uses webcam emotion detection  ·  press 2",
		               C_TEXT_DIM, cx, self.MODE2_RECT.top + 52)

		# Training toggle
		tr_on = self.training_mode
		tr_bg = (10, 30, 10) if tr_on else C_PANEL
		_draw_gl_rect(self.TRAIN_RECT.x, self.TRAIN_RECT.y,
		              self.TRAIN_RECT.w, self.TRAIN_RECT.h,
		              tr_bg[0]/255, tr_bg[1]/255, tr_bg[2]/255, 0.9)
		tr_bc = (60, 200, 60) if tr_on else (60, 60, 60)
		_draw_gl_border(self.TRAIN_RECT.x, self.TRAIN_RECT.y,
		                self.TRAIN_RECT.w, self.TRAIN_RECT.h,
		                tr_bc[0]/255, tr_bc[1]/255, tr_bc[2]/255, 0.8)
		status_col = (80, 220, 80) if tr_on else C_TEXT_DIM
		status_label = "Training Mode  ·  ON  [T]" if tr_on else "Training Mode  ·  OFF  [T]"
		_blit_centered(LABEL_FONT, status_label, status_col, cx, self.TRAIN_RECT.top + 16)

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
	currentState = MainMenu() #calls the class and sets it to currentState

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
