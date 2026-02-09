import pygame
import json

pygame.init()

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
WHITE = (255,255,255)
BLUE = (0,0,255)
BLACK = (0,0,0)
FONT = pygame.font.Font(None, 36)

screen = pygame.display.set_mode ((SCREEN_WIDTH,SCREEN_HEIGHT))
pygame.display.set_caption("Cat and mouse")

#Player settings
PLAYER_WIDTH = 80
PLAYER_HEIGHT = 120
PLAYER_SPEED = 2.5
GRAVITY = 15
GROUND_LEVEL = 500

#Enemy Settings
ENEMY_WIDTH = 80
ENEMY_HEIGHT = 100

#Scoring and lives
score = 0
score_timer = pygame.time.get_ticks()
lives = 3

#Game Clock
clock = pygame.time.Clock()
#Player and objects
player = pygame.image.load('pixil-frame-Rat.png')
enemy = pygame.image.load('pixil-frame-Enemy.png')
skybox = pygame.image.load('pixil-frame-Skybox.png')

#Secondary Functions
def collision(p1_x, p1_y, e1_x, e1_y):
        player_rect = pygame.Rect(p1_x + 20, p1_y + 20, PLAYER_WIDTH - 40, PLAYER_HEIGHT- 40)
        enemy_rect = pygame.Rect(e1_x + 20, e1_y + 20, ENEMY_WIDTH - 40, ENEMY_HEIGHT - 40)
        return player_rect.colliderect(enemy_rect)
#Allows for game saving when closing the game
def game_save(p1_x, p1_y, e1_x, e1_y, score, lives):
    game_save = {
        'player_x' : p1_x,
        'player_y' : p1_y,
        'enemy_x' : e1_x,
        'enemy_y' : e1_y,
        'Score' : score,
        'Lives' : lives
    }
    with open('gamesave.json', 'w') as file:
        json.dump(game_save, file)

