"""OpenGL / pygame 2D UI primitives (fonts, text, menu chrome)."""

import math
import os
import random

import pygame
from OpenGL.GL import *

import config
import game_state as gs
from game_types import InputMode

SCREEN = None

# Drawable pixel size (matches pygame window client area; may differ from config on HiDPI)
FRAME_W: int | None = None
FRAME_H: int | None = None


def sync_frame_dimensions():
	"""Refresh FRAME_W/H from the window and set glViewport to match (call after display mode exists)."""
	global FRAME_W, FRAME_H
	try:
		w, h = pygame.display.get_window_size()
	except Exception:
		w, h = (0, 0)
	if w <= 0 or h <= 0:
		w, h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
	FRAME_W, FRAME_H = int(w), int(h)
	glViewport(0, 0, FRAME_W, FRAME_H)
	return FRAME_W, FRAME_H


def frame_w() -> int:
	return FRAME_W if FRAME_W is not None else config.SCREEN_WIDTH


def frame_h() -> int:
	return FRAME_H if FRAME_H is not None else config.SCREEN_HEIGHT


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
	sync_frame_dimensions()
	glMatrixMode(GL_PROJECTION)
	glPushMatrix()
	glLoadIdentity()
	glOrtho(0, frame_w(), frame_h(), 0, -1, 1)
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
	sync_frame_dimensions()
	init_menu_typography()
	t = pygame.time.get_ticks() / 1000.0
	W, H = frame_w(), frame_h()

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
	cx = frame_w() // 2
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
	W, H = frame_w(), frame_h()
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
	x = frame_w() - pip_w - margin
	y = frame_h() - pip_h - margin
	bg = pygame.Rect(x - 3, y - 22, pip_w + 6, pip_h + 25)
	pygame.draw.rect(SCREEN, UI_PANEL, bg, border_radius=10)
	pygame.draw.rect(SCREEN, UI_PANEL_BORDER, bg, width=2, border_radius=10)
	label = FONT_SUB.render("Camera", True, UI_MUTED_TEXT)
	SCREEN.blit(label, (x, y - 20))
	SCREEN.blit(surf, (x, y))


# --- Red / navy menu theme (from uicopy.py): GL backdrop, glass buttons, surface text ---

RED_CLEAR_RGB = (0.03, 0.03, 0.05)
RED_PANEL = (8, 10, 18)
RED_C_RED = (220, 40, 40)
RED_C_RED_DIM = (120, 20, 20)
RED_C_RED_BRIGHT = (255, 80, 80)
RED_C_ACCENT = (255, 200, 60)
RED_C_TEXT = (210, 210, 220)
RED_C_TEXT_DIM = (100, 105, 120)
RED_C_WHITE = (255, 255, 255)

FONT_RED_TITLE = None
FONT_RED_HEADING = None
FONT_RED_MENU = None
FONT_RED_LABEL = None
FONT_RED_SMALL = None


def init_red_theme_fonts():
	global FONT_RED_TITLE, FONT_RED_HEADING, FONT_RED_MENU, FONT_RED_LABEL, FONT_RED_SMALL
	if FONT_RED_TITLE is not None:
		return
	# Slightly smaller hierarchy so the hero title and card headings don’t dwarf body/nav text.
	FONT_RED_TITLE = pygame.font.Font(None, 88)
	FONT_RED_HEADING = pygame.font.Font(None, 56)
	FONT_RED_MENU = pygame.font.Font(None, 44)
	FONT_RED_LABEL = pygame.font.Font(None, 30)
	FONT_RED_SMALL = pygame.font.Font(None, 22)


def _red_lerp(a, b, t):
	return a + (b - a) * t


def _red_lerp_color(c1, c2, t):
	return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


red_lerp_color = _red_lerp_color


def red_gl_rect(x, y, w, h, r, g, b, a=1.0):
	glColor4f(r, g, b, a)
	glBegin(GL_QUADS)
	glVertex2f(x, y)
	glVertex2f(x + w, y)
	glVertex2f(x + w, y + h)
	glVertex2f(x, y + h)
	glEnd()


