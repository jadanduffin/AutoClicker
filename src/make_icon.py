# Draws the AutoClicker icon from scratch (pointing hand tapping two rings) in brand orange on an ink tile, writes AutoClicker.ico + icon_preview.png.
import math, os
from PIL import Image, ImageDraw, ImageFilter

ORANGE = (251, 75, 29, 255)
S = 2  # supersample for clean edges
TILT = 35  # degrees the hand leans left
HERE = os.path.dirname(os.path.abspath(__file__))

def px(v): return int(v * S)

def smooth(mask, r):  # blur + threshold: rounds every corner and fills the creases where shapes meet, so the hand reads as one soft form
    return mask.filter(ImageFilter.GaussianBlur(px(r))).point(lambda v: 255 if v > 127 else 0)

# --- hand, drawn upright on its own layer, then tilted ---
size = (px(1200), px(1200))
palm = Image.new("L", size, 0)
d = ImageDraw.Draw(palm)
d.rounded_rectangle((px(390), px(560), px(930), px(1040)), radius=px(235), fill=255)   # mitten-shaped palm, round at the wrist
for i in range(41):                                                                    # thumb: a short fat taper from the palm out to the left
    t = i / 40
    x, y, r = 480 - 255 * t, 790 - 105 * t, 128 - 58 * t
    d.ellipse((px(x - r), px(y - r), px(x + r), px(y + r)), fill=255)
d.rounded_rectangle((px(390), px(90), px(530), px(720)), radius=px(70), fill=255)      # index finger
# closing (grow, then shrink back): fills the sharp V between thumb and finger with a curve of webbing, leaves the outer shape alone
palm = palm.filter(ImageFilter.GaussianBlur(px(22))).point(lambda v: 255 if v > 40 else 0)
palm = palm.filter(ImageFilter.GaussianBlur(px(22))).point(lambda v: 255 if v > 215 else 0)
palm = smooth(palm, 10)

hand = palm.copy()
d = ImageDraw.Draw(hand)
d.rounded_rectangle((px(390), px(90), px(530), px(720)), radius=px(70), fill=255)      # the finger again, at its true width
FINGERS = ((544, 430, 664), (678, 475, 798), (812, 535, 922))                          # three curled fingers, each knuckle a step lower
for x0, top, x1 in FINGERS:
    d.rounded_rectangle((px(x0), px(top), px(x1), px(top + 300)), radius=px((x1 - x0) / 2), fill=255)
for x, top in ((537, 430), (671, 475), (805, 535)):                                    # the creases between the fingers
    d.line((px(x), px(top - 20), px(x), px(top + 140)), fill=0, width=px(14))
hand = hand.rotate(TILT, resample=Image.BICUBIC, expand=True)

# rings sit around the pad of the fingertip: the topmost hand pixel is the top of the finger's round cap
bbox = hand.getbbox()
col = hand.crop((0, bbox[1], hand.width, bbox[1] + 1)).getbbox()
tip = ((col[0] + col[2]) // 2, bbox[1] + px(70))

canvas = Image.new("RGBA", (px(1700), px(1700)), (0, 0, 0, 0))
cx, cy = px(420), px(420)
ox, oy = cx - tip[0], cy - tip[1]
rings = Image.new("L", canvas.size, 0)
r = ImageDraw.Draw(rings)
for rad, w in ((px(330), px(62)), (px(190), px(58))):
    r.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=255, width=w)

hand_full = Image.new("L", canvas.size, 0)
hand_full.paste(hand, (ox, oy))
halo = hand_full.filter(ImageFilter.GaussianBlur(px(30))).point(lambda v: 255 if v > 2 else 0)  # dilated hand = gap between finger and rings
rings = Image.composite(Image.new("L", canvas.size, 0), rings, halo)

mask = Image.new("L", canvas.size, 0)
mask.paste(255, mask=rings)
mask.paste(255, mask=hand_full)
canvas.paste(ORANGE, mask=mask)

# crop to content, centre on a rounded ink tile: bare orange vanished against warm wallpapers and taskbars
b = canvas.getbbox()
art = canvas.crop(b)
side = int(max(art.size) / 0.68)
icon = Image.new("RGBA", (side, side), (0, 0, 0, 0))
ImageDraw.Draw(icon).rounded_rectangle((0, 0, side - 1, side - 1), radius=int(side * 0.22), fill=(8, 9, 10, 255))
icon.paste(art, ((side - art.width) // 2, (side - art.height) // 2), art)
icon = icon.resize((1024, 1024), Image.LANCZOS)

icon.save(os.path.join(HERE, "icon_preview.png"))
icon.save(os.path.join(HERE, "AutoClicker.ico"), sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
assert os.path.getsize(os.path.join(HERE, "AutoClicker.ico")) > 1000
print("ok", icon.size)
