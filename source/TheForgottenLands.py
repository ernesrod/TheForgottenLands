
import os
import gc
import math
import atexit
import bisect
import random
import itertools as it

import pymunk

import pyglet
from pyglet.gl import *
from pyglet.window import key

import cocos
from cocos.actions import *
from cocos.scenes.transitions import *


pyglet.resource.path.extend([
    "./data/fonts", 
    "./data/images/icons", 
    "./data/images/tilemap", 
    "./data/images/tiles",
    "./data/music",
    "./data/sounds"])
pyglet.resource.reindex()

pyglet.resource.add_font("Kenney Blocks.ttf")
pyglet.resource.add_font("Kenney Mini.ttf")


TITLE = "The Forgotten Lands"

ICONS = tuple(map(pyglet.resource.image, 
    (f"icon{x}x{x}.ico" for x in (16, 32, 48, 64, 128))))

SCALE = 5
TILEWIDTH, TILEHEIGHT = 16, 16
TILEXMARGIN, TILEYMARGIN = 1, 1

IMAGES = pyglet.image.ImageGrid(
    pyglet.resource.image("monochrome_tilemap_transparent.png"), 
    20, 20, TILEWIDTH, TILEHEIGHT, TILEXMARGIN, TILEYMARGIN)

DAMAGE_SOUND = pyglet.resource.media("damage.wav", False)
DAMAGE_SOUND.play().volume = 0

JUMP_SOUND = pyglet.resource.media("jump.wav", False)
JUMP_SOUND.play().volume = 0

PICKUP_SOUND = pyglet.resource.media("pickup.wav", False)
PICKUP_SOUND.play().volume = 0


MUSIC01 = pyglet.resource.media("01 Rolemusic - Spell.mp3")
MUSIC02 = pyglet.resource.media("02 Rolemusic - Leafless Quince Tree.mp3")
MUSIC03 = pyglet.resource.media("03 Rolemusic - Straw Fields.mp3")
MUSIC04 = pyglet.resource.media("04 Rolemusic - Yellow Dust.mp3")
MUSIC05 = pyglet.resource.media("05 Rolemusic - Poppies.mp3")


PLAYER_TYPE = 0
GROUND_TYPE = 1
DECORATION_TYPE = 2
REWARD_TYPE = 3
TRAP_TYPE = 4

STEP = 1 / 60


GRASS_STYLE = {
    "ground": [(11, 10)],
    "top_deco": [(19, 13), (18, 13), (19, 16), (19, 17), (19, 18)],
    "top_deco1": [(18, 14), (18, 15), (17, 15)],
    "top_deco2": [(19, 14), (19, 15)],
    "bottom_deco":[(18, 19)],
    "bottom_deco1":[(19, 19)],
    "bottom_deco2":[(18, 19)],
    "music": MUSIC02
}

SNOW_STYLE = {
    "ground": [(11, 15)],
    "top_deco": [(18, 16), (18, 17), (18, 18)],
    "top_deco1": [(18, 14), (18, 15)],
    "top_deco2": [(19, 0)],
    "bottom_deco":[(11, 6)],
    "bottom_deco1":[(19, 0)],
    "bottom_deco2":[(19, 0)],
    "music": MUSIC04
}

TECH_STYLE = {
    "ground": [(7, 10)],
    "top_deco": [(8, 3), (8, 4), (8, 5), (8, 6), (18, 18), (19, 18)],
    "top_deco1": [(9, 4), (9, 5), (9, 6)],
    "top_deco2": [(10, 4), (10, 5), (10, 6)],
    "bottom_deco":[(19, 6), (17, 3)],
    "bottom_deco1":[(19, 3)],
    "bottom_deco2":[(19, 6), (17, 3)],
    "music": MUSIC05
}

FUNGI_STYLE = {
    "ground": [(3, 10)],
    "top_deco": [(18, 13), (17, 13), (17, 14)],
    "top_deco1": [(18, 14), (18, 15), (17, 15)],
    "top_deco2": [(19, 14), (19, 15)],
    "bottom_deco":[(18, 19)],
    "bottom_deco1":[(19, 19)],
    "bottom_deco2":[(18, 19)],
    "music": MUSIC01
}

ROCK_STYLE = {
    "ground": [(3, 15), (7, 15)],
    "top_deco": [(19, 18), (18, 18)],
    "top_deco1": [(18, 14), (18, 15)],
    "top_deco2": [(19, 0)],
    "bottom_deco":[(11, 6)],
    "bottom_deco1":[(19, 19)],
    "bottom_deco2":[(18, 19)],
    "music": MUSIC03
}

