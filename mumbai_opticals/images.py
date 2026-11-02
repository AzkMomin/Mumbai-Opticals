"""Product photo processing: remove a plain background and place the product on a
soft backdrop that suits it.

Uses Pillow only, so it runs on PythonAnywhere without extra installs. It works
best for photos taken against a plain or evenly lit background (a table top, a
wall, a sheet of paper). When the background is too busy to separate safely, the
photo is kept as it is (only resized), so nothing is ever cut off by mistake.
The original upload is always kept next to the processed image.
"""
import colorsys
import os
import uuid
from collections import deque

from werkzeug.utils import secure_filename

from .settings import ALLOWED_IMAGE_EXTENSIONS, STATIC_DIR

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
except ImportError:  # Pillow missing: uploads are saved without processing
    Image = None

CANVAS = (1200, 900)          # 4:3, matches the product cards
PRODUCT_BOX = (0.80, 0.76)    # share of the canvas the product may fill
MAX_SOURCE = 1600             # longest side kept for the original
MASK_SIZE = 360               # background detection runs on a small copy
BG_TOLERANCE = 38             # how far (0-255) a pixel may differ from the background colour
HOLE_TOLERANCE = 16           # stricter match for enclosed areas (so a white dial isn't taken for background)


def allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS | {'webp'}


def save_product_photo(file, folder):
    """Save an uploaded photo. Returns dict(path, original_path, bg_removed) with paths
    relative to static/, None if no file was sent, or raises ValueError for a bad file."""
    if not file or not file.filename:
        return None
    if not allowed(file.filename):
        raise ValueError("Product photos must be JPG, PNG, GIF or WEBP images.")

    target_dir = os.path.join(STATIC_DIR, folder)
    original_dir = os.path.join(target_dir, 'originals')
    os.makedirs(original_dir, exist_ok=True)
    stem = f"{uuid.uuid4().hex[:12]}_{os.path.splitext(secure_filename(file.filename))[0][:40] or 'photo'}"

    if Image is None:
        name = f"{stem}{os.path.splitext(file.filename)[1].lower()}"
        file.save(os.path.join(target_dir, name))
        rel = f"{folder}/{name}"
        return {'path': rel, 'original_path': rel, 'bg_removed': 0}

    try:
        img = Image.open(file.stream)
        img = ImageOps.exif_transpose(img)
        img.load()
    except Exception as e:
        raise ValueError("That file couldn't be read as an image.") from e

    img = img.convert('RGBA')
    img.thumbnail((MAX_SOURCE, MAX_SOURCE), Image.LANCZOS)

    original_name = f"{stem}.png" if _has_transparency(img) else f"{stem}.jpg"
    original_path = os.path.join(original_dir, original_name)
    if original_name.endswith('.png'):
        img.save(original_path, optimize=True)
    else:
        img.convert('RGB').save(original_path, quality=90, optimize=True)

    result, removed = compose_on_backdrop(img)
    name = f"{stem}_shop.jpg"
    result.save(os.path.join(target_dir, name), quality=86, optimize=True, progressive=True)
    return {
        'path': f"{folder}/{name}",
        'original_path': f"{folder}/originals/{original_name}",
        'bg_removed': 1 if removed else 0,
    }


def reprocess(original_rel_path, folder):
    """Run the background step again on a stored original. Returns the new relative path."""
    src = Image.open(os.path.join(STATIC_DIR, original_rel_path)).convert('RGBA')
    result, removed = compose_on_backdrop(src)
    name = f"{uuid.uuid4().hex[:12]}_shop.jpg"
    result.save(os.path.join(STATIC_DIR, folder, name), quality=86, optimize=True, progressive=True)
    return f"{folder}/{name}", removed


# ---------------------------------------------------------------- internals

def _has_transparency(img):
    alpha = img.getchannel('A')
    return alpha.getextrema()[0] < 250


def compose_on_backdrop(img):
    """Return (RGB canvas image, background_was_removed)."""
    mask = _foreground_mask(img)
    removed = mask is not None
    if mask is None:
        # Couldn't separate the product: keep the photo, fitted onto the canvas
        return _fit_photo(img), False

    product = img.copy()
    product.putalpha(mask)
    box = product.getbbox() or (0, 0, *product.size)
    product = product.crop(box)

    backdrop = _backdrop_for(product)
    max_w, max_h = int(CANVAS[0] * PRODUCT_BOX[0]), int(CANVAS[1] * PRODUCT_BOX[1])
    scale = min(max_w / product.width, max_h / product.height)
    size = (max(1, int(product.width * scale)), max(1, int(product.height * scale)))
    product = product.resize(size, Image.LANCZOS)
    x = (CANVAS[0] - size[0]) // 2
    y = (CANVAS[1] - size[1]) // 2 - int(CANVAS[1] * 0.02)

    # Soft contact shadow under the product
    shadow = Image.new('L', CANVAS, 0)
    sw, sh = int(size[0] * 0.78), max(14, int(size[1] * 0.07))
    sx, sy = (CANVAS[0] - sw) // 2, y + size[1] - sh // 2
    ImageDraw.Draw(shadow).ellipse((sx, sy, sx + sw, sy + sh), fill=70)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    backdrop.paste((20, 30, 40), (0, 0), shadow)

    backdrop.paste(product, (x, y), product)
    return backdrop.convert('RGB'), removed


