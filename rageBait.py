#Created 2/2/2026 11:02PM
#Original Coder James Musick
#In this code you should find game code for RageBait, CS450 Capstone project Team Joy
#VERSION 0.1
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

screen = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Rage Bait")


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

		self.rect = self.image.get_rect()
		self.rect.center = (x, y)

		self.vel_x = 0
		self.vel_y = 0
		self.speed = 5
		self.gravity = 2 #is based off of framerate
		self.isJumping = False

	def update(self):
		#apply gravity
#		self.vel_y += self.gravity

		self.rect.x += self.vel_x
		self.rect.y += self.vel_y

	def setDirection(self, direction):
		if direction == "left":
			self.vel_x = -self.speed
		elif direction == "right":
			self.vel_x = self.speed
		else:
			self.vel_x = 0


player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
all_sprites = pygame.sprite.Group(player)
#=========================================================


heartRate = 0
#Main Game Loop
clock = pygame.time.Clock()

player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
all_sprites = pygame.sprite.Group(player)

#========================================================


#NOTE: THIS WILL LATER BE PLACED INTO A FUNCTION WHEN MENUS ARE EVENTUALLY ADDDED
# PLAYER WILL ALSO GET ITS OWN CLASS IN THE FUTURE
def lvlOne():
	isRunning = True
	while isRunning:
		screen.fill(BLACK)
		delta_time = clock.tick(60) / 1000

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				isRunning = False

	#Keybinding
		keys = pygame.key.get_pressed()

		player.vel_x = 0

		if keys[pygame.K_LEFT]:
			player.vel_x -= player.speed
		if keys[pygame.K_RIGHT]:
			player.vel_x += player.speed

		all_sprites.update()
		all_sprites.draw(screen)

	#Platforms Arguments: for pygame.Rect(RGB Color), (x, y, width, height)
		GROUND_LEVEL
		pygame.draw.rect(screen, (0, 255, 0), (0, GROUND_LEVEL, SCREEN_WIDTH, 300))

		PLATFORM_1
		pygame.draw.rect(screen, (255, 0, 0), (1000, PLATFORM_1, 500, 50))


	#Rendering text
		heartRate_Text = FONT.render(f"HeartRate: {heartRate}", True, WHITE)

	#Display
		screen.blit(heartRate_Text, (10, 50))


		pygame.display.flip()

	pygame.quit()

def lvlTwo():
	isRunning = True
	while isRunning:
		screen.fill(BLACK)
		delta_time = clock.tick(60) / 1000

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				isRunning = False


def main_menu():
	menu = True
	while menu:
		screen.fill(BLACK)

		TITLE = FONT.render("Heart Beat Devil", True, WHITE)
		START_TEXT = FONT.render("Play", True, WHITE)
		LEVEL_TEXT = FONT.render("Level Select", True, WHITE)
		QUIT_TEXT = FONT.render("Quit", True, WHITE)

		TITLE_RECT = TITLE.get_rect(center=(SCREEN_WIDTH//2 - 90, 120))
		START_RECT = START_TEXT.get_rect(center=(SCREEN_WIDTH//2, 235))
		LEVEL_RECT = LEVEL_TEXT.get_rect(center=(SCREEN_WIDTH//2, 295))
		QUIT_RECT = QUIT_TEXT.get_rect(center=(SCREEN_WIDTH//2, 355))

		screen.blit(TITLE, TITLE_RECT)
		screen.blit(START_TEXT, START_RECT)
		screen.blit(LEVEL_TEXT, LEVEL_RECT)
		screen.blit(QUIT_TEXT, QUIT_RECT)

		mousePos = pygame.mouse.get_pos()
		mouseClick = pygame.mouse.get_pressed()

		if START_RECT.collidepoint(mousePos):
			if mouseClick[0]:
				lvlOne()
				menu = False
		if LEVEL_RECT.collidepoint(mousePos):
			if mouseClick[0]:
				lvlSelect()
				menu = False
		if QUIT_RECT.collidepoint(mousePos):
			if mouseClick[0]:
				pygame.quit()
				quit()
		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				menu = False
				pygame.quit()
		pygame.display.update()
		clock.tick(60)

if __name__ == "__main__":
	main_menu()
