#Created 2/2/2026 11:02PM
#Original Coder James Musick
#3D version of rageBait Version 0.04
import pygame
import json
import sys
import socket
import threading

from enum import Enum
from dataclasses import dataclass

from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

pygame.init()

inputMode = None
trainingMode = False

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = pygame.font.Font(None, 36)


SCREEN = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Heart Beat Devil")

class InputMode(Enum):
	HEART_RATE = 1
	EMOTION = 2

#OpenGL Matrixs and setups----
glMatrixMode(GL_PROJECTION)
glLoadIdentity()
gluPerspective(90, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, 100.0)
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
#Platform arguments  [x, y, z] X controls the - = left and + = right, Y is ground.
#z controls forward and backward  with + = forward and - = backward
#PLATFORM_POS = [5, 2, 0]

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

#Below is the multi-input reciver class and variable related to running the heart beat
#================================================================================
def clamp(val, min_val, max_val):
	return max(min_val, min(max_val, val))

UDP_BIND_IP = "0.0.0.0"
UDP_PORT = 5005
UDP_TIMEOUT = 0.5

class MultiInputReceiver:
	def __init__(self, bind_ip = UDP_BIND_IP, port = UDP_PORT):
		self.bind_ip = bind_ip
		self.port = port
		self._latest_bpm = None
		self._latest_emotion = "NEUTRAL"
		self._lock = threading.Lock()
		self._stop = threading.Event()
		self._thread = None

	def start(self):
		if self._thread and self._thead.is_alive():
			return
		self._stop.clear()
		self._thread = threading.Thread(target = self._run, daemon = True)
		self._thread.start()

	def stop(self):
		self._stop.set()

	def get_data(self):
		with self._lock:
			return self._latest_bpm, self._latest_emotion

	def _parse_bpm(self, msg: str):
		if msg.startwith("{") and "bpm" in msg.lower():
			try:
				obj = json.loads(msg)
				return int(float(obj.get("bpm", 0)))
			except: pass
		if ":" in msg:
			parts = msg.split(":")
			for p in reversed(parts):
				clean = "".join(c for c in p if c.isdigit() or c == '.')
				if clean:
					return int(float(clean))
		clean = "".join(c for c in msg if c.isdigit() or c == '.')
		if clean:
			return int(float(clean))
		return None

	def _run(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.settimeout(UDP_TIMEOUT)
		try:
			sock.bind((self.bind_ip, self.port))
		except OSError:
			print(f"UDP Port {self.port} busy. Live input disabled.")
			return

		while not self._stop.is_set():
			try:
				data, _addr = sock.recvfrom(512)
				msg = data.decode("utf-8", errors="ignore").strip().upper()

				valid_emotion = ["HAPPY", "NEUTRAL", "SAD", "ANGRY", "FEAR", "SURPRISED"]
				found_emotion = False

				for emo in valid_emotions:
					if emo in msg:
						with self._lock:
							self._latest_emotion = emo
						found_emotion = True
						break
				if not found_emotion:
					bpm = self._parse_emotion(msg)
					if bpm is not None:
						bpm = int(clamp(bpm, 40, 180))
						with self._lock:
							self._latest_bpm = bpm

			except socket.timeout:
				continue
			except Exception as e:
				continue
receiver = MultiInputReceiver()
receiver.start()
#===============================================================================
class Player:
	def __init__(self, spawn_pos = [0, 2, 35]):
		self.spawn_pos = list(spawn_pos)
		self.pos = list(spawn_pos)
		self.vel_y = 0
		self.speed = 6
		self.gravity = -15
		self.jump = False

		self.yaw = 90
		self.pitch = -30
		self.sens = 0.1 # sens stands for Sensitivity

		self.bpm = 80
		self.emotion = "NEUTRAL"

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
		speed = self.speed * dt

		if keys[K_w]:
			self.pos[0] += flat[0]*speed
			self.pos[2] += flat[2]*speed

		if keys[K_s]:
			self.pos[0] -= flat[0]*speed
			self.pos[2] -= flat[2]*speed

		if keys[K_d]:
			self.pos[0] -= right[0]*speed
			self.pos[2] -= right[2]*speed

		if keys[K_a]:
			self.pos[0] += right[0]*speed
			self.pos[2] += right[2]*speed

		if keys[K_SPACE] and not self.jump:
			self.vel_y = 10
			self.jump = True

	def gravity_apply(self, dt):
		self.vel_y += self.gravity*dt
		self.pos[1] += self.vel_y*dt

	def camera(self):
		x, y, z = self.pos[0], self.pos[1] +1.5, self.pos[2]
		f = self.front()
		gluLookAt(x, y, z, x+f[0], y+f[1], z+f[2], 0, 1, 0)

	def respawn(self):
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
		draw_object(self.pos, self.size[0], self.size[1], self.size[2], (1, 0, 1))

	def check_collision(self, player):
		player_half = 1
		return (
			abs(player.pos[0] - self.pos[0]) < (self.size[0] + player_half) and
			abs(player.pos[1] - self.pos[1]) < (self.size[1] + player_half) and
			abs(player.pos[2] - self.pos[2]) < (self.size[2] + player_half)
		)
#=======================================================================================
class LevelSelection:
	def __init__(self):
		self.button_width = 250
		self.button_height = 50
		self.button_spacing = 60

		start_y = 200
		level_y = start_y + self.button_spacing
		#level 1 button
		self.LVL1_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LVL1_RECT.center = (SCREEN_WIDTH// 2, start_y)
		#level 2 button
		self.LVL2_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LVL2_RECT.center = (SCREEN_WIDTH//2, level_y)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == MOUSEBUTTONDOWN and event.button == 1:
				if self.LVL1_RECT.collidepoint(event.pos):
					return "level1"
				if self.LVL2_RECT.collidepoint(event.pos):
					return "level2"

	def update(self, dt):
		pass
	def draw(self):
		#Clears the screen
		glClearColor(0.2, 0.2, 0.2, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		#Calls the 2D OpenGl Render projection
		begin_2d()

		glColor3f(0.4, 0.4, 0.4)

		pygame.draw.rect(SCREEN, (100, 100, 100), self.LVL1_RECT)
		pygame.draw.rect(SCREEN, (100, 100, 100), self.LVL2_RECT)

		draw_text("Level 1", self.LVL1_RECT.centerx - 40, self.LVL1_RECT.centery - 15)
		draw_text("Level 2", self.LVL2_RECT.centerx - 40, self.LVL2_RECT.centery - 15)


		end_2d()
#=======================================================================================
class Lvl:
	def __init__(self):
			#x  y,  z, scale_x, scale_y, scale_z
		self.GROUNDS = [
			[0, -1,  25, 4, 1, 15], #player spawns on this platform
			[0, -1, -40, 4, 1, 15]  #this platfrom has the door on it
		]
		#Platforms have x,y,z  (z is -forward, +back. Y +up & -down. X -left to +Right)
		self.PLATFORMS_POS = [-3,1,2], [-1, 3, -7], [3, 4, -17] 

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

		for plat in self.PLATFORMS_POS:
			top = plat[1] + self.plat_half[1]

			if abs(p.pos[0] - plat[0]) < self.plat_half[0] + self.player_half and \
			   abs(p.pos[2] - plat[2]) < self.plat_half[2] + self.player_half:

				if p.vel_y <= 0 and p.pos[1] >= top and p.pos[1] <= top + self.player_half:
					p.pos[1] = top + self.player_half
					p.vel_y = 0
					p.jump = False

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
		self.level= Lvl()

		self.door = Door([0, 2, -50], [1, 2, 1], "level2") #This is the line you change to move the door

	def handleEvents(self, events):
		for event in events:
			if event.type == QUIT:
				return "quit"
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

		self.level.collide(self.player)

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()

		if self.door.check_collision(self.player):
			return self.door.targetLevel

	def draw(self):
		glClearColor(0.5, 0.7, 1.0, 1)
		glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
		glLoadIdentity()

		self.player.camera()

		self.level.draw()
		self.door.draw()

		begin_2d()

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

		end_2d()
#=========================================================================================================
class LvlTwo:
	def __init__(self):
		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)
		self.player = Player()
		self.level = Lvl()

	def handleEvents(self, events):
		for event in events:
			if event.type == QUIT:
				return "quit"
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

		self.level.collide(self.player)

		if self.player.pos[1] < self.level.DEATH_Y:
			self.player.respawn()

	def draw(self):
		glClearColor(0.5, 0.7, 1.0, 1)
		glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
		glLoadIdentity()

		self.player.camera()
		self.level.draw()

		begin_2d()

		mode_text = "None"
		if inputMode == InputMode.HEART_RATE:
			mode_text = "Heart Rate"
		elif inputMode == InputMode.EMOTION:
			mode_text = "Facial Emotion"

		training_text = "ON" if trainingMode else "OFF"

		draw_text("Level Two", 20, 40)
		draw_text(f"Mode: {mode_text}", 20, 80)
		draw_text(f"Training: {training_text}", 20, 100)

		end_2d()
#========================================================================================
class MainMenu:
	def __init__(self):
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)

		#Button Variables
		self.button_width = 250
		self.button_height = 60
		self.button_spacing = 20

		self.TITLE = FONT.render("Heart Beat Devil", True, WHITE)
		self.TITLE_RECT = self.TITLE.get_rect(center=(SCREEN_WIDTH//2, 120))

		start_y = 235
		level_y = start_y + self.button_spacing + self.button_height #in order to get the button spacing and postion did this
		quit_y = level_y + self.button_spacing + self.button_height   #to take our starting variable and then add the 
							 #spacing variable to get the next y coordinate/postion
		#start button
		self.START_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.START_RECT.center = (SCREEN_WIDTH//2, start_y)
		#level selection button
		self.LEVEL_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.LEVEL_RECT.center = (SCREEN_WIDTH//2, level_y)
		#quit button
		self.QUIT_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.QUIT_RECT.center = (SCREEN_WIDTH//2, quit_y)
		
		#pre rendering
		self.START_TEXT = FONT.render("Start", True, WHITE)
		self.START_TEXT_RECT = self.START_TEXT.get_rect(center = self.START_RECT.center)

		self.LEVEL_TEXT = FONT.render("Level Selection" , True, WHITE)
		self.LEVEL_TEXT_RECT = self.LEVEL_TEXT.get_rect(center = self.LEVEL_RECT.center)

		self.QUIT_TEXT = FONT.render("Quit", True, WHITE)
		self.QUIT_TEXT_RECT = self.QUIT_TEXT.get_rect(center = self.QUIT_RECT.center)

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
			if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
				mousePos = event.pos

				if self.START_RECT.collidepoint(mousePos):
					return "start"
				elif self.LEVEL_RECT.collidepoint(mousePos):
					return "lvlSelection"
				elif self.QUIT_RECT.collidepoint(mousePos):
					return "quit"


	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0, 0, 0, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

		begin_2d()
		#draws the button boxes
		pygame.draw.rect(SCREEN, (100, 100, 100), self.START_RECT)
		pygame.draw.rect(SCREEN, (100, 100, 100), self.LEVEL_RECT)
		pygame.draw.rect(SCREEN, (100, 100, 100), self.QUIT_RECT)

		#draws our button text
		draw_text("Start", self.START_RECT.centerx - 40, self.START_RECT.centery -15)
		draw_text("Level Selection", self.LEVEL_RECT.centerx - 90, self.LEVEL_RECT.centery - 15)
		draw_text("Quit", self.QUIT_RECT.centerx - 25, self.QUIT_RECT.centery - 15)

		#draws title
		draw_text("Heart Beat Devil", SCREEN_WIDTH//2 - 120, 120)

		end_2d()
#==============================================================================================================
class ModeSelection:
	def __init__(self):
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)

		self.training_mode = False
		self.next_state = "level1"

		#Button Variable for selections
		self.button_width = 350
		self.button_height = 100
		self.button_spacing = 20

		cx = SCREEN_WIDTH//2

		start_y = 280
		mode2_y = start_y + self.button_height + self.button_spacing
		train_y = mode2_y + self.button_height + self.button_spacing

		self.MODE1_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MODE1_RECT.center = (cx, start_y)

		self.MODE2_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.MODE2_RECT.center = (cx, mode2_y)

		self.TRAIN_RECT = pygame.Rect(0, 0, self.button_width, self.button_height)
		self.TRAIN_RECT.center = (cx, train_y)

		self.TITLE = FONT.render("Heart Beat Devil", True, WHITE)
		self.TITLE_RECT = self.TITLE.get_rect(center=(cx, 80))

		self.SUBTITLE = FONT.render("Select input mode", True, (255, 0, 255))
		self.SUBTITLE_RET = self.SUBTITLE.get_rect(center=(cx, 180))

		self.MODE1_TEXT = FONT.render("1. Heart Rate (BPM)", True, WHITE)
		self.MODE1_TEXT_RECT = self.MODE1_TEXT.get_rect(center = self.MODE1_RECT.center)

		self.MODE2_TEXT = FONT.render("2. Facial Emotion", True, WHITE)
		self.MODE2_TEXT_RECT = self.MODE2_TEXT.get_rect(center = self.MODE2_RECT.center)

	def handleEvents(self, events):
		global inputMode, trainingMode

		for event in events:
			if event.type == pygame.QUIT:
				return "quit"

			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_1:
					inputMode = InputMode.HEART_RATE
					trainingMode = self.training_mode
					return self.next_state

				if event.key == pygame.K_2:
					inputMode = InputMode.EMOTION
					trainingMode = self.training_mode
					return self.next_state

				if event.key == pygame.K_t:
					self.training_mode = not self.training_mode

			if event.type == pygame.MOUSEBUTTONDOWN and event.button ==  1:
				mousePos = event.pos

				if self.MODE1_RECT.collidepoint(mousePos):
					inputMode = InputMode.HEART_RATE
					trainingMode = self.training_mode
					return self.next_state

				elif self.MODE2_RECT.collidepoint(mousePos):
					inputMode = InputMode.EMOTION
					trainingMode = self.training_mode
					return self.next_state
				elif self.TRAIN_RECT.collidepoint(mousePos):
					self.training_mode = not self.training_mode

		
	def update(self, dt):
		pass

	def draw(self):
		glClearColor(0, 0, 0, 1)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

		begin_2d()

		mousePos = pygame.mouse.get_pos()

		#Hover coloring
		color1 = (150, 220, 150)
		color2 = (150, 150, 220)

		if self.MODE1_RECT.collidepoint(mousePos):
			color1 = (230, 255, 230)

		if self.MODE2_RECT.collidepoint(mousePos):
			color2 = (230, 230, 255)

		#Draws the buttons
		pygame.draw.rect(SCREEN, (30, 40, 30), self.MODE1_RECT)
		pygame.draw.rect(SCREEN, color1, self.MODE1_RECT, 2)

		pygame.draw.rect(SCREEN, (30, 30, 40), self.MODE2_RECT)
		pygame.draw.rect(SCREEN, color2, self.MODE2_RECT, 2)

		#training toggle colors
		col_tr = (100, 255, 100) if self.training_mode else (100, 100, 100)
		bg_tr = (20, 50, 20) if self.training_mode else (30, 30, 30)

		pygame.draw.rect(SCREEN, bg_tr, self.TRAIN_RECT)
		pygame.draw.rect(SCREEN, col_tr, self.TRAIN_RECT, 2)

		#Draws the text
		draw_text("1. Heart Rate (BPM)", self.MODE1_RECT.centerx - 120, self.MODE1_RECT.centery - 15)
		draw_text("2. Facial Emotion", self.MODE2_RECT.centerx - 120, self.MODE2_RECT.centery - 15)

		status = "ON" if self.training_mode else "OFF"
		draw_text(f"Training Mode: {status}", self.TRAIN_RECT.centerx - 130, self.TRAIN_RECT.centery - 10)

		draw_text("Heart Beat Devil", SCREEN_WIDTH//2 - 120, 80)
		draw_text("Select Input Mode", SCREEN_WIDTH//2 - 110, 180)

		end_2d()
#=============================================================================================================
def main_menu():
	currentState = MainMenu() #calls the class and sets it to currentState

	menu = True
	while menu:
		dt = clock.tick(60) / 1000
		events = pygame.event.get()
		result = None

		if hasattr(currentState, "handleEvents"):
			result = currentState.handleEvents(events)

		if result == "quit":
			menu = False

		elif result == "start":
			mode = ModeSelection()
			mode.next_state = "level1"
			currentState = mode

		elif result == "lvlSelection":
			mode = ModeSelection()
			mode.next_state = "levelSelection"
			currentState = mode

		elif result == "levelSelection":
			currentState = LevelSelection()
		elif result == "level1":
			currentState = LvlOne() #loads lvl1
		elif result == "level2":
			currentState = LvlTwo() #placeholder until lvl 2 is built


		result = currentState.update(dt)
		if result == "level2":
			currentState = LvlTwo()
		currentState.draw()

		pygame.display.flip()

	pygame.quit()
if __name__ == "__main__":
	main_menu()
