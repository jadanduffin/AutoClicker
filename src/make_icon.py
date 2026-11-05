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

C, R_DISC, R_RING = (70, 70), 42, 67     # ring centre; disc edge; outer edge of the ring
LINE = 8                                 # the one line weight: the gap between disc and ring, the outline round the hand, the creases

# --- the hand ---
TIP = (72.5, 73.5)                       # centre of the index fingertip, just off the ring centre
A = math.radians(29)                     # the hand leans 29 degrees to the left
def at(across, along):  # a point in the hand's own frame: units across the fingers from the index axis, units back from its tip
    return (TIP[0] + across * math.cos(A) + along * math.sin(A), TIP[1] - across * math.sin(A) + along * math.cos(A))

R_INDEX, R_FINGER = 11, 9
PITCH = 2 * R_FINGER + LINE
FINGERS = [(R_INDEX + LINE + R_FINGER + i * PITCH, back) for i, back in enumerate((47, 55.5, 65))]  # three curled fingers, each set further back
KNUCKLES = [at(*f) for f in FINGERS]
PALM, THUMB = ((164, 169), 52), ((69.5, 167.5), 8.5)     # round heel of the palm; tip of the thumb
NOTCH = (110, 171)                                       # where the thumb meets the index finger
little, heel_r = tangent(KNUCKLES[2], R_FINGER, *PALM, -1)  # outer edge of the little finger
under, heel_l = tangent(*THUMB, *PALM, 1)                # underside of the thumb

def draw_hand(extra):  # the hand, with every finger grown by `extra` units: 0 for the hand itself, LINE for the outline round it
    im = layer()
    capsule(im, TIP, at(0, 112), R_INDEX + extra)
    for i, (across, back) in enumerate(FINGERS):  # the little finger is only its tip: its outer edge is the polygon's, running into the heel
        capsule(im, at(across, back), at(across, back + (25 if i < 2 else 0)), R_FINGER + extra)
    circle(im, *PALM[0], PALM[1]); circle(im, *THUMB[0], THUMB[1])
    # the body: from the index axis round the thumb and heel, up the little finger, then back across below the fingertips
    ImageDraw.Draw(im).polygon(p(*at(0, 60), *NOTCH, 73, 159.5, *under, *heel_l, *PALM[0], *heel_r, *little, *KNUCKLES[2],
                                 *at(FINGERS[1][0], FINGERS[1][1] + 15), *at(FINGERS[0][0], FINGERS[0][1] + 15)), fill=255)
    return im

hand = draw_hand(0)
gap = R_INDEX + LINE / 2                                 # creases sit in the gaps between the fingers, the same weight as the outline
for across, start, end in ((gap, 15, 72), (gap + PITCH, 40, 77), (gap + 2 * PITCH, 48, 83)):
    capsule(hand, at(across, start), at(across, end), LINE / 2, fill=0)

# --- disc and ring, cut back from the hand by one line all the way round it ---
rings = layer()
circle(rings, *C, R_RING); circle(rings, *C, R_DISC + LINE, 0); circle(rings, *C, R_DISC)
mask = ImageChops.lighter(ImageChops.subtract(rings, draw_hand(LINE)), hand)
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