STYLES = [
    GRASS_STYLE, 
    SNOW_STYLE, 
    TECH_STYLE,
    FUNGI_STYLE,
    ROCK_STYLE,
    ]

def sequence2animation(*args, **kwargs):
    return pyglet.image.Animation.from_image_sequence(*args, **kwargs)


HEARTS = (IMAGES[380], *map(sequence2animation, ((IMAGES[380], IMAGES[340]), 
    IMAGES[340: 342], IMAGES[341: 343]), (0.125, 0.25, 0.5)))


SCORESDIR = os.path.join(os.path.expandvars("$APPDATA"), TITLE)
if not os.path.exists(SCORESDIR):
    os.makedirs(SCORESDIR)

SCORESFILENAME = os.path.join(SCORESDIR, "hight_scores.txt")
HIGHTSCORES = []
HIGHTSCORES_NAMES = []
try:
    with open(SCORESFILENAME) as file:
        for line in file:
            name, score = line.split(": ")
            HIGHTSCORES.insert(0, int(score))
            HIGHTSCORES_NAMES.insert(0, name)

except:
    for i in range(1, 6):
        HIGHTSCORES.append(5 ** i)
        HIGHTSCORES_NAMES.append("Forgotten")

@atexit.register
def save_hight_scores():
    with open(SCORESFILENAME, "w") as file:
        for name, score in zip(reversed(HIGHTSCORES_NAMES), reversed(HIGHTSCORES)):
            file.write(f"{name}: {score}\n")


def _ScrollableLayer_on_exit_patch(self):
    try:
        super(cocos.layer.ScrollableLayer, self).on_exit()
    except AssertionError:
        pass

cocos.layer.ScrollableLayer.on_exit = _ScrollableLayer_on_exit_patch


class Mixer:
    def __init__(self):
        self.queue = []
        self.player = pyglet.media.Player()

    @property
    def source(self):
        return self.player.source

    @property
    def volume(self):
        return self.player.volume

    @volume.setter
    def volume(self, value):
        self.player.volume = value

    def _iter_queue(self):
        index = 0
        while self.queue:
            index %= len(self.queue)
            yield self.queue[index]
            index += 1

    def play(self, source=None):
        if source is not None:
            self.clear()
            self.add(source)
            self.next()
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.pause()
        self.clear()

    def next(self):
        self.player.next_source()

    def add(self, source):
        self.queue.append(source)
        if self.player.source is None:
            self.player.queue(self._iter_queue())

    def remove(self, source):
        self.queue.remove(source)

    def clear(self):
        self.queue.clear()

MIXER = Mixer()
MIXER.volume = 0.5

class MainMenu(cocos.menu.Menu):
    def __init__(self):
        super().__init__(title=TITLE)
        self.font_title["font_name"] = "Kenney Blocks"
        self.font_title["font_size"] = 72

        self.font_item["font_name"] = "Kenney Mini"
        self.font_item_selected["font_name"] = "Kenney Mini"

        self.menu_valign = cocos.menu.CENTER
        self.menu_halign = cocos.menu.CENTER

        items = []
        items.append(cocos.menu.MenuItem("New Game", self.on_new_game))
        items.append(cocos.menu.MenuItem("Options", self.on_options))
        items.append(cocos.menu.MenuItem("Scores", self.on_scores))
        items.append(cocos.menu.MenuItem("Quit", self.on_quit))
        self.create_menu(items, cocos.menu.zoom_in(), cocos.menu.zoom_out())

    def on_new_game(self):
        cocos.director.director.push(FadeTransition(GameScene()))

    def on_options(self):
        self.parent.switch_to(1)

    def on_scores(self):
        self.parent.switch_to(2)

    def on_quit(self):
        cocos.director.director.pop()


class OptionMenu(cocos.menu.Menu):
    def __init__(self):
        super().__init__(title=TITLE)
        self.font_title["font_name"] = "Kenney Blocks"
        self.font_title["font_size"] = 72

        self.font_item["font_name"] = "Kenney Mini"
        self.font_item_selected["font_name"] = "Kenney Mini"

        self.menu_valign = cocos.menu.CENTER
        self.menu_halign = cocos.menu.CENTER

        items = []
        items.append(cocos.menu.ToggleMenuItem("Fullscreen: ", self.on_fullscreen, True))
        items.append(cocos.menu.ToggleMenuItem("Show FPS: ", self.on_show_fps, False))
        items.append(cocos.menu.MenuItem("Ok", self.on_quit))
        self.create_menu(items, cocos.menu.zoom_in(), cocos.menu.zoom_out())

    def on_fullscreen(self, value):
        cocos.director.director.window.set_fullscreen(value)

    def on_quit(self):
        self.parent.switch_to(0)

    def on_show_fps(self, value):
        cocos.director.director.show_FPS = value


