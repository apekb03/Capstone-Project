"""OpenGL / pygame 2D UI primitives (fonts, text, menu chrome)."""

import math
import os

import pygame
from OpenGL.GL import *

import config
import game_state as gs
from game_types import InputMode

SCREEN = None
FONT = pygame.font.Font(None, 36)
FONT_TITLE = pygame.font.Font(None, 72)
FONT_SUB = pygame.font.Font(None, 28)

# Optional system fonts (filled by init_menu_typography)
FONT_HERO = None
FONT_NAV = None
FONT_MICRO = None

UI_ACCENT = (160, 120, 255)
UI_ACCENT_DIM = (110, 85, 170)
UI_PANEL = (18, 18, 24)
UI_PANEL_BORDER = (72, 72, 92)
UI_BTN_BG = (32, 32, 44)
UI_BTN_HOVER = (48, 44, 70)
UI_BTN_BORDER = (95, 95, 115)
UI_MUTED_TEXT = (190, 185, 210)
UI_GLOW = (200, 160, 255)
UI_DEEP = (8, 6, 18)

# Fullscreen menu photo (optional); scaled cache keyed by (width, height)
_menu_bg_cache_key = None
_menu_bg_scaled = None


def menu_background_asset_path():
	return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "menu_background.png")


def menu_background_file_exists():
	return os.path.isfile(menu_background_asset_path())


def _get_menu_background_scaled(W, H):
	"""Return a pygame surface scaled to the screen, or None if missing / unloadable."""
	global _menu_bg_cache_key, _menu_bg_scaled
	path = menu_background_asset_path()
	if not os.path.isfile(path):
		return None
	key = (W, H)
	if _menu_bg_cache_key == key and _menu_bg_scaled is not None:
		return _menu_bg_scaled
	try:
		img = pygame.image.load(path).convert()
		_menu_bg_scaled = pygame.transform.smoothscale(img, (W, H))
		_menu_bg_cache_key = key
		return _menu_bg_scaled
	except Exception:
		_menu_bg_scaled = None
		_menu_bg_cache_key = None
		return None


def set_screen(surface):
	global SCREEN
	SCREEN = surface


def init_menu_typography():
	"""Prefer crisp system fonts for menus (safe fallbacks)."""
	global FONT_HERO, FONT_NAV, FONT_MICRO
	if FONT_HERO is not None:
		return
	try:
		fam = ["arial", "helvetica", "sans-serif"]
		FONT_HERO = pygame.font.SysFont(fam, 84, bold=True)
		FONT_NAV = pygame.font.SysFont(fam, 31)
		FONT_MICRO = pygame.font.SysFont(fam, 19)
		return
	except Exception:
		pass
	FONT_HERO = FONT_TITLE
	FONT_NAV = FONT
	FONT_MICRO = FONT_SUB


def begin_2d():
	glMatrixMode(GL_PROJECTION)
	glPushMatrix()
	glLoadIdentity()
	glOrtho(0, config.SCREEN_WIDTH, config.SCREEN_HEIGHT, 0, -1, 1)
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


def _gl_blit_text_surface(surface, x, y):
	text_data = pygame.image.tostring(surface, "RGBA", True)
	glRasterPos2f(x, y)
	glDrawPixels(surface.get_width(), surface.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)


def draw_text(text, x, y, font=None, color=None):
	f = font or FONT
	c = color if color is not None else config.WHITE
	surface = f.render(str(text), True, c)
	_gl_blit_text_surface(surface, x, y)


