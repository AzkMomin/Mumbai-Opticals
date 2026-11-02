"""Small, additive database changes the app needs. Runs once per process.

Only ever adds nullable columns and new tables, so existing data is never changed.
"""
from flask import current_app

from . import db

REQUIRED_COLUMNS = [
    # (table, column, definition)
    ('bill_items', 'details', 'TEXT NULL'),               # extra boxes from the bill form (JSON)
    ('bills', 'prescription_details', 'TEXT NULL'),       # prescription rows entered on the bill (JSON)
]

REQUIRED_TABLES = {
    # Several photos per product. products.product_image keeps the main photo's path.
    'product_images': """
        CREATE TABLE IF NOT EXISTS product_images (
            image_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            path VARCHAR(500) NOT NULL,
            original_path VARCHAR(500) NULL,
            processed_path VARCHAR(500) NULL,
            bg_removed TINYINT(1) NOT NULL DEFAULT 0,
            sort_order INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_product_images_product (product_id, sort_order),
            CONSTRAINT fk_product_images_product FOREIGN KEY (product_id)
                REFERENCES products (product_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # Customer ratings and reviews (shown immediately; staff can hide them)
    'product_reviews': """
        CREATE TABLE IF NOT EXISTS product_reviews (
            review_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            name VARCHAR(80) NOT NULL,
            phone VARCHAR(20) NULL,
            rating TINYINT NOT NULL,
            title VARCHAR(150) NULL,
            body TEXT NULL,
            verified TINYINT(1) NOT NULL DEFAULT 0,
            helpful INT NOT NULL DEFAULT 0,
            status ENUM('published', 'hidden') NOT NULL DEFAULT 'published',
            created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_reviews_product (product_id, status),
            CONSTRAINT fk_reviews_product FOREIGN KEY (product_id)
                REFERENCES products (product_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # Customer questions, shown once staff answer them
    'product_questions': """
        CREATE TABLE IF NOT EXISTS product_questions (
            question_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            product_id INT NOT NULL,
            name VARCHAR(80) NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NULL,
            answered_by INT NULL,
            answered_at TIMESTAMP NULL,
            status ENUM('pending', 'published', 'hidden') NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_questions_product (product_id, status),
            CONSTRAINT fk_questions_product FOREIGN KEY (product_id)
                REFERENCES products (product_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}

_checked = False


def ensure_schema():
    global _checked
    if _checked:
        return
    _checked = True
    try:
        for table, column, definition in REQUIRED_COLUMNS:
            exists = db.query_value("""
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """, (table, column))
            if not exists:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                current_app.logger.warning("Added column %s.%s", table, column)
        for table, ddl in REQUIRED_TABLES.items():
            exists = db.query_value("""
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """, (table,))
            if not exists:
                db.execute(ddl)
                current_app.logger.warning("Created table %s", table)
        # Existing single product photos become the first photo in the gallery
        db.execute("""
            INSERT INTO product_images (product_id, path, original_path, processed_path, bg_removed, sort_order)
            SELECT p.product_id, p.product_image, p.product_image, NULL, 0, 0 FROM products p
            WHERE p.product_image IS NOT NULL AND p.product_image != ''
              AND NOT EXISTS (SELECT 1 FROM product_images i WHERE i.product_id = p.product_id)
        """)
        db.commit()
    except Exception as e:  # never block the site over this
        current_app.logger.exception("Schema check failed: %s", e)