class ScoreMenu(cocos.menu.Menu):
    def __init__(self):
        super().__init__(title=TITLE)
        self.font_title["font_name"] = "Kenney Blocks"
        self.font_title["font_size"] = 72

        self.font_item["font_name"] = "Kenney Mini"
        self.font_item_selected["font_name"] = "Kenney Mini"

        self.menu_valign = cocos.menu.CENTER
        self.menu_halign = cocos.menu.CENTER

        items = []
        for name, score in zip(HIGHTSCORES_NAMES, HIGHTSCORES):
            items.insert(0, cocos.menu.MenuItem(f"{name}: {score}", lambda: None))

        items.append(cocos.menu.MenuItem("Go Back", self.on_quit))
        self.create_menu(items, cocos.menu.zoom_in(), cocos.menu.zoom_out())

    def on_quit(self):
        self.parent.switch_to(0)


class NewHightScoreMenu(cocos.menu.Menu):
    def __init__(self, name, score):
        super().__init__(title="New Hight Score: %s" % score)

        self.font_title["font_name"] = "Kenney Mini"
        self.font_title["font_size"] = 72

        self.font_item["font_name"] = "Kenney Mini"
        self.font_item_selected["font_name"] = "Kenney Mini"

        self.menu_valign = cocos.menu.CENTER
        self.menu_halign = cocos.menu.CENTER

        items = []
        items.append(cocos.menu.EntryMenuItem("Name: ", self.on_write, name, 10))
        items.append(cocos.menu.MenuItem("Ok", self.on_quit))
        self.create_menu(items, cocos.menu.zoom_in(), cocos.menu.zoom_out())

        self.score = score
        self.name = name

    def on_write(self, text):
        self.name = text

    def on_quit(self):
        global HIGHTSCORES, HIGHTSCORES_NAMES
        index = bisect.bisect(HIGHTSCORES, self.score)
        HIGHTSCORES.insert(index, self.score)
        HIGHTSCORES = HIGHTSCORES[-5:]
        HIGHTSCORES_NAMES.insert(index, self.name)
        HIGHTSCORES_NAMES = HIGHTSCORES_NAMES[-5:]
        cocos.director.director.replace(FadeTransition(GameScene()))


class NewHightScoreScene(cocos.scene.Scene):
    def on_enter(self):
        super().on_enter()
        MIXER.play(MUSIC01)


class MenuScene(cocos.scene.Scene):
    def on_enter(self):
        super().on_enter()
        self.menulayer = cocos.layer.MultiplexLayer(MainMenu(), OptionMenu(), ScoreMenu())
        self.add(self.menulayer)
        MIXER.play(MUSIC01)

    def on_exit(self):
        self.remove(self.menulayer)
        del self.menulayer
        super().on_exit()


class Entity(pymunk.Body):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self._sprites = cocos.layer.ScrollableLayer()
        self._sprites = set()

    @property
    def sprites(self):
        return self._sprites