def draw_text_centered(text, cx, y, font=None, color=None):
	f = font or FONT
	c = color if color is not None else config.WHITE
	surface = f.render(str(text), True, c)
	_gl_blit_text_surface(surface, cx - surface.get_width() // 2, y)


def _draw_menu_backdrop_photo_overlays(W, H, t):
	"""Tint + vignette over blitted menu photo (readability for UI)."""
	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
	glColor4f(0.03, 0.04, 0.09, 0.56)
	glBegin(GL_QUADS)
	glVertex2f(0, 0)
	glVertex2f(W, 0)
	glVertex2f(W, H)
	glVertex2f(0, H)
	glEnd()
	pulse = 0.22 + 0.08 * math.sin(t * 1.2)
	glColor4f(UI_ACCENT[0] / 255.0 * pulse, UI_ACCENT[1] / 255.0 * pulse, UI_ACCENT[2] / 255.0 * pulse, 0.12)
	y_line = H * (0.72 + 0.02 * math.sin(t * 0.5))
	glBegin(GL_QUADS)
	glVertex2f(0, y_line - 2)
	glVertex2f(W, y_line - 2)
	glVertex2f(W, y_line + 2)
	glVertex2f(0, y_line + 2)
	glEnd()


def draw_menu_backdrop():
	"""Menu backdrop: optional fullscreen photo, else animated gradient + vignette (call inside begin_2d)."""
	init_menu_typography()
	t = pygame.time.get_ticks() / 1000.0
	W, H = config.SCREEN_WIDTH, config.SCREEN_HEIGHT

	bg = _get_menu_background_scaled(W, H)
	if SCREEN is not None and bg is not None:
		SCREEN.blit(bg, (0, 0))
		_draw_menu_backdrop_photo_overlays(W, H, t)
		return

	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

	# Vertical gradient bands
	steps = 8
	for i in range(steps):
		y0 = H * (i / steps)
		y1 = H * ((i + 1) / steps)
		u = i / (steps - 1) if steps > 1 else 0
		br = 0.04 + 0.06 * math.sin(t * 0.35 + u * 2.1)
		r = 0.05 + u * 0.12 + br * 0.08
		g = 0.04 + u * 0.08
		b = 0.12 + u * 0.22 + 0.04 * math.sin(t * 0.5 + u)
		glColor4f(r, g, b, 1.0)
		glBegin(GL_QUADS)
		glVertex2f(0, y0)
		glVertex2f(W, y0)
		glVertex2f(W, y1)
		glVertex2f(0, y1)
		glEnd()

	# Radial vignette (corners darker)
	glColor4f(0.0, 0.0, 0.0, 0.45)
	glBegin(GL_QUADS)
	glVertex2f(0, 0)
	glVertex2f(W, 0)
	glVertex2f(W, H)
	glVertex2f(0, H)
	glEnd()

	# Accent horizon line
	pulse = 0.35 + 0.15 * math.sin(t * 1.8)
	glColor4f(UI_ACCENT[0] / 255.0 * pulse, UI_ACCENT[1] / 255.0 * pulse, UI_ACCENT[2] / 255.0 * pulse, 0.22)
	y_line = H * (0.38 + 0.02 * math.sin(t * 0.9))
	glBegin(GL_QUADS)
	glVertex2f(0, y_line - 2)
	glVertex2f(W, y_line - 2)
	glVertex2f(W, y_line + 2)
	glVertex2f(0, y_line + 2)
	glEnd()

	# Subtle diagonal grid
	glColor4f(0.45, 0.42, 0.55, 0.04)
	glBegin(GL_LINES)
	step = 96
	off = int((t * 40) % step)
	for x in range(-step + off, W + step, step):
		glVertex2f(x, 0)
		glVertex2f(x + H * 0.35, H)
	for x in range(-step * 2, W + step * 2, step):
		glVertex2f(x, H)
		glVertex2f(x + H * 0.35, 0)
	glEnd()


def draw_labeled_input_box(rect, label, value, active, mask=False):
	"""Bordered input area with label above; no placeholder text (empty box is intentional)."""
	if SCREEN is None:
		return
	init_menu_typography()
	micro = FONT_MICRO or FONT_SUB
	f = FONT_NAV or FONT
	draw_text(label, rect.x, rect.y - 22, font=micro, color=UI_MUTED_TEXT)
	border_col = UI_ACCENT if active else (82, 88, 108)
	pygame.draw.rect(SCREEN, (10, 12, 20), rect, border_radius=10)
	pygame.draw.rect(SCREEN, border_col, rect, width=2, border_radius=10)
	inner = rect.inflate(-12, -12)
	pygame.draw.rect(SCREEN, (22, 26, 38), inner, border_radius=8)
	if value:
		text = ("*" * len(value)) if mask else value
		ty = inner.centery - f.get_height() // 2
		draw_text(text, inner.x + 10, ty, font=f, color=config.WHITE)


def draw_glass_panel(rect, title=None, subtitle=None):
	"""Frosted-style card with border glow."""
	if SCREEN is None:
		return
	shadow = rect.inflate(14, 14)
	shadow.center = rect.center
	shadow.y += 6
	pygame.draw.rect(SCREEN, (0, 0, 0), shadow, border_radius=28)
	pygame.draw.rect(SCREEN, UI_PANEL, rect, border_radius=24)
	pygame.draw.rect(SCREEN, UI_PANEL_BORDER, rect, width=2, border_radius=24)
	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
	glColor4f(UI_ACCENT[0] / 255.0, UI_ACCENT[1] / 255.0, UI_ACCENT[2] / 255.0, 0.12)
	glBegin(GL_QUADS)
	glVertex2f(rect.left, rect.top)
	glVertex2f(rect.right, rect.top)
	glVertex2f(rect.right, rect.top + 72)
	glVertex2f(rect.left, rect.top + 72)
	glEnd()
	if title:
		draw_text_centered(title, rect.centerx, rect.y + 26, font=FONT_HERO or FONT_TITLE, color=UI_ACCENT)
	if subtitle:
		draw_text_centered(subtitle, rect.centerx, rect.y + 96, font=FONT_MICRO or FONT_SUB, color=UI_MUTED_TEXT)


def draw_menu_chip(rect, title, subtitle=None, hovered=False, accent=False):
	"""Two-line navigation row with premium styling."""
	if SCREEN is None:
		return
	init_menu_typography()
	if accent:
		base = (42, 32, 72) if not hovered else (52, 40, 88)
		border = UI_ACCENT if hovered else (130, 100, 200)
	else:
		base = UI_BTN_HOVER if hovered else UI_BTN_BG
		border = UI_ACCENT if hovered else UI_BTN_BORDER
	pygame.draw.rect(SCREEN, base, rect, border_radius=16)
	pygame.draw.rect(SCREEN, border, rect, width=2, border_radius=16)
	nav = FONT_NAV or FONT
	micro = FONT_MICRO or FONT_SUB
	title_s = nav.render(title, True, config.WHITE)
	_gl_blit_text_surface(title_s, rect.centerx - title_s.get_width() // 2, rect.y + 12)
	if subtitle:
		sub = micro.render(subtitle, True, UI_MUTED_TEXT)
		_gl_blit_text_surface(sub, rect.centerx - sub.get_width() // 2, rect.y + 38)


def draw_menu_button(rect, label, hovered=False):
	"""Legacy single-line button (still used in a few places)."""
	draw_menu_chip(rect, label, None, hovered, accent=False)


def draw_cta_strip(text, y, width=520):
	"""Soft glowing bar behind call-to-action copy."""
	t = pygame.time.get_ticks() / 1000.0
	cx = config.SCREEN_WIDTH // 2
	w2 = width / 2
	p = 0.4 + 0.3 * math.sin(t * 2.4)
	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
	glColor4f(UI_ACCENT[0] / 255.0 * p, UI_ACCENT[1] / 255.0 * p, UI_ACCENT[2] / 255.0 * p, 0.28)
	glBegin(GL_QUADS)
	glVertex2f(cx - w2, y - 6)
	glVertex2f(cx + w2, y - 6)
	glVertex2f(cx + w2, y + 28)
	glVertex2f(cx - w2, y + 28)
	glEnd()
	draw_text_centered(text, cx, y, font=FONT_MICRO or FONT_SUB, color=(220, 218, 240))


def draw_title_particles():
	"""Lightweight drifting points."""
	t = pygame.time.get_ticks() / 1000.0
	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
	glPointSize(3.0)
	glBegin(GL_POINTS)
	W, H = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
	for i in range(48):
		seed = i * 9973
		x = (seed % W) + 40 * math.sin(t * 0.3 + i * 0.2)
		y = ((seed * 7) % H) + 30 * math.cos(t * 0.25 + i * 0.15)
		x = x % W
		y = y % H
		a = 0.15 + 0.12 * math.sin(t * 2.0 + i)
		glColor4f(0.7, 0.65, 0.95, a)
		glVertex2f(x, y)
	glEnd()


def draw_webcam_pip():
	"""Small mirrored webcam preview (emotion mode only). Call inside begin_2d / before end_2d."""
	if SCREEN is None or gs.input_mode != InputMode.EMOTION:
		return
	with gs.webcam_lock:
		buf = gs.webcam_rgb
		wh = gs.webcam_wh
	if not buf or wh[0] <= 0 or wh[1] <= 0:
		return
	try:
		raw = pygame.image.frombuffer(buf, wh, "RGB")
	except Exception:
		return
	surf = raw.copy()
	margin = 12
	pip_w, pip_h = wh[0], wh[1]
	x = config.SCREEN_WIDTH - pip_w - margin
	y = config.SCREEN_HEIGHT - pip_h - margin
	bg = pygame.Rect(x - 3, y - 22, pip_w + 6, pip_h + 25)
	pygame.draw.rect(SCREEN, UI_PANEL, bg, border_radius=10)
	pygame.draw.rect(SCREEN, UI_PANEL_BORDER, bg, width=2, border_radius=10)
	label = FONT_SUB.render("Camera", True, UI_MUTED_TEXT)
	SCREEN.blit(label, (x, y - 20))
	SCREEN.blit(surf, (x, y))
