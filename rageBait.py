#Created 2/2/2026 11:02PM
#Original Coder James Musick
#In this code you should find game code for RageBait, CS450 Capstone project Team Joy
#VERSION 0.3
import pygame
import json

pygame.init()


SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = pygame.font.Font(None, 36)

GROUND_LEVEL = 820

PLATFORM_1 = 620
PLATFORM_SPEED = 2

SCREEN = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Rage Bait")

clock = pygame.time.Clock()
heartRate = 0

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
		self.speed = 5
		self.gravity = 2 #is based off of framerate
		self.jumpForce = -15
		self.isJumping = False
	
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
			if self.rect.colliderect(platform):
				if self.vel_x > 0: #moves right
					self.rect.right = platform.left
				elif self.vel_x < 0: #moves left
					self.rect.left = platform.right
		#Vertical collison
		self.rect.y += self.vel_y
		for platform in platforms:
			if self.rect.colliderect(platform):
				if self.vel_y > 0:
					self.rect.bottom = platform.top
					self.vel_y = 0
					self.isJumping = False
				elif self.vel_y < 0:
					self.rect.top = platform.bottom
					self.vel_y = 0

	def update(self, platforms):
		self.movement()
		self.grav()
		self.collisionCheck(platforms)

player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
all_sprites = pygame.sprite.Group(player)

#=========================================================

#========================================================

def lvlSelect():

	isRunning = True
	while isRunning:
		SCREEN.fill(BLACK)
		delta_time = clock.tick(60) / 1000

		#LVL one
		pygame.draw.rect(SCREEN, (WHITE), (200, 200, 100, 100))
		#melvins lvl 1 location
		pygame.draw.rect(SCREEN, (WHITE), (400, 200, 100, 100))
		#mel lvl 2
		pygame.draw.rect(SCREEN, (WHITE), (600, 200, 100, 100))
		#mel lvl 3
		pygame.draw.rect(SCREEN, (WHITE), (800, 200, 100, 100))
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				levelSelect = False

		pygame.display.flip()

	pygame.quit()
#====================================================================
class Lvl:
	def __init__(self):

		self.player = Player(SCREEN_WIDTH//2, SCREEN_HEIGHT//2)

		self.all_sprites = pygame.sprite.Group(self.player)
		self.platforms = []

	def handleEvents(self, events):
		for event in events:
			if event.type == pygame.QUIT:
				return "quit"

	def update(self):
		self.all_sprites.update(self.platforms)

	def draw(self):
		SCREEN.fill(BLACK)
		for platform in self.platforms:
			pygame.draw.rect(SCREEN, (225, 0, 0), platform)
		self.all_sprites.draw(SCREEN)
#=====================================================
class lvlOne(Lvl):
	def __init__(self):
		super().__init__()
		self.ground = pygame.Rect(0, GROUND_LEVEL, SCREEN_WIDTH, 300)
		self.platform = pygame.Rect(1000, PLATFORM_1, 500, 50)
		self.platforms = [self.ground, self.platform]

	def draw(self):
		SCREEN.fill(BLACK)
		pygame.draw.rect(SCREEN,(0, 255, 0),self.ground)
		pygame.draw.rect(SCREEN,(255, 0, 0),self.platform)
		self.all_sprites.draw(SCREEN)
		HEARTRATE = FONT.render(f"HeartRate: {heartRate}", True, WHITE)
		SCREEN.blit(HEARTRATE,(10,50))

#============================================================================
class lvlTwo(Lvl):
	def __init__(self):
		super().__init__()
		self.ground = pygame.Rect(0, GROUND_LEVEL, SCREEN_WIDTH, 300)
		self.platforms = [self.ground]

	def draw(self):
		SCREEN.fill((30, 30, 80))
		pygame.draw.rect(SCREEN, (0, 255, 0), self.ground)
		text = FONT.render("Coming Soon", True, WHITE)
		SCREEN.blit(text,(SCREEN_WIDTH//2-100, SCREEN_HEIGHT//2))

		self.all_sprites.draw(SCREEN)
#==============================================================================
class MainMenu:
	def __init__(self):
		self.TITLE = FONT.render("Heart Beat Devil", True, WHITE)
		self.START_TEXT = FONT.render("Play", True, WHITE)
		self.LEVEL_TEXT = FONT.render("Level Selection", True, WHITE)
		self.QUIT_TEXT = FONT.render("Quit", True, WHITE)

		self.TITLE_RECT = self.TITLE.get_rect(center=(SCREEN_WIDTH//2-90, 120))
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
			return "level1"

		if self.QUIT_RECT.collidepoint(mousePos) and mouseClick[0]:
			return "quit"

	def update(self):
		pass

	def draw(self):
		SCREEN.fill(BLACK)

		SCREEN.blit(self.TITLE, self.TITLE_RECT)
		SCREEN.blit(self.START_TEXT, self.START_RECT)
		SCREEN.blit(self.LEVEL_TEXT, self.LEVEL_RECT)
		SCREEN.blit(self.QUIT_TEXT, self.QUIT_RECT)
#=======================================================================================

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

		elif result == "level1":
			currentState = lvlOne()
		elif result == "level2":
			currentState = lvlTwo()

		if hasattr(currentState, "update"):
			currentState.update()

		currentState.draw()
		pygame.display.flip()
		clock.tick(60)

	pygame.quit()

if __name__ == "__main__":
	main_menu()