class Player(Entity):
    def __init__(self, idle_right, walk_right, jump_right, dead_right, **kwargs):
        super().__init__(1, math.inf)
        self.sprite = cocos.sprite.Sprite(idle_right, **kwargs)
        self.idle_left = idle_right.get_transform(flip_x=True)
        self.idle_right = idle_right
        self.walk_left = walk_right.get_transform(flip_x=True)
        self.walk_right = walk_right
        self.jump_left = jump_right.get_transform(flip_x=True)
        self.jump_right = jump_right
        self.dead_left = dead_right.get_transform(flip_x=True)
        self.dead_right = dead_right
        self.sprites.add(self.sprite)

        w, h = self.sprite.get_AABB().size
        x, y = w / 3, h / 3
        self.shape = pymunk.Poly(self, 
            [(0, y), (x, 0), (w - x, 0), (w, y), 
            (w, h - y), (w - x, h), (x, h), (0, h - y)], 
            transform=pymunk.Transform(tx=-w / 2, ty=-h / 2))
        self.shape.collision_type = PLAYER_TYPE
        self.shape.friction = 0.50

        self.key_left_pressed = False
        self.key_right_pressed = False

        self.face2right = True
        self.on_ground = False
        self.hearts = 3

    def damage(self, amount):
        if amount > 0 and self.hearts > 0:
            DAMAGE_SOUND.play()
            self.hearts -= int(amount)
            if self.hearts <= 0:
                self.hearts = 0

    def change_image(self, image):
        if self.sprite.image is not image:
            self.sprite.image = image

    def update(self, dt):
        x, y = self.position
        scroller.set_focus(x, y)
        self.sprite.position = x, y

        vx, vy = self.velocity
        if self.hearts > 0 and abs(vx) < 500:
            force = pymunk.Vec2d.zero()
            fx = 500 if self.on_ground else 150
            if self.key_left_pressed:
                force -= pymunk.Vec2d(fx, 0)
            if self.key_right_pressed:
                force += pymunk.Vec2d(fx, 0)
            self.apply_force_at_local_point(force)

        if not self.on_ground:
            self.change_image(self.jump_right if self.face2right else self.jump_left)
        elif self.hearts <= 0:
            self.change_image(self.dead_right if self.face2right else self.dead_left)
        elif math.isclose(vx, 0, abs_tol=10):
            self.change_image(self.idle_right if self.face2right else self.idle_left)
        else:
            self.change_image(self.walk_right if self.face2right else self.walk_left)

    def on_key_press(self, symbol, modifiers):
        if self.hearts > 0:
            if symbol in (key.LEFT, key.A):
                self.key_left_pressed = True
                self.face2right = False
            elif symbol in (key.RIGHT, key.D):
                self.key_right_pressed = True
                self.face2right = True
            elif symbol in (key.UP, key.W, key.SPACE) and self.on_ground:
                self.apply_impulse_at_local_point(pymunk.Vec2d(0, 725))
                JUMP_SOUND.play()

    def on_key_release(self, symbol, modifiers):
        if symbol in (key.LEFT, key.A):
            self.key_left_pressed = False
        elif symbol in (key.RIGHT, key.D):
            self.key_right_pressed = False
        elif symbol in (key.UP, key.W, key.SPACE):
            vx, vy = self.velocity
            self.velocity = pymunk.Vec2d(vx, min(vy, 200))

    def on_collide_with_ground(self, arbiter, space, data):
        angle = arbiter.normal.angle_degrees
        if math.isclose(angle, 90):
            self.on_ground = True

        if arbiter.is_first_contact:
            fall_damage = arbiter.total_ke // 1e6
            self.damage(fall_damage)

    def on_separate_from_ground(self, arbiter, space, data):
        self.on_ground = False


def create_tile(row, column, image, **kwargs):
    sprite = cocos.sprite.Sprite(image, **kwargs)
    rect = sprite.get_AABB()
    rect.position = column * sprite.width, row * sprite.height
    sprite.position = rect.center 
    return sprite


class Ground(Entity):
    def __init__(self, bb, shape_bb, style, **kwargs):
        super().__init__(body_type=pymunk.Body.STATIC)
        self.shape = pymunk.Poly.create_box_bb(self, shape_bb)
        self.shape.collision_type = GROUND_TYPE
        self.shape.friction = 0.5

        left, bottom, right, top = map(round, bb)
        width, height = right - left, top - bottom
        y, x = random.choice(style["ground"])
        if width > 1:
            if height > 1:
                self.sprites.add(create_tile(top - 1, left, IMAGES[(y + 3, x + 0)], **kwargs))
                self.sprites.add(create_tile(bottom, left, IMAGES[(y + 1, x)], **kwargs))
                self.sprites.add(create_tile(bottom, right - 1, IMAGES[(y + 1, x + 2)], **kwargs))
                self.sprites.add(create_tile(top - 1, right - 1, IMAGES[(y + 3, x + 2)], **kwargs))
                for column in range(left + 1, right -1):
                    self.sprites.add(create_tile(top - 1, column, IMAGES[(y + 3, x + 1)], **kwargs))
                    self.sprites.add(create_tile(bottom, column, IMAGES[(y + 1, x + 1)], **kwargs))
                for row in range(bottom + 1, top - 1):
                    self.sprites.add(create_tile(row, left, IMAGES[(y + 2, x + 0)], **kwargs))
                    self.sprites.add(create_tile(row, right - 1, IMAGES[(y + 2, x + 2)], **kwargs))
                for row, column in it.product(range(bottom + 1, top - 1), range(left + 1, right -1)):
                    image = IMAGES[random.choice([(y + 2, x + 1), 
                        (y + 0, x + 4), (y + 1, x + 4), (y + 2, x + 4), (y + 3, x + 4)])]
                    self.sprites.add(create_tile(row, column, image, **kwargs))
            else:
                self.sprites.add(create_tile(bottom , left, IMAGES[(y + 0, x + 0)], **kwargs))
                self.sprites.add(create_tile(bottom, right - 1, IMAGES[(y + 0, x + 2)], **kwargs))
                for column in range(left + 1, right - 1):
                    self.sprites.add(create_tile(bottom, column, IMAGES[(y + 0, x + 1)], **kwargs))
        elif height > 1:
            self.sprites.add(create_tile(bottom, left, IMAGES[(y + 1, x + 3)], **kwargs))
            self.sprites.add(create_tile(top - 1, left, IMAGES[(y + 3, x + 3)], **kwargs))
            for row in range(bottom + 1, top - 1):
                self.sprites.add(create_tile(row, left, IMAGES[(y + 2, x + 3)], **kwargs))
        else:
            self.sprites.add(create_tile(bottom, left, IMAGES[(y + 0, x + 3)], **kwargs))


