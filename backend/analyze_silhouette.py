import os
from PIL import Image

desktop = 'C:/Users/Ярослав/Desktop'
portfolio_dir = None
for item in os.listdir(desktop):
    full = os.path.join(desktop, item)
    if os.path.isdir(full) and os.path.exists(os.path.join(full, 'assets', 'me-hero.webp')):
        portfolio_dir = full
        break

assets = os.path.join(portfolio_dir, 'assets')
wb = Image.open(os.path.join(assets, 'me-hero-whitebg.webp'))
backup = Image.open(os.path.join(assets, 'me-hero-backup.webp'))
w, h = backup.size

# Let's inspect rows 500, 600, 700, 800, 900, 1000 in backup:
# Find leftmost opaque pixel and rightmost opaque pixel on each row
for y in range(450, 1100, 50):
    opaque_xs = [x for x in range(w) if backup.getpixel((x, y))[3] > 100]
    if opaque_xs:
        min_x, max_x = min(opaque_xs), max(opaque_xs)
        # Check how many transparent pixels lie between min_x and max_x
        holes = [x for x in range(min_x, max_x) if backup.getpixel((x, y))[3] == 0]
        print(f'Row y={y}: min_x={min_x:3d}, max_x={max_x:3d}, total_width={max_x-min_x}, HOLES_INSIDE_BODY={len(holes)}')
