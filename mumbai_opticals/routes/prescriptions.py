"""Prescriptions: list, add, edit, view, print, delete, and lookup by customer."""
from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from .. import db
from ..auth import admin_required, require_login
from ..helpers import DELETE_METHODS, save_image

bp = Blueprint('prescriptions', __name__)
bp.before_request(require_login)

PRESCRIPTION_SELECT = """
    SELECT pr.*, c.name AS customer_name, c.phone AS customer_phone, c.email AS customer_email
    FROM prescriptions pr JOIN customers c ON pr.customer_id = c.customer_id
"""


def _get(prescription_id):
    return db.query_one(PRESCRIPTION_SELECT + " WHERE pr.prescription_id = %s", (prescription_id,))


def _form_values():
    form = request.form
    return [
        form.get('prescription_date'),
        form.get('eye', ''),
        form.get('splt') or None,
        form.get('cvl') or None,
        form.get('axis') or None,
        form.get('add_value') or None,
        form.get('vision', ''),
        form.get('pupillary_distance') or None,
    ]


@bp.route('/prescriptions')
def prescriptions_list():
    rows = db.query_all(PRESCRIPTION_SELECT + " ORDER BY pr.prescription_date DESC, pr.prescription_id DESC")
    return render_template('prescriptions/prescriptions_list.html', prescriptions=rows)


@bp.route('/prescriptions/add', methods=['GET', 'POST'])
def add_prescription():
    if request.method == 'GET':
        return render_template('prescriptions/add_prescription.html')

    customer_id = request.form.get('customer_id', type=int)
    if not customer_id or not request.form.get('prescription_date'):
        flash('Please choose a customer and a prescription date.', 'error')
        return redirect(url_for('prescriptions.add_prescription'))

    photo_path = save_image(request.files.get('photo'), 'uploads/prescriptions', prefix='pres')
    if photo_path is None:
        flash('Prescription photo must be a PNG, JPG or GIF image.', 'error')
        return redirect(url_for('prescriptions.add_prescription'))

    db.execute("""
        INSERT INTO prescriptions (customer_id, prescription_date, eye, splt, cvl, axis,
                                   add_value, vision, pupillary_distance, photo_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, [customer_id] + _form_values() + [photo_path])
    db.commit()
    flash('Prescription added successfully!', 'success')
    return redirect(url_for('prescriptions.prescriptions_list'))


@bp.route('/prescriptions/view/<int:prescription_id>')
def view_prescription(prescription_id):
    prescription = _get(prescription_id)
    if not prescription:
        flash('Prescription not found', 'error')
        return redirect(url_for('prescriptions.prescriptions_list'))
    return render_template('prescriptions/view_prescription.html', prescription=prescription)


@bp.route('/prescriptions/print/<int:prescription_id>')
def print_prescription(prescription_id):
    prescription = _get(prescription_id)
    if not prescription:
        flash('Prescription not found', 'error')
        return redirect(url_for('prescriptions.prescriptions_list'))
    return render_template('prescriptions/print_prescription.html', prescription=prescription)


@bp.route('/prescriptions/edit/<int:prescription_id>', methods=['GET', 'POST'])
def edit_prescription(prescription_id):
    prescription = _get(prescription_id)
    if not prescription:
        flash('Prescription not found', 'error')
        return redirect(url_for('prescriptions.prescriptions_list'))

    if request.method == 'GET':
        return render_template('prescriptions/add_prescription.html', edit_mode=True, prescription=prescription)

    if not request.form.get('prescription_date'):
        flash('Prescription date is required.', 'error')
        return redirect(url_for('prescriptions.edit_prescription', prescription_id=prescription_id))

    photo_path = save_image(request.files.get('photo'), 'uploads/prescriptions', prefix='pres')
    if photo_path is None:
        flash('Prescription photo must be a PNG, JPG or GIF image.', 'error')
        return redirect(url_for('prescriptions.edit_prescription', prescription_id=prescription_id))
    photo_path = photo_path or prescription.get('photo_path') or ''

    db.execute("""
        UPDATE prescriptions SET prescription_date = %s, eye = %s, splt = %s, cvl = %s, axis = %s,
               add_value = %s, vision = %s, pupillary_distance = %s, photo_path = %s
        WHERE prescription_id = %s
    """, _form_values() + [photo_path, prescription_id])
    db.commit()
    flash('Prescription updated successfully!', 'success')
    return redirect(url_for('prescriptions.view_prescription', prescription_id=prescription_id))


@bp.route('/prescriptions/delete/<int:prescription_id>', methods=DELETE_METHODS)
@admin_required("You don't have permission to delete prescriptions.", 'prescriptions.prescriptions_list')
def delete_prescription(prescription_id):
    db.execute("DELETE FROM prescriptions WHERE prescription_id = %s", (prescription_id,))
    db.commit()
    flash('Prescription deleted successfully!', 'success')
    return redirect(url_for('prescriptions.prescriptions_list'))


@bp.route('/get_customer_prescriptions')
def get_customer_prescriptions():
    rows = db.query_all("""
        SELECT prescription_id, DATE_FORMAT(prescription_date, '%Y-%m-%d') AS prescription_date,
               eye, splt, cvl, axis, add_value, vision, pupillary_distance
        FROM prescriptions WHERE customer_id = %s
        ORDER BY prescription_date DESC
    """, (request.args.get('customer_id', type=int),))
    return jsonify(db.jsonable(rows))