def red_gl_border(x, y, w, h, r, g, b, a=1.0, lw=1.0):
	glColor4f(r, g, b, a)
	glLineWidth(lw)
	glBegin(GL_LINE_LOOP)
	glVertex2f(x, y)
	glVertex2f(x + w, y)
	glVertex2f(x + w, y + h)
	glVertex2f(x, y + h)
	glEnd()
	glLineWidth(1.0)


def draw_red_card_gl(rect, fill_alpha=0.4):
	"""Translucent bordered card (GL only)."""
	red_gl_rect(rect.left, rect.top, rect.width, rect.height, 0.06, 0.04, 0.07, fill_alpha)
	red_gl_border(rect.left, rect.top, rect.width, rect.height, 0.55, 0.12, 0.12, 0.55, 1.5)


def red_draw_text_surface(surface, x, y):
	"""Blit pygame text surface with correct GL orientation (y is top-left)."""
	flipped = pygame.transform.flip(surface, False, True)
	text_data = pygame.image.tostring(flipped, "RGBA", False)
	sh = surface.get_height()
	glRasterPos2f(x, y + sh)
	glDrawPixels(surface.get_width(), sh, GL_RGBA, GL_UNSIGNED_BYTE, text_data)


def red_blit_centered(font, text, color, cx, y, max_alpha=255):
	surf = font.render(text, True, color)
	if max_alpha < 255:
		surf.set_alpha(max_alpha)
	sw, sh = surf.get_size()
	red_draw_text_surface(surf, cx - sw // 2, y)


def red_blit_left(font, text, color, x, y):
	surf = font.render(text, True, color)
	red_draw_text_surface(surf, x, y)


def red_blit_right(font, text, color, right_x, y):
	surf = font.render(text, True, color)
	sw, sh = surf.get_size()
	red_draw_text_surface(surf, right_x - sw, y)


class MenuBackdropRed:
	"""Animated navy field + red grid + drifting particles (uicopy style)."""

	def __init__(self, n_particles=60):
		sync_frame_dimensions()
		W, H = frame_w(), frame_h()
		self._p = [self._new(W, H) for _ in range(n_particles)]
		self._time = 0.0

	def _new(self, W, H):
		return {
			"x": random.uniform(0, W),
			"y": random.uniform(0, H),
			"vy": random.uniform(8, 35),
			"alpha": random.uniform(0.04, 0.18),
			"size": random.uniform(1, 2.5),
		}

	def update(self, dt):
		W, H = frame_w(), frame_h()
		self._time += dt
		for p in self._p:
			p["y"] += p["vy"] * dt
			if p["y"] > H + 4:
				p["y"] = -4
				p["x"] = random.uniform(0, W)

	def draw(self):
		W, H = frame_w(), frame_h()
		glEnable(GL_BLEND)
		glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
		red_gl_rect(0, 0, W, H, *RED_CLEAR_RGB, 1.0)
		for i in range(10):
			t = i / 10
			mx, my = W * 0.5, H * 0.5
			rx = W * (0.05 + t * 0.5)
			ry = H * (0.05 + t * 0.5)
			alpha = (1 - t) * 0.35
			red_gl_rect(mx - rx, my - ry, rx * 2, ry * 2, 0.28, 0.0, 0.02, alpha)
		tm = self._time
		grid_alpha = 0.06
		glColor4f(0.6, 0.05, 0.05, grid_alpha)
		glLineWidth(1.0)
		step = 80
		for gx in range(0, W + step, step):
			glBegin(GL_LINES)
			glVertex2f(gx, 0)
			glVertex2f(gx, H)
			glEnd()
		for gy in range(0, H + step, step):
			glBegin(GL_LINES)
			glVertex2f(0, gy)
			glVertex2f(W, gy)
			glEnd()
		sweep_y = H * ((tm * 0.12) % 1.0)
		for i in range(3):
			a = 0.18 - i * 0.06
			glColor4f(0.8, 0.1, 0.1, a)
			glBegin(GL_LINES)
			glVertex2f(0, sweep_y + i * 2)
			glVertex2f(W, sweep_y + i * 2)
			glEnd()
		glPointSize(2.0)
		glBegin(GL_POINTS)
		for p in self._p:
			glColor4f(1.0, 0.2, 0.2, p["alpha"])
			glVertex2f(p["x"], p["y"])
		glEnd()
		glPointSize(1.0)


def draw_red_single_button(rect, label, hover_t, font=None):
	"""One-line glass button with red accent (uicopy _ui_button)."""
	init_red_theme_fonts()
	if font is None:
		font = FONT_RED_MENU
	x, y, w, h = rect.left, rect.top, rect.width, rect.height
	bg = _red_lerp_color(RED_PANEL, (25, 6, 6), hover_t)
	red_gl_rect(x, y, w, h, bg[0] / 255, bg[1] / 255, bg[2] / 255, 0.92)
	red_gl_rect(x + 2, y + 1, w - 4, 2, 1.0, 1.0, 1.0, 0.04 + hover_t * 0.08)
	bar_h = int(h * _red_lerp(0.35, 1.0, hover_t))
	bar_y = y + (h - bar_h) // 2
	bar_c = _red_lerp_color(RED_C_RED_DIM, RED_C_RED_BRIGHT, hover_t)
	red_gl_rect(x, bar_y, 3, bar_h, bar_c[0] / 255, bar_c[1] / 255, bar_c[2] / 255)
	bc = _red_lerp_color((45, 20, 20), (200, 50, 50), hover_t)
	red_gl_border(x, y, w, h, bc[0] / 255, bc[1] / 255, bc[2] / 255, 0.7 + hover_t * 0.3, 1.0 + hover_t)
	if hover_t > 0.01:
		red_gl_rect(x + 3, y + 1, w - 3, h - 2, 0.9, 0.15, 0.15, hover_t * 0.07)
	tc = _red_lerp_color((160, 155, 165), RED_C_WHITE, hover_t)
	lsurf = font.render(label, True, tc)
	lw, lh = lsurf.get_size()
	sc = 1.0 + hover_t * 0.03
	if sc > 1.005:
		lsurf = pygame.transform.smoothscale(lsurf, (int(lw * sc), int(lh * sc)))
		lw, lh = lsurf.get_size()
	red_draw_text_surface(lsurf, rect.centerx - lw // 2, rect.centery - lh // 2)


def draw_red_nav_button(rect, title, subtitle, hover_t, accent=False):
	"""Two-line menu row using red glass button chrome."""
	init_red_theme_fonts()
	x, y, w, h = rect.left, rect.top, rect.width, rect.height
	ht = min(1.0, hover_t + (0.12 if accent else 0))
	bg = _red_lerp_color(RED_PANEL, (28, 10, 10), ht)
	red_gl_rect(x, y, w, h, bg[0] / 255, bg[1] / 255, bg[2] / 255, 0.92)
	red_gl_rect(x + 2, y + 1, w - 4, 2, 1.0, 1.0, 1.0, 0.04 + ht * 0.08)
	bar_h = int(h * _red_lerp(0.35, 1.0, ht))
	bar_y = y + (h - bar_h) // 2
	bar_c = _red_lerp_color(RED_C_RED_DIM, RED_C_RED_BRIGHT, ht)
	if accent:
		bar_c = _red_lerp_color(bar_c, (255, 220, 120), 0.25)
	red_gl_rect(x, bar_y, 3, bar_h, bar_c[0] / 255, bar_c[1] / 255, bar_c[2] / 255)
	bc = _red_lerp_color((45, 20, 20), (200, 50, 50), ht)
	red_gl_border(x, y, w, h, bc[0] / 255, bc[1] / 255, bc[2] / 255, 0.7 + ht * 0.3, 1.0 + ht * 0.5)
	if ht > 0.01:
		red_gl_rect(x + 3, y + 1, w - 3, h - 2, 0.9, 0.15, 0.15, ht * 0.07)
	tc = _red_lerp_color((160, 155, 165), RED_C_WHITE, ht)
	# Fit text into the fixed button height by scaling font sizes with `h`.
	# This avoids the two lines looking too cramped on smaller menu rows.
	title_size = max(16, int(h * 0.46))
	subtitle_size = max(12, int(h * 0.33))
	title_font = pygame.font.Font(None, title_size)
	subtitle_font = pygame.font.Font(None, subtitle_size)

	ts = title_font.render(title, True, tc)
	tw, th = ts.get_size()

	if subtitle:
		sub_c = _red_lerp_color(RED_C_TEXT_DIM, RED_C_TEXT, ht * 0.5)
		st = subtitle_font.render(subtitle, True, sub_c)
		sw, sh = st.get_size()
		gap = 4
		total_h = th + gap + sh
	else:
		sw, sh = 0, 0
		st = None
		gap = 0
		total_h = th

	ty = int(rect.centery - total_h / 2)
	red_draw_text_surface(ts, rect.centerx - tw // 2, ty)
	if st is not None:
		red_draw_text_surface(st, rect.centerx - sw // 2, ty + th + gap)


def draw_red_main_title(cx, y_title=155):
	"""Pulsing HEART BEAT DEVIL title stack."""
	init_red_theme_fonts()
	ticks = pygame.time.get_ticks()
	pulse = (math.sin(ticks * 0.0018) + 1) * 0.5
	for off, sz, ga in [(6, 98, 30), (3, 92, 50)]:
		g = pygame.font.Font(None, sz).render("HEART BEAT DEVIL", True, RED_C_RED)
		g.set_alpha(int(ga + pulse * 22))
		gw, gh = g.get_size()
		red_draw_text_surface(g, cx - gw // 2, y_title - off)
	tc = _red_lerp_color((215, 30, 30), (255, 95, 95), pulse)
	red_blit_centered(FONT_RED_TITLE, "HEART BEAT DEVIL", tc, cx, y_title)


def draw_red_title_underline(cx, div_y=285):
	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
	glColor4f(0.65, 0.10, 0.10, 0.55)
	glLineWidth(1.0)
	glBegin(GL_LINES)
	glVertex2f(cx - 280, div_y)
	glVertex2f(cx + 280, div_y)
	glEnd()
	ds = 5
	glColor4f(0.9, 0.2, 0.2, 0.85)
	glBegin(GL_QUADS)
	glVertex2f(cx, div_y - ds)
	glVertex2f(cx + ds, div_y)
	glVertex2f(cx, div_y + ds)
	glVertex2f(cx - ds, div_y)
	glEnd()


def draw_red_glass_panel(rect, title=None, subtitle=None):
	"""Dark panel with red border (pygame); use inside begin_2d with SCREEN set."""
	if SCREEN is None:
		return
	init_red_theme_fonts()
	shadow = rect.inflate(14, 14)
	shadow.center = rect.center
	shadow.y += 6
	pygame.draw.rect(SCREEN, (0, 0, 0), shadow, border_radius=28)
	pygame.draw.rect(SCREEN, RED_PANEL, rect, border_radius=24)
	pygame.draw.rect(SCREEN, (120, 40, 40), rect, width=2, border_radius=24)
	glEnable(GL_BLEND)
	glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
	glColor4f(0.8, 0.15, 0.15, 0.12)
	glBegin(GL_QUADS)
	glVertex2f(rect.left, rect.top)
	glVertex2f(rect.right, rect.top)
	glVertex2f(rect.right, rect.top + 72)
	glVertex2f(rect.left, rect.top + 72)
	glEnd()
	if title:
		red_blit_centered(FONT_RED_HEADING, title, RED_C_RED_BRIGHT, rect.centerx, rect.y + 18)
	if subtitle:
		red_blit_centered(FONT_RED_SMALL, subtitle, RED_C_TEXT_DIM, rect.centerx, rect.y + 88)


def draw_red_labeled_input_box(rect, label, value, active, mask=False):
	if SCREEN is None:
		return
	init_red_theme_fonts()
	red_blit_left(FONT_RED_SMALL, label, RED_C_TEXT_DIM, rect.x, rect.y - 22)
	border_col = RED_C_RED_BRIGHT if active else (100, 55, 55)
	pygame.draw.rect(SCREEN, (12, 8, 10), rect, border_radius=10)
	pygame.draw.rect(SCREEN, border_col, rect, width=2, border_radius=10)
	inner = rect.inflate(-12, -12)
	pygame.draw.rect(SCREEN, (22, 14, 16), inner, border_radius=8)
	if value:
		text = ("*" * len(value)) if mask else value
		f = FONT_RED_MENU
		ty = inner.centery - f.get_height() // 2
		red_blit_left(f, text, RED_C_WHITE, inner.x + 10, ty)
