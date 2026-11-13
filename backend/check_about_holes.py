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
about = Image.open(os.path.join(assets, 'me-about.webp'))

# Check holes inside torso in about image
w, h = about.size
for y in range(300, 800, 50):
    opaque_xs = [x for x in range(w) if about.getpixel((x, y))[3] > 100]
    if opaque_xs:
        min_x, max_x = min(opaque_xs), max(opaque_xs)
        holes = [x for x in range(min_x, max_x) if about.getpixel((x, y))[3] == 0]
        if holes:
            print(f'About Row y={y}: holes={len(holes)}')
