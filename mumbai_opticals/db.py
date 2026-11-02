"""Database access: one MySQL connection per request, closed automatically.

Writes must be followed by commit(). Anything not committed is rolled back when
the request ends, so a request that fails half-way never leaves partial data.
"""
from decimal import Decimal

import mysql.connector
from flask import current_app, g


def get_db():
    if 'db' not in g:
        cfg = current_app.config
        g.db = mysql.connector.connect(
            host=cfg['DB_HOST'],
            user=cfg['DB_USER'],
            password=cfg['DB_PASSWORD'],
            database=cfg['DB_NAME'],
        )
    return g.db


def cursor():
    return get_db().cursor(dictionary=True, buffered=True)


def query_all(sql, params=()):
    cur = cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def query_one(sql, params=()):
    cur = cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def query_value(sql, params=()):
    row = query_one(sql, params)
    return next(iter(row.values())) if row else None


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE. Returns the new row id for inserts."""
    cur = cursor()
    try:
        cur.execute(sql, params)
        return cur.lastrowid
    finally:
        cur.close()


def commit():
    get_db().commit()


def close_db(_exc=None):
    db = g.pop('db', None)
    if db is not None:
        try:
            db.rollback()  # discards anything not committed
        finally:
            db.close()


def to_float(value):
    return float(value) if value else 0.0


def floatify(row, *keys):
    """Convert Decimal/None money columns in a row to float (in place)."""
    for key in keys:
        if key in row:
            row[key] = to_float(row[key])
    return row


def jsonable(rows):
    """Make query rows safe for jsonify (Decimal -> float)."""
    out = []
    for row in rows:
        out.append({k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()})
    return out
