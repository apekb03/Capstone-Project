#Created 2/2/2026 11:02PM
#Original Coder James Musick
#In this code you should find game code for RageBait, CS450 Capstone project Team Joy
#VERSION 0.3
import pygame
import json
import sys
from enum import Enum

pygame.init()

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = pygame.font.Font(None, 36)

GROUND_LEVEL = 900
PLATFORM_SPEED = 3

SCREEN = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Rage Bait")

class InputMode(Enum):
	HEART_RATE = 1
	EMOTION = 2

clock = pygame.time.Clock()
heartRate = 0
inputMode = None
trainingMode = False

#Player class===========================================
class Player ( pygame.sprite.Sprite ):

	def __init__(self, x, y):
		super().__init__()

		#Appereance
		self.width = 50
		self.height = 50
		self.color = (25,170, 76)

		self.image = pygame.Surface((self.width, self.height))
		self.image.fill(self.color)

		self.rect = self.image.get_rect(center=(x, y))

		self.vel_x = 0
		self.vel_y = 0
		self.speed = 8
		self.gravity = 2 #is based off of framerate
		self.jumpForce = -33 #-10 is the minimum to get off the ground
		self.isJumping = False
		self.onPlatform = None
		self.platform_dx = 0
		self.platform_dy = 0
	
	def movement(self):
		keys = pygame.key.get_pressed()
		self.vel_x = 0

		if keys[pygame.K_LEFT]:
			self.vel_x = -self.speed
		if keys[pygame.K_RIGHT]:
			self.vel_x = self.speed
		if keys[pygame.K_SPACE] and not self.isJumping:
			self.vel_y = self.jumpForce
			self.isJumping = True
	def grav(self):
		self.vel_y += self.gravity

	def collisionCheck(self, platforms):
		self.rect.x += self.vel_x
		for platform in platforms:
			if self.rect.colliderect(platform.rect):
				if self.vel_x > 0: #moves right
					self.rect.right = platform.rect.left
				elif self.vel_x < 0: #moves left
					self.rect.left = platform.rect.right
		#Vertical collison
		self.rect.y += self.vel_y
		self.onPlatform = None

		for platform in platforms:
			if self.rect.colliderect(platform.rect):

				if self.vel_y > 0:
					self.rect.bottom = platform.rect.top
					self.vel_y = 0
					self.isJumping = False

					self.onPlatform = platform

				elif self.vel_y < 0:
					self.rect.top = platform.rect.bottom
					self.vel_y = 0

	def update(self, platforms):
		self.movement()
		self.grav()
		self.collisionCheck(platforms)

		if self.onPlatform:
			self.rect.x += self.onPlatform.dx
			self.rect.y += self.onPlatform.dy

			if self.onPlatform.type == "falling":
				self.onPlatform.falling = True
			if self.onPlatform.type == "trap":
				if self.onPlatform.timer == 0:
					self.onPlatform.timer = 60 #one second delay
					self.onPlatform.falling = True

player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
all_sprites = pygame.sprite.Group(player)

#=========================================================
class Platform:
	def __init__(self, x, y, w, h, type="static"):
		self.rect = pygame.Rect(x, y, w, h)
		self.type = type

		self.dx = 0
		self.dy = 0

		self.direction = 1
		self.speed = PLATFORM_SPEED

		self.timer = 0
		self.falling = False

	def update(self):
		if self.type == "moving":
			self.dx = self.speed * self.direction
			self.rect.x += self.dx

			if self.rect.left <= 0 or self.rect.right >= SCREEN_WIDTH:
				self.direction *= -1

		if self.type == "falling":
			self.dy += 1
			self.rect.y += self.dy
		
		if self.type == "trap":
			if self.timer > 0:
				self.timer -= 0.5

		if self.timer == 0 and self.falling:
			self.dy += 1
			self.rect.y += self.dy


#========================================================
class LevelSelection:
	def __init__(self):
		#note the arguments for < self.LVL1_RECT = pygame,Rect(200, 200, 150, 100) > are
		#(x, y, width, height)
		self.LVL1_RECT = pygame.Rect(200, 200, 150, 100)
		self.LVL2_RECT = pygame.Rect(400, 200, 150, 100)

	def handleEvents(self, events):
		mousePos = pygame.mouse.get_pos()
		mouseClick = pygame.mouse.get_pressed()

		for event in events:
			if event.type == pygame.QUIT:
				return "quit"
		if self.LVL1_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "level1"
		if self.LVL2_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "level2"

	def update(self):
		pass
	def draw(self):
		SCREEN.fill(BLACK)

		#argument order as follows (screen width and hight, color of the rectangle, and then the object)
		#simplifed (SCREEN, color, object)
		pygame.draw.rect(SCREEN, WHITE, self.LVL1_RECT)
		pygame.draw.rect(SCREEN, WHITE, self.LVL2_RECT)

		lvl1TEXT = FONT.render("Level 1", True, BLACK)
		lvl2TEXT = FONT.render("Level 2", True, BLACK)

		SCREEN.blit(lvl1TEXT, (self.LVL1_RECT.x + 20, self.LVL1_RECT.y + 35))
		SCREEN.blit(lvl2TEXT, (self.LVL2_RECT.x + 20, self.LVL2_RECT.y + 35))
		#LVL one
	#	pygame.draw.rect(SCREEN, (WHITE), (200, 200, 100, 100))
		#melvins lvl 1 location
	#	pygame.draw.rect(SCREEN, (WHITE), (400, 200, 100, 100))
		#mel lvl 2
	#	pygame.draw.rect(SCREEN, (WHITE), (600, 200, 100, 100))
		#mel lvl 3
	#	pygame.draw.rect(SCREEN, (WHITE), (800, 200, 100, 100))