def _fit_photo(img):
    canvas = Image.new('RGB', CANVAS, _border_colour(img) or (240, 243, 246))
    photo = img.convert('RGB')
    photo.thumbnail(CANVAS, Image.LANCZOS)
    canvas.paste(photo, ((CANVAS[0] - photo.width) // 2, (CANVAS[1] - photo.height) // 2))
    return canvas


def _border_pixels(small):
    w, h = small.size
    px = small.load()
    points = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + \
             [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    return [px[p][:3] for p in points], points


def _border_colour(img):
    small = img.convert('RGB').copy()
    small.thumbnail((64, 64))
    colours, _ = _border_pixels(small)
    n = len(colours)
    return tuple(sorted(c[i] for c in colours)[n // 2] for i in range(3)) if n else None


def _foreground_mask(img):
    """Full-size alpha mask (L) of the product, or None if separation isn't safe."""
    if _has_transparency(img):
        alpha = img.getchannel('A')
        coverage = sum(1 for v in alpha.resize((80, 80)).getdata() if v > 128) / 6400
        return alpha if 0.03 < coverage < 0.97 else None

    small = img.convert('RGB')
    small.thumbnail((MASK_SIZE, MASK_SIZE), Image.BILINEAR)
    small = small.filter(ImageFilter.MedianFilter(3))
    w, h = small.size

    colours, points = _border_pixels(small)
    bg = tuple(sorted(c[i] for c in colours)[len(colours) // 2] for i in range(3))
    # A busy border means there's no plain background to remove
    close = sum(1 for c in colours if max(abs(c[i] - bg[i]) for i in range(3)) < BG_TOLERANCE)
    if close / len(colours) < 0.55:
        return None

    # Distance from the background colour (max over channels), as a mask: 255 = looks like background
    diff = ImageChops.difference(small, Image.new('RGB', small.size, bg))
    r, g, b = diff.split()
    distance = ImageChops.lighter(ImageChops.lighter(r, g), b)
    similar = distance.point(lambda v: 255 if v < BG_TOLERANCE else 0)
    sim = similar.load()

    # Background = "similar" pixels connected to the border
    background = bytearray(w * h)
    queue = deque()
    for x, y in points:
        if sim[x, y] and not background[y * w + x]:
            background[y * w + x] = 1
            queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h:
                i = ny * w + nx
                if not background[i] and sim[nx, ny]:
                    background[i] = 1
                    queue.append((nx, ny))

    # Enclosed areas that clearly show the background (e.g. through the lenses of a frame)
    strict = distance.point(lambda v: 255 if v < HOLE_TOLERANCE else 0).load()
    min_hole = int(w * h * 0.002)
    seen = bytearray(w * h)
    for start in range(w * h):
        if background[start] or seen[start]:
            continue
        sx, sy = start % w, start // w
        if not strict[sx, sy]:
            continue
        component, queue = [start], deque([(sx, sy)])
        seen[start] = 1
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    i = ny * w + nx
                    if not seen[i] and not background[i] and strict[nx, ny]:
                        seen[i] = 1
                        component.append(i)
                        queue.append((nx, ny))
        if len(component) >= min_hole:
            for i in component:
                background[i] = 1

    fg_share = 1 - sum(background) / (w * h)
    if not 0.03 < fg_share < 0.95:
        return None

    mask_small = Image.frombytes('L', (w, h), bytes(0 if v else 255 for v in background))
    # Fill pin-holes inside the product, then smooth the edge
    mask_small = mask_small.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    mask = mask_small.resize(img.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.2))
    return mask.point(lambda v: 0 if v < 40 else (255 if v > 215 else v))


def _backdrop_for(product):
    """A soft radial backdrop chosen from the product's own colour so it stands out."""
    sample = product.copy()
    sample.thumbnail((80, 80))
    pixels = [p for p in sample.getdata() if p[3] > 200]
    if pixels:
        r = sum(p[0] for p in pixels) / len(pixels) / 255
        g = sum(p[1] for p in pixels) / len(pixels) / 255
        b = sum(p[2] for p in pixels) / len(pixels) / 255
    else:
        r = g = b = 0.5
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)

    if light > 0.72:
        # Light products (white, silver, clear) need a deeper backdrop to show their edges
        centre = colorsys.hls_to_rgb(0.58, 0.80, 0.18)
        edge = colorsys.hls_to_rgb(0.58, 0.70, 0.20)
    elif sat < 0.12:
        # Black / grey / metal: cool, very light grey-blue
        centre = colorsys.hls_to_rgb(0.57, 0.975, 0.25)
        edge = colorsys.hls_to_rgb(0.57, 0.90, 0.18)
    else:
        # Coloured products: a pale tint of the opposite hue keeps the colour true but separated
        bg_hue = (hue + 0.5) % 1.0
        centre = colorsys.hls_to_rgb(bg_hue, 0.965, 0.30)
        edge = colorsys.hls_to_rgb(bg_hue, 0.89, 0.22)

    centre = tuple(int(c * 255) for c in centre)
    edge = tuple(int(c * 255) for c in edge)
    gradient = Image.radial_gradient('L').resize(CANVAS, Image.BILINEAR)  # 0 centre -> 255 edge
    return Image.composite(Image.new('RGBA', CANVAS, edge + (255,)),
                           Image.new('RGBA', CANVAS, centre + (255,)), gradient)
