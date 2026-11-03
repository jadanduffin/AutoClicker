# Draws the AutoClicker icon from scratch (pointing hand tapping two rings) in brand orange, writes AutoClicker.ico + icon_preview.png.
import os
from PIL import Image, ImageDraw, ImageFilter

ORANGE = (251, 75, 29, 255)
S = 2  # supersample for clean edges
HERE = os.path.dirname(os.path.abspath(__file__))

def px(v): return int(v * S)

# --- hand, drawn upright on its own layer, then tilted ---
hand = Image.new("L", (px(1100), px(1100)), 0)
d = ImageDraw.Draw(hand)
d.rounded_rectangle((px(360), px(100), px(510), px(640)), radius=px(75), fill=255)   # index finger
d.rounded_rectangle((px(360), px(480), px(870), px(860)), radius=px(90), fill=255)   # palm
for x, y in ((520, 410), (650, 450), (770, 500)):                                    # three curled fingers
    d.rounded_rectangle((px(x), px(y), px(x + 125), px(y + 220)), radius=px(60), fill=255)
d.rounded_rectangle((px(190), px(600), px(420), px(830)), radius=px(95), fill=255)   # thumb
d.rounded_rectangle((px(440), px(890), px(800), px(990)), radius=px(35), fill=255)   # cuff
hand = hand.rotate(22, resample=Image.BICUBIC, expand=True)

# fingertip = topmost hand pixel; rings sit around it
bbox = hand.getbbox()
col = hand.crop((0, bbox[1], hand.width, bbox[1] + 1)).getbbox()
tip = ((col[0] + col[2]) // 2, bbox[1])

canvas = Image.new("RGBA", (px(1400), px(1400)), (0, 0, 0, 0))
ox, oy = px(330) - tip[0], px(330) - tip[1]  # place fingertip at (330, 330)
rings = Image.new("L", canvas.size, 0)
r = ImageDraw.Draw(rings)
cx, cy = px(330), px(330)
for rad, w in ((px(300), px(60)), (px(170), px(60))):
    r.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), outline=255, width=w)

hand_full = Image.new("L", canvas.size, 0)
hand_full.paste(hand, (ox, oy))
halo = hand_full.filter(ImageFilter.GaussianBlur(px(30))).point(lambda v: 255 if v > 2 else 0)  # dilated hand = gap between finger and rings
rings = Image.composite(Image.new("L", canvas.size, 0), rings, halo)

mask = Image.new("L", canvas.size, 0)
mask.paste(255, mask=rings)
mask.paste(255, mask=hand_full)
canvas.paste(ORANGE, mask=mask)

# crop to content, pad to square with a little margin
b = canvas.getbbox()
art = canvas.crop(b)
side = max(art.size) + px(80)
icon = Image.new("RGBA", (side, side), (0, 0, 0, 0))
icon.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
icon = icon.resize((1024, 1024), Image.LANCZOS)

icon.save(os.path.join(HERE, "icon_preview.png"))
icon.save(os.path.join(HERE, "AutoClicker.ico"), sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
assert os.path.getsize(os.path.join(HERE, "AutoClicker.ico")) > 1000
print("ok", icon.size)
