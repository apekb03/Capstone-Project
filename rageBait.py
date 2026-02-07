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
PLAYER_WIDTH, PLAYER_HEIGHT = 50, 50
PLAYER_COLOR = (25, 170, 76)
player_velocity_y = 0
PLAYER_SPEED = 2
PLAYER_X = SCREEN_WIDTH // 2 - PLAYER_WIDTH // 2
PLAYER_Y = SCREEN_HEIGHT //2 - PLAYER_HEIGHT // 2
GRAVITY = 3

#Objects and their variables
GROUND_LEVEL = 820

PLATFORM_1 = 620



#Heart Rate
heartRate = 0
#Main Game Loop
clock = pygame.time.Clock()
#NOTE: THIS WILL LATER BE PLACED INTO A FUNCTION WHEN MENUS ARE EVENTUALLY ADDDED
# PLAYER WILL ALSO GET ITS OWN CLASS IN THE FUTURE
isRunning = True
while isRunning:
	screen.fill(BLACK)
	delta_time = clock.tick(60) / 1000

	#Keybinding
	for event in pygame.event.get():
		if event.type == pygame.QUIT:
			isRunning = False
	if event.type == pygame.KEYDOWN:
		if event.key == pygame.K_RIGHT:
			PLAYER_X += PLAYER_SPEED
		if event.key == pygame.K_LEFT:
			PLAYER_X -= PLAYER_SPEED
		if event.key == pygame.K_UP:
			PLAYER_Y -= PLAYER_SPEED
		if event.key == pygame.K_DOWN:
			PLAYER_Y += PLAYER_SPEED

	#Setting boundaries for player
	PLAYER_X = max(0, min(PLAYER_X, SCREEN_WIDTH - PLAYER_WIDTH))
	PLAYER_Y = max(0, min(PLAYER_Y, SCREEN_HEIGHT - PLAYER_HEIGHT))

	pygame.draw.rect(screen, PLAYER_COLOR, (PLAYER_X, PLAYER_Y, PLAYER_WIDTH, PLAYER_HEIGHT))
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