class Decoration(Entity):
    def __init__(self, bb, shape_bb, style,**kwargs):
        super().__init__(body_type=pymunk.Body.STATIC)
        self.shape = pymunk.Poly.create_box_bb(self, shape_bb)
        self.shape.collision_type = DECORATION_TYPE
        self.shape.sensor = True


class DecorationTop(Decoration):
    def __init__(self, bb, shape_bb, style, **kwargs):
        super().__init__(bb, shape_bb, style, **kwargs)
        left, bottom, right, top = map(round, bb)
        width, height = right - left, top - bottom
        if height == 1:
            image = IMAGES[random.choice(style["top_deco"])]
            self.sprites.add(create_tile(bottom, left, image, **kwargs))
        elif height == 2:
            if random.uniform(0, 1) < 0.3:
                bottom_image = IMAGES[random.choice(style["top_deco1"])]
                top_image = IMAGES[random.choice(style["top_deco2"])]
                self.sprites.add(create_tile(bottom, left, bottom_image, **kwargs))
                self.sprites.add(create_tile(bottom + 1, left, top_image, **kwargs))
            else:
                image = IMAGES[random.choice(style["top_deco"])]
                self.sprites.add(create_tile(bottom, left, image, **kwargs))


class DecorationBottom(Decoration):
    def __init__(self, bb, shape_bb, style, **kwargs):
        super().__init__(bb, shape_bb, style, **kwargs)
        left, bottom, right, top = map(round, bb)
        width, height = right - left, top - bottom
        if height == 1:
            image = IMAGES[random.choice(style["bottom_deco"])]
            self.sprites.add(create_tile(top - 1, left, image, **kwargs))
        elif height == 2:
            if random.uniform(0, 1) < 0.3:
                top_image = IMAGES[random.choice(style["bottom_deco1"])]
                bottom_image = IMAGES[random.choice(style["bottom_deco2"])]
                self.sprites.add(create_tile(top - 1, left, top_image, **kwargs))
                self.sprites.add(create_tile(top - 2, left, bottom_image, **kwargs))
            else:
                image = IMAGES[random.choice(style["bottom_deco"])]
                self.sprites.add(create_tile(top - 1, left, image, **kwargs))


class Reward(Entity):
    value = 1
    def __init__(self, bb, shape_bb, **kwargs):
        super().__init__(body_type=pymunk.Body.STATIC)
        shape_bb = pymunk.BB(*shape_bb)
        width = shape_bb.right - shape_bb.left
        self.shape = pymunk.Circle(self, width / 4, shape_bb.center())
        self.shape.collision_type = REWARD_TYPE
        self.shape.sensor = True


class Gem(Reward):
    def __init__(self, bb, shape_bb, **kwargs):
        super().__init__(bb, shape_bb, **kwargs)
        left, bottom, right, top = map(round, bb)
        self.sprites.add(create_tile(bottom, left, 
            IMAGES[14, 2], **kwargs))
        self.value = 1

class Diamond(Reward):
    def __init__(self, bb, shape_bb, **kwargs):
        super().__init__(bb, shape_bb, **kwargs)
        left, bottom, right, top = map(round, bb)
        self.sprites.add(create_tile(bottom, left, 
            sequence2animation((IMAGES[15, 2], IMAGES[16, 2]), 0.2), **kwargs))
        self.value = 5


class Trap(Entity):
    def __init__(self, bb, shape_bb, **kwargs):
        super().__init__(body_type=pymunk.Body.STATIC)
        left, bottom, right, top = shape_bb
        shape_bb = pymunk.BB(left, bottom, right, (bottom + top) / 2)
        self.shape = pymunk.Poly.create_box_bb(self, shape_bb, -15)
        self.shape.collision_type = TRAP_TYPE


