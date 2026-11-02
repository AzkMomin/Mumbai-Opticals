"""App-wide settings. Secrets (database password etc.) live in config.py, which is not in git."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_NAME = 'hamdanopticals$mumbaiopticals'

STATIC_DIR = os.path.join(BASE_DIR, 'static')
PRODUCT_UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads', 'products')
PRESCRIPTION_UPLOAD_DIR = os.path.join(STATIC_DIR, 'uploads', 'prescriptions')
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_UPLOAD_BYTES = 16 * 1024 * 1024

PER_PAGE = 10

# Third-party libraries loaded from CDNs (one place to upgrade them)
CDN = {
    'bootstrap_css': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
    'bootstrap_js': 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js',
    'fontawesome_css': 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css',
}

# Shop details shown on bills, printed bills, prescriptions and the customer bill page.
# Used only when the CompanyDetail table in the database is empty; fill that table in instead.
COMPANY = {
    'name': 'Mumbai Opticals',
    'address': '123, Linking Road, Bandra West, Mumbai - 400050',
    'phone': '+91 98765 43210',
    'email': 'info@mumbaiopticals.com',
    'gst': '27AAECM1234F1Z9',
    'logo': 'Images/Logo/Logo.png',
}

ADMIN_ROLES = ('super-admin', 'admin')

# Extra product fields shown on the Add Product form, by product type
PRODUCT_TYPE_FIELDS = {
    ('Goggles', 'Frames'): [
        {'name': 'frame_type', 'label': 'Frame Type', 'type': 'select',
         'options': ['Full Rim', 'Half Rim', 'Rimless', 'Sports']},
        {'name': 'material', 'label': 'Material', 'type': 'select',
         'options': ['Metal', 'Plastic', 'Acetate', 'Titanium', 'Stainless Steel', 'Wood']},
        {'name': 'model_name', 'label': 'Model Name', 'type': 'text'},
        {'name': 'model_code', 'label': 'Model Code', 'type': 'text'},
        {'name': 'model_color', 'label': 'Model Color', 'type': 'text'},
        {'name': 'model_size', 'label': 'Model Size', 'type': 'text', 'placeholder': 'e.g., 52-18-140'},
    ],
    ('Lenses',): [
        {'name': 'lens_type', 'label': 'Lens Type', 'type': 'select',
         'options': ['Single Vision', 'Bifocal', 'Progressive', 'Photochromic', 'Blue Cut', 'Polarized']},
        {'name': 'which_side', 'label': 'Which Side', 'type': 'select', 'options': ['Both', 'Right Only', 'Left Only']},
        {'name': 'lens_for', 'label': 'Lens For', 'type': 'text', 'placeholder': 'e.g., Reading, Distance, Computer'},
        {'name': 'company', 'label': 'Company', 'type': 'text', 'placeholder': 'e.g., Zeiss, Kodak, Crizal'},
    ],
    ('Wrist Watches', 'Hand Watches'): [
        {'name': 'watch_type', 'label': 'Watch Type', 'type': 'select',
         'options': ['Analog', 'Digital', 'Analog-Digital', 'Smart']},
        {'name': 'watch_mechanism', 'label': 'Mechanism', 'type': 'select',
         'options': ['Quartz', 'Automatic', 'Mechanical', 'Solar', 'Kinetic']},
        {'name': 'strap_material', 'label': 'Strap Material', 'type': 'select',
         'options': ['Leather', 'Metal', 'Silicone', 'Fabric', 'Rubber']},
        {'name': 'dial_color', 'label': 'Dial Color', 'type': 'text'},
        {'name': 'water_resistance', 'label': 'Water Resistance', 'type': 'text', 'placeholder': 'e.g., 50m, 100m, 200m'},
        {'name': 'model_name', 'label': 'Model Name', 'type': 'text'},
        {'name': 'model_code', 'label': 'Model Code', 'type': 'text'},
    ],
}

# Product columns filled from the Add/Edit Product forms
PRODUCT_DETAIL_COLUMNS = [
    'frame_type', 'material', 'model_name', 'model_code', 'model_color', 'model_size',
    'lens_type', 'which_side', 'lens_for', 'company',
    'watch_type', 'watch_mechanism', 'strap_material', 'water_resistance', 'dial_color',
]


def load_local_config():
    """Read secrets from config.py (kept out of git) with safe fallbacks."""
    try:
        import config  # noqa: WPS433 - optional local module
    except ImportError:
        config = None
    get = (lambda name, default=None: getattr(config, name, default)) if config else (lambda name, default=None: default)
    return {
        'DB_HOST': get('HOST', 'localhost'),
        'DB_USER': get('USER'),
        'DB_PASSWORD': get('PASSWORD'),
        'DB_NAME': get('DB_NAME', DB_NAME),
        'SECRET_KEY': get('SECRET_KEY'),
        'WEBHOOK_SECRET': get('WEBHOOK_SECRET'),
        'WSGI_FILE': get('WSGI_FILE'),
    }
