#Created 2/2/2026 11:02PM
#Original Coder James Musick
#In this code you should find game code for RageBait, CS450 Capstone project Team Joy
import pygame
import json

pygame.init()

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = pygame.font.Font(None, 36)

screen = pygame.display.set_mode ((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Rage Bait")

#Player variables
PLAYER_WIDTH = 50
PLAYER_HEIGHT = 50
PLAYER_SPEED = 2
GRAVITY = 3
GROUND_LEVEL = 920

#Lives
lives = 3

#Game Clock
clock = pygame.time.Clock()

#Player and objects

#Main Game Loop
def play(p1_x = None, p1_y = None, lives = None):

	if p1_x is None:
		p1_x = PLAYER_WIDTH/2
	if p1_y is None:
		p1_y = PLAYER_WIDTH/2
	if lives is None:
		lives = 3

	isRunning = True
	while isRunning:
		screen.fill(BLACK)
		delta_time = clock.tick(60) / 1000

		for event in pygame.event.get():
			if event.type == pygame.QUIT:
				isRunning = False

	#Platforms
		GROUND_LEVEL
		pygame.draw.rect(screen, (0, 255, 0), (0, GROUND_LEVEL, SCREEN_WIDTH, 100))

	#Rendering text
		lives_text = FONT.render(f"Lives: {lives}", True, WHITE)

	#Display
		screen.blit(lives_text, (10, 50))


		pygame.display.flip()

	pygame.quit()
play()