class StaticTrap(Trap):
    def __init__(self, bb, shape_bb, **kwargs):
        super().__init__(bb, shape_bb, **kwargs)
        left, bottom, right, top = bb
        self.sprite = create_tile(bottom, left, IMAGES[13, 2], **kwargs)
        self.sprites.add(self.sprite)


class HiddenTrap(Trap):
    def __init__(self, bb, shape_bb, **kwargs):
        super().__init__(bb, shape_bb, **kwargs)
        left, bottom, right, top = bb
        self.sprite = create_tile(bottom, left, IMAGES[9, 3], **kwargs)
        self.sprites.add(self.sprite)


def bb2tiles(bb, width=16, height=16):
    starts, stops = zip(*[iter(bb)] * 2)
    left, bottom = map(lambda x: math.floor(x / width), starts)
    right, top = map(lambda y: math.ceil(y / height), stops)
    for column in range(left, right):
        for row in range(bottom, top):
            yield row, column

def tiles2chunks(tiles, rows, columns):
    for row, column in tiles:
        cq, cr = divmod(column, columns)
        rq, rr = divmod(row, rows)
        if rr == cr == 0:
            yield rq, cq

def bb2chunks(bb, rows=3, columns=3, width=16, height=16):
    yield from tiles2chunks(bb2tiles(bb, width, height), rows, columns)

def chunks2tiles(chunks, rows=3, columns=3):
    for row, column in chunks:
        yield from ((row * rows + r, column * columns + c) 
            for r in range(rows) for c in range(columns))

def tiles2bb(tiles, width=16, height=16):
    (bottom, *_, top), (left, *_, right) = map(sorted, zip(*tiles))
    return left * width, bottom * height, (right + 1) * width, (top + 1) * height

def chunks2bb(chunks, rows=3, columns=3, width=16, height=16):
    yield from tiles2bb(chunks2tiles(chunks, rows, columns), width, height)


def get_chunk_containing(row, column, rows=3, columns=3):
    for w, h in it.product(range(1, columns + 1), range(1, rows + 1)):
        for i, j in it.product(range(h), range(w)):
            yield frozenset(it.product(range(row - i, row + h - i), range(column - j, column + w - j)))


