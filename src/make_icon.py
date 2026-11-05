# Draws the AutoClicker icon from scratch (pointing hand pressing a disc inside a ring) in brand orange on an ink tile,
# writes AutoClicker.ico + icon_preview.png. Built from circles, capsules and one polygon on a 260-unit grid;
# the proportions follow the reference screengrab, the geometry is our own.
import math, os
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ORANGE = (251, 75, 29, 255)
K = 12  # pixels per design unit: supersampled, then scaled down for clean edges
W, H = 260, 250
HERE = os.path.dirname(os.path.abspath(__file__))

def p(*xy): return tuple(int(round(v * K)) for v in xy)
def layer(): return Image.new("L", (W * K, H * K), 0)

def circle(im, x, y, r, fill=255):
    ImageDraw.Draw(im).ellipse(p(x - r, y - r, x + r, y + r), fill=fill)

def capsule(im, a, b, r, fill=255):  # a thick line with round ends
    ImageDraw.Draw(im).line(p(*a, *b), fill=fill, width=int(round(2 * r * K)))
    circle(im, *a, r, fill); circle(im, *b, r, fill)

def tangent(c1, r1, c2, r2, side):  # where a straight edge laid against two circles touches each of them
    base = math.atan2(c2[1] - c1[1], c2[0] - c1[0])
    a = base + side * math.acos((r1 - r2) / math.dist(c1, c2))
    return (c1[0] + r1 * math.cos(a), c1[1] + r1 * math.sin(a)), (c2[0] + r2 * math.cos(a), c2[1] + r2 * math.sin(a))

C, R_DISC, R_GAP, R_RING = (70, 70), 42, 50, 67  # ring centre; disc edge; inner and outer edge of the ring

# --- the hand ---
TIP = (72.5, 73.5)                       # centre of the index fingertip, just off the ring centre
A = math.radians(29)                     # the hand leans 29 degrees to the left
def at(across, along):  # a point in the hand's own frame: units across the fingers from the index axis, units back from its tip
    return (TIP[0] + across * math.cos(A) + along * math.sin(A), TIP[1] - across * math.sin(A) + along * math.cos(A))

R_INDEX, R_CORE, R_FINGER, CREASE = 13, 8.5, 10.75, 4.5
index = layer(); capsule(index, TIP, at(0, 112), R_INDEX)
core = layer(); capsule(core, TIP, at(0, 112), R_CORE)  # the finger as drawn on the disc: thinner, so an outline shows round it

PITCH = 2 * R_FINGER + CREASE
KNUCKLES = [at(R_INDEX + R_FINGER + i * PITCH, back) for i, back in enumerate((47, 55.5, 65))]  # three curled fingers, each set further back
PALM, THUMB = ((164, 169), 52), ((69.5, 167.5), 8.5)     # round heel of the palm; tip of the thumb
NOTCH = (110, 171)                                       # where the thumb meets the index finger
little, heel_r = tangent(KNUCKLES[2], R_FINGER, *PALM, -1)  # outer edge of the little finger
under, heel_l = tangent(*THUMB, *PALM, 1)                # underside of the thumb
rest = layer()                                           # palm, thumb and curled fingers
for x, y in KNUCKLES:
    circle(rest, x, y, R_FINGER)
circle(rest, *PALM[0], PALM[1]); circle(rest, *THUMB[0], THUMB[1])
ImageDraw.Draw(rest).polygon(p(*TIP, *NOTCH, 73, 159.5, *under, *heel_l, *PALM[0], *heel_r, *little,
                               *KNUCKLES[2], *KNUCKLES[1], *KNUCKLES[0]), fill=255)

hand = ImageChops.lighter(index, rest)
edge = R_INDEX - CREASE / 2                              # the first crease continues the outline round the index finger
for across, start, end in ((edge, 20, 72), (edge + PITCH, 40, 77), (edge + 2 * PITCH, 48, 83)):
    capsule(hand, at(across, start), at(across, end), CREASE / 2, fill=0)  # the creases between the fingers

# --- disc and ring ---
rings = layer()
circle(rings, *C, R_RING); circle(rings, *C, R_GAP, 0)
clear = rest.copy()
for x, y in KNUCKLES:
    circle(clear, x, y, R_FINGER + 5)
rings = ImageChops.subtract(rings, clear)                # the ring stops short of the curled fingers
circle(rings, *C, R_DISC)
near = layer(); circle(near, *C, R_GAP)                  # everything inside the ring's inner edge
far = ImageChops.invert(near)

mask = ImageChops.subtract(rings, ImageChops.multiply(index, near))         # the finger is cut out of the disc...
mask = ImageChops.lighter(mask, ImageChops.multiply(core, near))            # ...and drawn back thinner
hand = ImageChops.subtract(hand, ImageChops.subtract(ImageChops.multiply(index, near), core))  # nothing else may fill that outline
mask = ImageChops.lighter(mask, ImageChops.multiply(hand, far))             # outside the ring's inner edge the hand is solid
mask = ImageChops.lighter(mask, ImageChops.multiply(ImageChops.subtract(hand, index), near))
mask = mask.filter(ImageFilter.GaussianBlur(K * 0.6)).point(lambda v: 255 if v > 127 else 0)  # take the needle points off the corners

# crop to content, centre on a rounded ink tile: bare orange vanished against warm wallpapers and taskbars
art = Image.new("RGBA", mask.size, (0, 0, 0, 0))
art.paste(ORANGE, mask=mask)
art = art.crop(art.getbbox())
side = int(max(art.size) / 0.68)
icon = Image.new("RGBA", (side, side), (0, 0, 0, 0))
ImageDraw.Draw(icon).rounded_rectangle((0, 0, side - 1, side - 1), radius=int(side * 0.22), fill=(8, 9, 10, 255))
icon.paste(art, ((side - art.width) // 2, (side - art.height) // 2), art)
icon = icon.resize((1024, 1024), Image.LANCZOS)

icon.save(os.path.join(HERE, "icon_preview.png"))
icon.save(os.path.join(HERE, "AutoClicker.ico"), sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
assert os.path.getsize(os.path.join(HERE, "AutoClicker.ico")) > 1000
print("ok", icon.size)
