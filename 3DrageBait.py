#Created 2/2/2026 11:02PM
#Original Coder James Musick
#3D version of rageBait Version 0.02
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math

pygame.init()

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = pygame.font.Font(None, 36)


SCREEN = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Heart Beat Devil")

#pygame.event.set_grab(True)
pygame.mouse.set_visible(False)

#OpenGL Matrixs
glMatrixMode(GL_PROJECTION)
glLoadIdentity()
gluPerspective(90, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, 100.0)

glMatrixMode(GL_MODELVIEW)
glLoadIdentity()

#Ground and platform
GROUND_Y = -1
#Platform arguments  [x, y, z] X controls the - = left and + = right, Y is ground.
#z controls forward and backward  with + = forward and - = backward
#PLATFORM_POS = [5, 2, 0]

clock = pygame.time.Clock()

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

#================================================================================
class Player:
	def __init__(self):
		self.pos=[0,5,0]
		self.vel_y = 0
		self.speed = 6
		self.gravity = -15
		self.jump = False

		self.yaw = 90
		self.pitch = -30
		self.sens = 0.1 # sens stands for Sensitivity

	def mouse(self):
		pygame.mouse.set_pos(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)
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
#=======================================================================================
#=======================================================================================
class Level:
	def __init__(self):
		self.GROUND_Y = -1
		self.PLATFORMS_POS = [5,2,0], [-3, 3, -5], [0, 4, 6]

		self.player_half = 1
		self.ground_half = [5, 20]
		self.plat_half = [1, 0.25, 1]

	def collide(self, p): # the p stands for player
		if abs(p.pos[0]) < self.ground_half[0] + self.player_half and \
		   abs(p.pos[2]) < self.ground_half[1] + self.player_half:

			if p.pos[1] <= self.GROUND_Y + self.player_half:
				p.pos[1] = self.GROUND_Y + self.player_half
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
		draw_object([0, self.GROUND_Y -1, 0], 5,1,20, (1,0,0))
		for p in self.PLATFORMS_POS:
			draw_object(p, 2, 0.5, 2, (0.6, 0.4, 0.2))

#================================================================================
class LvlOne:
	def __init__(self):
		pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF|OPENGL)

		pygame.mouse.set_visible(False)
		pygame.event.set_grab(True)

		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		gluPerspective(90, (SCREEN_WIDTH/SCREEN_HEIGHT), 0.1, 100.0)

		glMatrixMode(GL_MODELVIEW)

		self.player= Player()
		self.level= Level()

	def handleEvents(self, events):
		for event in events:
			if event.type == QUIT:
				return "quit"
	def update(self, dt):
		self.player.mouse()

		keys = pygame.key.get_pressed()
		self.player.move(keys, dt)
		self.player.gravity_apply(dt)

		self.level.collide(self.player)

	def draw(self):
		glClearColor(0.5, 0.7, 1.0, 1)
		glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
		glEnable(GL_DEPTH_TEST)

		glLoadIdentity()
		self.player.camera()

		self.level.draw()
#=========================================================================================================
class MainMenu:
	def __init__(self):
		pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
		pygame.mouse.set_visible(True)
		pygame.event.set_grab(False)

		self.TITLE = FONT.render("Heart Beat Devil", True, WHITE)
		self.START_TEXT = FONT.render("Start", True, WHITE)
		self.QUIT_TEXT = FONT.render("Quit", True, WHITE)

		self.TITLE_RECT = self.TITLE.get_rect(center=(SCREEN_WIDTH//2, 120))
		self.START_RECT = self.START_TEXT.get_rect(center=(SCREEN_WIDTH//2, 235))
		self.QUIT_RECT = self.QUIT_TEXT.get_rect(center=(SCREEN_WIDTH//2, 295))

	def handleEvents(self, events):
		mousePos = pygame.mouse.get_pos()
		mouseClick = pygame.mouse.get_pressed()

		for event in events:
			if event.type == pygame.QUIT:
				return "quit"

		if self.START_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "start"

		if self.QUIT_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "quit"

	def update(self, dt):
		pass

	def draw(self):
		SCREEN.fill(BLACK)

		SCREEN.blit(self.TITLE, self.TITLE_RECT)
		SCREEN.blit(self.START_TEXT, self.START_RECT)
		SCREEN.blit(self.QUIT_TEXT, self.QUIT_RECT)
#==============================================================================================================
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
			currentState = LvlOne()

		if hasattr(currentState, "update"):
			currentState.update(dt)

		currentState.draw()
		pygame.display.flip()

	pygame.quit()
if __name__ == "__main__":
	main_menu()