class WorldGenerator:
    def __init__(self, game_scene, chunk_rows=3, 
        chunk_columns=3, tile_width=16, tile_height=16):
        self.game_scene = game_scene
        self.chunk_rows = chunk_rows
        self.chunk_columns = chunk_columns
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.chunks = {}

    def update(self, bb):
        left, bottom, right, top = bb
        xpad = self.chunk_columns * self.tile_width
        ypad = self.chunk_rows * self.tile_height
        new_bb = left - xpad, bottom - ypad, right + xpad, top + ypad
        target = set(bb2chunks(new_bb, 
            self.chunk_rows, self.chunk_columns, 
            self.tile_width, self.tile_height))
        for chunk in tuple(self.chunks.keys()):
            if target.isdisjoint(chunk):
                self.delete_chunk(chunk)
                del self.chunks[chunk]
        missing = target.difference(*self.chunks.keys())
        while missing:
            row, column = missing.pop()
            options = [*get_chunk_containing(row, column, 3, 3)]
            random.shuffle(options)
            while True:
                chunk = options.pop()
                if all(map(chunk.isdisjoint, self.chunks.keys())):
                    missing.difference_update(chunk)
                    self.chunks[chunk] = []
                    self.create_chunk(chunk)
                    break

    def create_chunk(self, chunk):
        left, bottom, right, top = chunks2bb(chunk, 
            self.chunk_rows, self.chunk_columns, 1, 1)
        width, height = right - left, top - bottom

        new_left = random.randint(left + 1, min(left + 2, right - 2))
        new_right = random.randint(max(new_left, right - 1), right - 1)

        bottom_top = random.randint(bottom + 1, min(bottom + 3, top - 2))
        top_bottom = random.randint(max(bottom_top + 1, top - 2), top - 1)

        bottom_bb = (new_left, bottom, new_right, bottom_top)
        ground_bb = (new_left, bottom_top, new_right, top_bottom)
        top_bb = (new_left, top_bottom, new_right, top)

        self.populate_top(chunk, top_bb)
        self.create_ground(chunk, ground_bb)
        self.populate_bottom(chunk, bottom_bb)

    def delete_chunk(self, chunk):
        self.game_scene.remove_entities(*self.chunks[chunk])
        # bb = pymunk.BB(*chunks2bb(chunk, self.chunk_rows, self.chunk_columns, 
        #     self.tile_width, self.tile_height))
        # for shape in self.game_scene.space.bb_query(bb, pymunk.ShapeFilter()):
        #     self.game_scene.remove_entity(shape.body)

    def create_ground(self, chunk, bb):
        true_bb = (bb[0] * self.tile_width, bb[1] * self.tile_height, 
            bb[2] * self.tile_width, bb[3] * self.tile_height)
        entity = Ground(bb, true_bb, self.game_scene.style, scale=SCALE)
        self.game_scene.add_entity(entity)
        self.chunks[chunk].append(entity)

    def populate_top(self, chunk, bb):
        left, bottom, right, top = map(round, bb)
        for column in range(left, right):
            u = random.uniform(0, 1) 
            if u < 0.3:
                decoration_bb = (column, bottom, column + 1, top)
                true_bb = (decoration_bb[0] * self.tile_width, decoration_bb[1] * self.tile_height, 
                    decoration_bb[2] * self.tile_width, decoration_bb[3] * self.tile_height)
                entity = DecorationTop(decoration_bb, true_bb, self.game_scene.style, scale=SCALE)
                self.game_scene.add_entity(entity)
                self.chunks[chunk].append(entity)
            elif u < 0.7:
                reward_bb = (column, bottom, column + 1, bottom + 1)
                true_bb = (reward_bb[0] * self.tile_width, reward_bb[1] * self.tile_height, 
                    reward_bb[2] * self.tile_width, reward_bb[3] * self.tile_height)
                if u < 0.6:
                    entity = Gem(reward_bb, true_bb, scale=SCALE)
                else:
                    entity = Diamond(reward_bb, true_bb, scale=SCALE)
                self.game_scene.add_entity(entity)
                self.chunks[chunk].append(entity)
            elif u < 0.75:
                trap_bb = (column, bottom, column + 1, bottom + 1)
                true_bb = (trap_bb[0] * self.tile_width, trap_bb[1] * self.tile_height, 
                    trap_bb[2] * self.tile_width, trap_bb[3] * self.tile_height)
                if u < 0.735:
                    entity = StaticTrap(trap_bb, true_bb, scale=SCALE)
                else:
                    entity = HiddenTrap(trap_bb, true_bb, scale=SCALE)
                self.game_scene.add_entity(entity)
                self.chunks[chunk].append(entity)

    def populate_bottom(self, chunk, bb):
        left, bottom, right, top = map(round, bb)
        for column in range(left, right):
            if random.uniform(0, 1) < 0.2:
                decoration_bb = (column, bottom, column + 1, top)
                true_bb = (decoration_bb[0] * self.tile_width, decoration_bb[1] * self.tile_height, 
                    decoration_bb[2] * self.tile_width, decoration_bb[3] * self.tile_height)
                entity = DecorationBottom(decoration_bb, true_bb, self.game_scene.style, scale=SCALE)
                self.game_scene.add_entity(entity)
                self.chunks[chunk].append(entity)