#====================================================================
class Door:
	def __init__(self, x, y, w, h, targetLevel):
		self.rect = pygame.Rect(x, y, w, h)
		self.targetLevel = targetLevel
		self.color = (200, 0, 200)
	
	def draw(self):
		pygame.draw.rect(SCREEN, self.color, self.rect)
#=====================================================================
class Lvl:
	def __init__(self):

		self.player = Player(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)

		self.all_sprites = pygame.sprite.Group(self.player)
		self.platforms = []
		self.doors = []
		self.traps = []

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"

	def update(self):

		for platform in self.platforms:
			platform.update()

		self.all_sprites.update(self.platforms)

		#Door collision
		for door in self.doors:
			if self.player.rect.colliderect(door.rect):
				return door.targetLevel

	def draw(self):
		SCREEN.fill(BLACK)
		for platform in self.platforms:

			color = (255, 0, 0)

			if platform.type == "moving":
				color = (0, 0, 255)
			elif platform.type == "falling":
				color = (255, 165, 0)

			elif platform.type == "trap":
				color = (255, 255, 0)

			pygame.draw.rect(SCREEN, color, platform.rect)

		for door in self.doors:
			door.draw()

		self.all_sprites.draw(SCREEN)
#=====================================================
class LvlOne(Lvl):
	def __init__(self):
		super().__init__()
		self.ground = Platform(0, GROUND_LEVEL, SCREEN_WIDTH, 300)

		#Argument explanation: (x-position, y-position, width, height, type tag for behavior)
		movingPlat = Platform(1000, 720, 300, 50, "moving")
		movingPlat2 = Platform(800, 420, 300, 50, "moving")

		fallingPlat = Platform(600, 500, 200, 50, "falling")

		trapPlat = Platform(300, 550, 200, 50, "trap")
		
		self.platformSpeed = PLATFORM_SPEED
		self.platformDirection = 1

		self.platforms = [self.ground, movingPlat, movingPlat2, fallingPlat, trapPlat]

		door = Door(940, 50, 80, 100, "level2")
		self.doors = [door]

	def draw(self):
		super().draw()

		self.all_sprites.draw(SCREEN)
		HEARTRATE = FONT.render(f"HeartRate: {heartRate}", True, WHITE)
		MODETXT = FONT.render(f"Mode: {inputMode}", True, WHITE)
		SCREEN.blit(MODETXT, (10, 90))
		SCREEN.blit(HEARTRATE, (10,50))


#============================================================================
class LvlTwo(Lvl):
	def __init__(self):
		super().__init__()
		self.ground = Platform(0, GROUND_LEVEL, SCREEN_WIDTH, 300)

		self. platforms = [self.ground]
	def draw(self):
		SCREEN.fill((30, 30, 80))
		super().draw()

		text = FONT.render("Coming Soon", True, WHITE)
		HEARTRATE = FONT.render(f"HeartRate: {heartRate}", True, WHITE)

		SCREEN.blit(HEARTRATE, (10,50))
		SCREEN.blit(text,(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2))

		self.all_sprites.draw(SCREEN)
#==============================================================================
#class LvlThree(Lvl):
#	def __init__(self):