def pause(p1_x, p1_y, e1_x, e1_y, score, lives):
    pauseText = pygame.font.SysFont(None, 48)
    
    paused = True
    while paused:
        screen.fill(BLACK)

        #TextSurf = pauseText.render("Paused", True, WHITE)
        #TextRect = TextSurf.get_rect(center = (400, 400))
        #TextRect.center = ((400), (400))
        #screen.blit(TextSurf, TextRect)
        PAUSE_TEXT = FONT.render("Paused", True, WHITE)

        QUIT_TEXT = FONT.render("Quit", True, WHITE)
        QUIT_SAVE_TEXT = FONT.render("Save and Quit", True, WHITE)
        screen.blit(QUIT_TEXT, (SCREEN_WIDTH//2 - 40, 380))
        screen.blit(QUIT_SAVE_TEXT, (SCREEN_WIDTH // 2 - 100, 320))
        screen.blit(PAUSE_TEXT, (SCREEN_WIDTH//2 - 55, 250))
        mousePos = pygame.mouse.get_pos()
        mouseClick = pygame.mouse.get_pressed()

        for event in pygame.event.get():

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    paused = False
            if event.type == pygame.QUIT:
                paused = False
                pygame.quit
                quit()
        if 320 <= mousePos[1] <= 350 and SCREEN_WIDTH // 2 - 100 <= mousePos[0] <= SCREEN_WIDTH // 2 + 100:
            if mouseClick[0]:
                game_save(p1_x, p1_y, e1_x, e1_y, score, lives)
                pygame.quit()
                quit()
        
        if 380 <= mousePos[1] <= 410 and SCREEN_WIDTH // 2 - 60 <= mousePos[0] <= SCREEN_WIDTH // 2 + 60:
            if mouseClick[0]:
                pygame.quit()
                quit()

        pygame.display.update()
        clock.tick(15)

#Game loop
def play(p1_x = None, p1_y = None, e1_x = None, e1_y = None, score = None, lives = None):
    collisionCooldown = 0
    ENEMY_DIRECTION = 1 #1 is for right -1 for left

    if p1_x is None: 
        p1_x = PLAYER_WIDTH/2
    if p1_y is None:
        p1_y = PLAYER_WIDTH/2
    if e1_x is None:
        e1_x = ENEMY_WIDTH/2
    if e1_y is None:
        e1_y = ENEMY_WIDTH/2
    if score is None:
        score = 0
    if lives is None:
        lives = 3
    
    p1_velocity_y = 0
    isJumping = False
    ENEMY_SPEED = 3
    score_timer = pygame.time.get_ticks()

    isRunning = True
    while isRunning:
        screen.blit(skybox, (0,0))
        delta_time = clock.tick(60) / 1000
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                isRunning = False
        
        #player & enemny gravity
        p1_velocity_y += GRAVITY * delta_time
        p1_y += p1_velocity_y
        e1_y += GRAVITY

        if p1_y + PLAYER_HEIGHT >= GROUND_LEVEL:
            p1_y = GROUND_LEVEL - PLAYER_HEIGHT
            p1_velocity_y = 0
            isJumping = False
    
        if e1_y + ENEMY_HEIGHT >- GROUND_LEVEL:
            e1_y = GROUND_LEVEL - ENEMY_HEIGHT

    #platforms
        GROUND_LEVEL #is declared at 500 in the begining
        pygame.draw.rect(screen, (0, 255, 0), (0, GROUND_LEVEL, SCREEN_WIDTH, 100))
        
    # Collsion checking
        if collision(p1_x, p1_y, e1_x, e1_y) and currentTime > collisionCooldown:
            lives -= 1
            ENEMY_SPEED = 3
            collisionCooldown = currentTime + 2000 # adds a two second cooldown
            if lives == 0:
                print("Game Over")
                isRunning = False
            else:
            #reset positions when making contact
                p1_x = 100
                p1_y = GROUND_LEVEL - PLAYER_HEIGHT
                e1_x = 800
                e1_y = GROUND_LEVEL - ENEMY_HEIGHT
    #Enemy movment
        e1_x += ENEMY_SPEED * ENEMY_DIRECTION
        if e1_x < 0:
            e1_x = 0
            ENEMY_DIRECTION = 1
            ENEMY_SPEED = min(ENEMY_SPEED + 1, 9)
        elif e1_x + ENEMY_WIDTH > 940:
            e1_x = 940 - ENEMY_WIDTH
            ENEMY_DIRECTION = -1
            ENEMY_SPEED = min(ENEMY_SPEED + 1, 9)

    #Key control
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] and p1_x > 0:
            p1_x -= PLAYER_SPEED
        if keys[pygame.K_RIGHT] and p1_x + PLAYER_WIDTH < SCREEN_WIDTH:
            p1_x += PLAYER_SPEED
        if keys[pygame.K_SPACE] and not isJumping:
            p1_velocity_y = -400 * delta_time
            isJumping = True
        if keys[pygame.K_ESCAPE]:
            pause(p1_x, p1_y, e1_x, e1_y, score, lives) 
        
        screen.blit(player, (p1_x, p1_y))
        screen.blit(enemy, (e1_x, e1_y))

    #Renders score and lives text
        score_text = FONT.render(f"Score: {score}", True, WHITE)
        lives_text = FONT.render(f"Lives: {lives}", True, WHITE)
    #Display in the left corner
        screen.blit(score_text, (10, 10))
        screen.blit(lives_text, (10, 50))

        pygame.display.flip() 
        currentTime = pygame.time.get_ticks()
        if currentTime - score_timer >= 1000:
            score += 1
            score_timer = currentTime


    pygame.quit()

def load():
    try:
        with open('gamesave.json', 'r') as file:
            data = json.load(file)
            p1_x = data.get('player_x', PLAYER_WIDTH/ 2)
            p1_y = data.get('player_y', PLAYER_HEIGHT/ 2)
            e1_x = data.get('enemy_x', ENEMY_WIDTH/ 2)
            e1_y = data.get('enemy_y', ENEMY_HEIGHT/ 2)
            score = data.get('Score', 0)
            lives = data.get('Lives', 3)
            play(p1_x, p1_y, e1_x, e1_y, score, lives)
    except FileNotFoundError:
        print("No save file found. Creating new game.")
        play()
def main_menu():
#In order to get this Menu to work I had asked AI 
#to help me impliment it mainly the mouse position
    menu = True
    
    while menu:
        screen.fill(BLACK)
        #Renders all the fonts
        TITLE = FONT.render("Cat And Mouse", True, WHITE)
        PLAY_TEXT = FONT.render("Play", True, WHITE)
        LOAD_TEXT = FONT.render("Load", True, WHITE)
        QUIT_TEXT = FONT.render("Quit", True, WHITE)

        #Handles the postioning on screen
        screen.blit(TITLE, (SCREEN_WIDTH//2 - 90, 120))
        screen.blit(PLAY_TEXT, (SCREEN_WIDTH//2 - 40, 220))
        screen.blit(LOAD_TEXT,(SCREEN_WIDTH//2 - 40, 280))
        screen.blit(QUIT_TEXT, (SCREEN_WIDTH//2 - 40, 340))

        mousePos = pygame.mouse.get_pos()
        mouseClick = pygame.mouse.get_pressed()

        if 220 <= mousePos[1] <= 240 and SCREEN_WIDTH//2 - 40 <= mousePos[0] <= SCREEN_WIDTH//2 + 40:
            if mouseClick[0]:
                play()
                menu = False
        if 280 <= mousePos[1] <= 300 and SCREEN_WIDTH//2 - 40 <= mousePos[0] <= SCREEN_WIDTH//2 + 40:
                if mouseClick[0]:
                    load()
        if 340 <= mousePos[1] <= 360 and SCREEN_WIDTH//2 - 40 <= mousePos[0] <= SCREEN_WIDTH//2 + 40:
                if mouseClick[0]:
                    pygame.quit()
                    quit()
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                menu = False
                pygame.quit
                quit()
        pygame.display.update()
        clock.tick(60)

if __name__ == "__main__":
    main_menu()