class GameScene(cocos.scene.Scene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        global scroller
        scroller = cocos.layer.ScrollingManager()
        self.scrollable = cocos.layer.ScrollableLayer()
        scroller.add(self.scrollable)
        self.add(scroller)

        self.space = pymunk.Space()
        self.space.gravity = (0, -900)
        self.space.damping = 0.75
        row = random.randint(4, 7)
        self.player = Player(IMAGES[row, 1], 
            sequence2animation(IMAGES[20 * row + 1: 20 * row + 4], 0.15), 
            IMAGES[row, 4], IMAGES[row, 6], scale=SCALE)
        
        self.add_entity(self.player, z=1)

        ch = self.space.add_collision_handler(GROUND_TYPE, PLAYER_TYPE)
        ch.post_solve = self.player.on_collide_with_ground
        ch.separate = self.player.on_separate_from_ground

        ch = self.space.add_collision_handler(DECORATION_TYPE, PLAYER_TYPE)
        ch.begin = lambda a, s, d: False

        self.score = 0
        ch = self.space.add_collision_handler(REWARD_TYPE, PLAYER_TYPE)
        ch.begin = self.pick_up_reward

        ch = self.space.add_collision_handler(TRAP_TYPE, PLAYER_TYPE)
        ch.begin = self.trap_collision

        self.style = None
        self.change_style()
        self.world = WorldGenerator(self, 3, 3, 
            TILEWIDTH * SCALE, TILEHEIGHT * SCALE)
        self.world.update((0, 0, width, height))
        chunk = tuple(self.world.chunks)[0]
        left, bottom, right, top = chunks2bb(chunk, 3, 3, 
            TILEWIDTH * SCALE, TILEHEIGHT * SCALE)
        self.player.position = pymunk.Vec2d((left + right) // 2, top - 1.25 * TILEHEIGHT * SCALE)
        for shape in self.space.bb_query(self.player.shape.cache_bb(), pymunk.ShapeFilter()):
            if not isinstance(shape.body, (Ground, Decoration)):
                self.remove_entity(shape.body)

        self.ui = cocos.layer.Layer()
        self.heart = cocos.sprite.Sprite(HEARTS[3], 
            (TILEWIDTH * SCALE, height - TILEHEIGHT * SCALE), scale=SCALE)
        self.heart.hearts = 3
        self.ui.add(self.heart)

        self.score_label = cocos.text.Label(f"Score: {self.score}", 
            (width - TILEWIDTH * SCALE, height - TILEHEIGHT * SCALE), 
            font_name="Kenney Mini",
            font_size=32,
            anchor_x="right",
            align="right"
            )
        self.ui.add(self.score_label)
        self.add(self.ui)

        self.schedule(self.update)

    def on_enter(self):
        super().on_enter()
        cocos.director.director.window.push_handlers(self.player)
        music = self.style.get("music")
        if MIXER.source != music:
            MIXER.play(music)
        gc.disable()

    def on_exit(self):
        cocos.director.director.window.pop_handlers()
        self.unschedule(self.game_over)
        # self.unschedule(self.change_style)
        gc.enable()
        try:
            super().on_exit()
        except AssertionError:
            pass

    def add_entity(self, entity, z=0):
        # scroller.add(entity.sprites, z)
        for sprite in entity.sprites:
            self.scrollable.add(sprite, z)
        self.space.add(entity, *entity.shapes)

    def add_entities(self, *entities):
        for entity in entities:
            self.add_entity(entity)

    def remove_entity(self, entity):
        try:
            # scroller.remove(entity.sprites)
            for sprite in entity.sprites:
                self.scrollable.remove(sprite)
        except Exception as e:
            pass
        try:
            self.space.remove(entity, *entity.shapes)
        except Exception as e:
            pass

    def remove_entities(self, *entities):
        for entity in entities:
            self.remove_entity(entity)

    def update(self, dt):
        self.space.step(STEP)
        self.player.update(STEP)

        x = self.player.position.x - width // 2
        y = self.player.position.y - height // 2
        self.world.update((x, y, x + width, y + height))

        self.score_label.element.text = f"Score: {self.score}"

        if self.heart.hearts != self.player.hearts:
            index = self.heart.hearts = self.player.hearts
            self.heart.image = HEARTS[index]
            if index == 0:
                pyglet.clock.schedule_once(self.game_over, 3)

    def game_over(self, dt):
        if not HIGHTSCORES or self.score > min(HIGHTSCORES):
            cocos.director.director.replace(FadeTransition(
               NewHightScoreScene(NewHightScoreMenu("", self.score))))
        else:
            cocos.director.director.replace(FadeTransition(GameScene()))

    def change_style(self, dt=None):
        new_style = random.choice(STYLES)
        while new_style == self.style:
            new_style = random.choice(STYLES)
        self.style = new_style
        MIXER.play(new_style.get("music"))
        self.unschedule(self.change_style)
        self.schedule_interval(self.change_style, random.randint(30, 180))

    def on_quit(self):
        cocos.director.director.replace(FadeTransition(MenuScene()))

    def pick_up_reward(self, arbiter, space, data):
        reward = arbiter.shapes[0].body
        self.score += reward.value
        self.remove_entity(reward)
        PICKUP_SOUND.play()
        return False

    def trap_collision(self, arbiter, space, data):
        player = arbiter.shapes[1].body
        if player.hearts <= 0:
            return False
        if not arbiter.is_first_contact:
            return True
        trap = arbiter.shapes[0].body
        if isinstance(trap, HiddenTrap):
            trap.sprite.image = IMAGES[10, 3]
        player.damage(1)
        normal = arbiter.normal
        vx, vy = player.velocity
        player.velocity = pymunk.Vec2d(0, 0)
        force = pymunk.Vec2d(math.copysign(200, -vx), 400)
        player.apply_impulse_at_local_point(force)
        return True

def main():
    global width, height
    cocos.director.director.init(
        caption=TITLE,
        fullscreen=True
        )
    cocos.director.director.window.set_icon(*ICONS)
    width, height = cocos.director.director.window.get_size()
    cocos.director.director.run(MenuScene())

if __name__ == "__main__":
    main()