class MainMenu:
	def __init__(self):
		self.TITLE = FONT.render("Heart Beat Devil", True, WHITE)
		self.START_TEXT = FONT.render("Play", True, WHITE)
		self.LEVEL_TEXT = FONT.render("Level Selection", True, WHITE)
		self.QUIT_TEXT = FONT.render("Quit", True, WHITE)

		self.TITLE_RECT = self.TITLE.get_rect(center=(SCREEN_WIDTH//2, 120))
		self.START_RECT = self.START_TEXT.get_rect(center=(SCREEN_WIDTH//2, 235))
		self.LEVEL_RECT = self.LEVEL_TEXT.get_rect(center=(SCREEN_WIDTH//2, 295))
		self.QUIT_RECT = self.QUIT_TEXT.get_rect(center=(SCREEN_WIDTH//2, 355))

	def handleEvents(self, events):
		mousePos = pygame.mouse.get_pos()
		mouseClick = pygame.mouse.get_pressed()

		for event in events:
			if event.type == pygame.QUIT:
				return "quit"

		if self.START_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "modeSelect"

		if self.QUIT_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "quit"

		if self.LEVEL_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "lvlSelection"

	def update(self):
		pass

	def draw(self):
		SCREEN.fill(BLACK)

		SCREEN.blit(self.TITLE, self.TITLE_RECT)
		SCREEN.blit(self.START_TEXT, self.START_RECT)
		SCREEN.blit(self.LEVEL_TEXT, self.LEVEL_RECT)
		SCREEN.blit(self.QUIT_TEXT, self.QUIT_RECT)
#=======================================================================================
class ModeSelection:
	def __init__(self):
		self.training_mode = False

		cx = SCREEN_WIDTH // 2
		self.rect1 = pygame.Rect(cx - 200, 280, 400, 80)
		self.rect2 = pygame.Rect(cx - 200, 380, 400, 80)
		self.rect_train = pygame.Rect(cx - 200, 480, 400, 50)

	def handleEvents(self, events):
		global inputMode, trainingMode

		mousePos = pygame.mouse.get_pos()

		for event in events:

			if event.type == pygame.QUIT:
				return "quit"

			if event.type == pygame.KEYDOWN:
				if event.key == pygame.K_1:
					inputMode = InputMode.HEART_RATE
					trainingMode = self.training_mode
					return "level1"

				if event.type == pygame.K_2:
					inputMode = InputMode.EMOTION
					trainingMode = self.training_mode
					return "level1"

				if event.key == pygame.K_t:
					self.training_mode = not self.training_mode
			if event.type == pygame.MOUSEBUTTONDOWN:
				if self.rect1.collidepoint(mousePos):
					inputMode = InputMode.HEART_RATE
					trainingMode = self.training_mode
					return "level1"
				if self.rect_train.collidepoint(mousePos):
					self.training_mode = not self.training_mode


	def update(self):
		pass

	def draw(self):

		SCREEN.fill((10, 5, 20))

		cx = SCREEN_WIDTH // 2
		title = FONT.render("Heart Beat Devil", True, (255,0,255))
		SCREEN.blit(title, (cx - title.get_width()//2, 80))

		text = FONT.render("Select Input Mode", True, WHITE)
		SCREEN.blit(text, (cx - text.get_width()//2, 180))

		mousePos = pygame.mouse.get_pos()

		color1 = (230,255,230) if self.rect1.collidepoint(mousePos) else (150,220,150)
		pygame.draw.rect(SCREEN, (30,40,30), self.rect1)
		pygame.draw.rect(SCREEN, color1, self.rect1, 2)

		txt1 = FONT.render("1. Heart Rate (BPM)", True, color1)
		SCREEN.blit(txt1, (self.rect1.x + 50, self.rect1.y + 20))

		color2 =  (230,230,255) if self.rect2.collidepoint(mousePos) else (150,150,220)
		pygame.draw.rect(SCREEN, (30,30,40), self.rect2)
		pygame.draw.rect(SCREEN, color2, self.rect2, 2)

		txt2 = FONT.render("2. Facial Emotion", True, color2)
		SCREEN.blit(txt2, (self.rect1.x + 50, self.rect2.y + 20))

		col_tr = (100,255,100) if self.training_mode else (100,100,100)
		bg_tr = (20,50,20) if self.training_mode else (30,30,30)

		pygame.draw.rect(SCREEN, bg_tr, self.rect_train)
		pygame.draw.rect(SCREEN, col_tr, self.rect_train, 2)

		status = "ON" if self.training_mode else "OFF"

		trTxt = FONT.render(f"Training Mode: {status}", True, col_tr)
		SCREEN.blit(trTxt, (self.rect_train.x + 60, self.rect_train.y + 10))

#======================================================================================
def main_menu():
	currentState = MainMenu()

	menu = True
	while menu:

		events = pygame.event.get()
		result = None

		if hasattr(currentState, "handleEvents"):
			result = currentState.handleEvents(events)

		if result == "quit":
			menu  = False

		elif result == "modeSelect":
			currentState = ModeSelection()

		elif result == "level1":
			print("Mode Selected:",inputMode)
			print("Training Mode:", trainingMode)
			currentState = LvlOne()

		elif result == "level2":
			currentState = LvlTwo()
		elif result == "lvlSelection":
			currentState = LevelSelection()

		if hasattr(currentState, "update"):
			result = currentState.update()
			if result == "level2":
				currentState = LvlTwo()

		currentState.draw()
		pygame.display.flip()
		clock.tick(60)

	pygame.quit()

if __name__ == "__main__":
	main_menu()
