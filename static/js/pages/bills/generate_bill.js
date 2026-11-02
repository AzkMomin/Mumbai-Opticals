/* Generate Bill page.
 * Product rows are grouped by type. On submit, every row is sent as
 * items[] / quantities[] / prices[] / discounts[] / details[] (JSON of the row's
 * extra boxes), plus the prescription rows as prescription_rows (JSON).
 * The server recalculates all totals; the summary here is a preview.
 */
(function () {
    'use strict';

    const allProducts = JSON.parse(document.getElementById('billProducts').textContent);
    let prescriptions = [];

    const productsByType = {
        frames: allProducts.filter(p => p.type_name === 'Frames'),
        goggles: allProducts.filter(p => p.type_name === 'Goggles'),
        lenses: allProducts.filter(p => p.type_name === 'Lenses'),
        watches: allProducts.filter(p => p.type_name === 'Wrist Watches' || p.type_name === 'Hand Watches'),
        misc: allProducts.filter(p => !['Frames', 'Goggles', 'Lenses', 'Wrist Watches', 'Hand Watches'].includes(p.type_name))
    };

    const SECTION_INFO = {
        frames: { title: 'Frames', icon: 'fa-glasses' },
        goggles: { title: 'Goggles', icon: 'fa-glasses' },
        lenses: { title: 'Lenses', icon: 'fa-eye' },
        watches: { title: 'Watches', icon: 'fa-clock' },
        misc: { title: 'Misc', icon: 'fa-box' }
    };

    const FIELDS = {
        frames: [
            { name: 'frame_type', label: 'Frame Type' }, { name: 'material', label: 'Material' },
            { name: 'model_name', label: 'Model Name' }, { name: 'model_code', label: 'Model Code' },
            { name: 'model_color', label: 'Color' }, { name: 'model_size', label: 'Size' }
        ],
        lenses: [
            { name: 'lens_for', label: 'Lens For' }, { name: 'lens_type', label: 'Lens Type' },
            { name: 'which_side', label: 'Side' }, { name: 'company', label: 'Company' },
            { name: 'add_on', label: 'Add On' }, { name: 'index_value', label: 'Index' }, { name: 'dia', label: 'DIA' }
        ],
        watches: [
            { name: 'watch_type', label: 'Type' }, { name: 'watch_mechanism', label: 'Mechanism' },
            { name: 'strap_material', label: 'Strap' }, { name: 'dial_color', label: 'Dial' },
            { name: 'model_name', label: 'Model' }, { name: 'model_code', label: 'Code' }
        ],
        misc: [
            { name: 'brand', label: 'Brand' }, { name: 'color', label: 'Color' }, { name: 'size', label: 'Size' }
        ]
    };
    FIELDS.goggles = FIELDS.frames;

    function escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    function money(value) {
        return '₹' + (Number(value) || 0).toFixed(2);
    }

    // ==================== PRODUCT SECTIONS ====================
    function toggleProductType(type) {
        const btn = document.querySelector(`.product-type-btn[data-type="${type}"]`);
        if (btn.classList.contains('active')) {
            btn.classList.remove('active');
            removeSection(type);
        } else {
            btn.classList.add('active');
            createProductSection(type);
        }
    }

    function removeSection(type) {
        const section = document.getElementById(`section_${type}`);
        if (section) section.remove();
        const btn = document.querySelector(`.product-type-btn[data-type="${type}"]`);
        if (btn) btn.classList.remove('active');
        updateAllTotals();
    }

    function createProductSection(type) {
        const info = SECTION_INFO[type];
        const fields = FIELDS[type];
        const html = `
            <div class="product-section" id="section_${type}" data-type="${type}">
                <div class="section-title">
                    <span><i class="fas ${info.icon} me-1"></i>${info.title}</span>
                    <button type="button" class="btn btn-sm btn-danger remove-section-btn" data-remove-section="${type}">
                        <i class="fas fa-times me-1"></i>Remove
                    </button>
                </div>
                <table class="product-table">
                    <thead>
                        <tr>
                            <th>Item</th>
                            ${fields.map(f => `<th>${f.label}</th>`).join('')}
                            <th>Qty</th><th>MRP</th><th>Disc ₹</th><th>Total</th><th></th>
                        </tr>
                    </thead>
                    <tbody id="section_${type}_tbody"></tbody>
                </table>
                <button type="button" class="btn btn-sm btn-primary add-row-btn" data-add-row="${type}">
                    <i class="fas fa-plus me-1"></i>Add
                </button>
            </div>`;
        document.getElementById('tablesContainer').insertAdjacentHTML('beforeend', html);
        addRowToSection(type);
    }

    function addRowToSection(type) {
        const tbody = document.getElementById(`section_${type}_tbody`);
        const options = ['<option value="">-- Select Item --</option>'].concat(
            productsByType[type].map(p =>
                `<option value="${p.product_id}" data-price="${p.selling_price || 0}" data-stock="${p.quantity}">` +
                `${escapeHtml(p.product_name)} (₹${p.selling_price || 0}, ${p.quantity} in stock)</option>`)
        ).join('');
        const fieldCells = FIELDS[type].map(f =>
            `<td><input type="text" class="form-control form-control-sm product-field" data-field="${f.name}" style="font-size: 0.7rem;"></td>`
        ).join('');
        const html = `
            <tr class="bill-row">
                <td><select class="form-control form-control-sm product-select">${options}</select></td>
                ${fieldCells}
                <td><input type="number" class="form-control form-control-sm quantity" value="1" min="1" style="width: 55px; font-size: 0.7rem;"></td>
                <td><input type="number" class="form-control form-control-sm mrp" value="0" min="0" step="0.01" style="width: 70px; font-size: 0.7rem;"></td>
                <td><input type="number" class="form-control form-control-sm discount" value="0" min="0" step="0.01" style="width: 70px; font-size: 0.7rem;"></td>
                <td class="row-total" style="font-size: 0.7rem;">₹0.00</td>
                <td><i class="fas fa-trash remove-row" title="Remove row"></i></td>
            </tr>`;
        tbody.insertAdjacentHTML('beforeend', html);
        updateAllTotals();
    }

    function onProductSelected(select) {
        const row = select.closest('tr');
        const option = select.options[select.selectedIndex];
        const product = allProducts.find(p => String(p.product_id) === select.value);
        row.querySelector('.mrp').value = parseFloat(option.getAttribute('data-price') || 0).toFixed(2);
        if (product) {
            // Pre-fill the detail boxes from the product, staff can still change them
            row.querySelectorAll('.product-field').forEach(input => {
                const value = product[input.dataset.field];
                if (value && !input.value) input.value = value;
            });
        }
        updateAllTotals();
    }

    // ==================== TOTALS ====================
    function rowNumbers(row) {
        const quantity = parseFloat(row.querySelector('.quantity').value) || 0;
        const mrp = parseFloat(row.querySelector('.mrp').value) || 0;
        const gross = quantity * mrp;
        const discount = Math.min(parseFloat(row.querySelector('.discount').value) || 0, gross);
        return { quantity, mrp, gross, discount };
    }

    function updateAllTotals() {
        let subtotal = 0;
        let itemDiscount = 0;
        document.querySelectorAll('#tablesContainer .bill-row').forEach(row => {
            const n = rowNumbers(row);
            subtotal += n.gross;
            itemDiscount += n.discount;
            row.querySelector('.row-total').textContent = money(n.gross - n.discount);
        });
        const additionalDiscount = Math.max(parseFloat(document.getElementById('additionalDiscount').value) || 0, 0);
        const afterDiscount = Math.max(subtotal - itemDiscount - additionalDiscount, 0);
        const taxPercent = Math.max(parseFloat(document.getElementById('tax').value) || 0, 0);
        const taxAmount = afterDiscount * taxPercent / 100;

        document.getElementById('subtotal').textContent = money(subtotal);
        document.getElementById('itemDiscount').textContent = money(itemDiscount);
        document.getElementById('afterDiscount').textContent = money(afterDiscount);
        document.getElementById('taxAmount').textContent = money(taxAmount);
        document.getElementById('grandTotal').textContent = money(afterDiscount + taxAmount);
    }

    // ==================== PRESCRIPTION ====================
    function addPrescriptionRow(values) {
        values = values || {};
        const eye = values.eye || 'Right';
        const cell = (cls, value) =>
            `<td><input type="text" class="form-control form-control-sm ${cls}" value="${escapeHtml(value)}" style="font-size: 0.7rem;"></td>`;
        const html = `
            <tr class="prescription-row">
                <td><select class="form-control form-control-sm eye-select" style="font-size: 0.7rem; min-width: 70px;">
                    ${['Right', 'Left', 'Both'].map(e => `<option value="${e}" ${e === eye ? 'selected' : ''}>${e}</option>`).join('')}
                </select></td>
                ${cell('sph', values.splt)}${cell('cyl', values.cvl)}${cell('axis', values.axis)}
                ${cell('add', values.add_value)}${cell('vision', values.vision)}${cell('pd', values.pupillary_distance)}
                <td><i class="fas fa-trash remove-row" title="Remove row"></i></td>
            </tr>`;
        document.getElementById('prescriptionRows').insertAdjacentHTML('beforeend', html);
    }

    function loadCustomerPrescriptions(customerId) {
        fetch(`/get_customer_prescriptions?customer_id=${customerId}`)
            .then(r => r.json())
            .then(data => {
                prescriptions = Array.isArray(data) ? data : [];
                const select = document.getElementById('prescriptionSelect');
                select.innerHTML = '<option value="">-- Select Prescription --</option>' + prescriptions.map(p =>
                    `<option value="${p.prescription_id}">${escapeHtml(p.prescription_date)} — ${escapeHtml(p.eye || '')}</option>`
                ).join('');
            });
    }

    function loadPrescription() {
        const id = document.getElementById('prescriptionSelect').value;
        const prescription = prescriptions.find(p => String(p.prescription_id) === id);
        if (!prescription) return;
        // Replace an empty first row, otherwise add a new one
        const rows = document.querySelectorAll('#prescriptionRows .prescription-row');
        if (rows.length === 1 && ![...rows[0].querySelectorAll('input')].some(i => i.value.trim())) rows[0].remove();
        addPrescriptionRow(prescription);
    }

    function collectPrescriptionRows() {
        return [...document.querySelectorAll('#prescriptionRows .prescription-row')].map(row => ({
            eye: row.querySelector('.eye-select').value,
            sph: row.querySelector('.sph').value.trim(),
            cyl: row.querySelector('.cyl').value.trim(),
            axis: row.querySelector('.axis').value.trim(),
            add: row.querySelector('.add').value.trim(),
            vision: row.querySelector('.vision').value.trim(),
            pd: row.querySelector('.pd').value.trim()
        })).filter(r => r.sph || r.cyl || r.axis || r.add || r.vision || r.pd);
    }

    // ==================== CUSTOMER SEARCH ====================
    const customerSearch = document.getElementById('customerSearch');
    const customerDropdown = document.getElementById('customerDropdown');
    let customerSearchTimeout;

    function searchCustomers(term) {
        clearTimeout(customerSearchTimeout);
        customerSearchTimeout = setTimeout(() => {
            fetch(`/search_customers?term=${encodeURIComponent(term)}`)
                .then(r => r.json()).then(updateCustomerDropdown);
        }, 250);
    }

    function updateCustomerDropdown(customers) {
        customerDropdown.innerHTML = '';
        if (!Array.isArray(customers) || !customers.length) {
            customerDropdown.innerHTML = '<div class="search-dropdown-item text-muted">No customers found</div>';
            customerDropdown.style.display = 'block';
            return;
        }
        customers.forEach(c => {
            const div = document.createElement('div');
            div.className = 'search-dropdown-item';
            div.innerHTML = `<div><strong>${escapeHtml(c.name)}</strong><br><small>${escapeHtml(c.phone)}</small></div>`;
            div.addEventListener('click', () => selectCustomer(c));
            customerDropdown.appendChild(div);
        });
        customerDropdown.style.display = 'block';
    }

    function selectCustomer(customer) {
        document.getElementById('customerId').value = customer.customer_id;
        document.getElementById('selectedCustomerName').textContent = customer.name;
        document.getElementById('selectedCustomerDetails').textContent = `${customer.phone} | ${customer.email || ''}`;
        document.getElementById('selectedCustomer').style.display = 'block';
        customerSearch.value = '';
        customerDropdown.style.display = 'none';
        loadCustomerPrescriptions(customer.customer_id);
    }

    function clearCustomer() {
        document.getElementById('customerId').value = '';
        document.getElementById('selectedCustomer').style.display = 'none';
        document.getElementById('prescriptionSelect').innerHTML = '<option value="">-- Select Prescription --</option>';
        customerSearch.value = '';
    }

    // ==================== SUBMIT ====================
    function addHidden(form, name, value) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value;
        input.className = 'generated-field';
        form.appendChild(input);
    }

    function onSubmit(e) {
        const form = e.target;
        form.querySelectorAll('.generated-field').forEach(el => el.remove());

        if (!document.getElementById('customerId').value) {
            e.preventDefault();
            alert('Please select a customer.');
            return;
        }

        const rows = [...document.querySelectorAll('#tablesContainer .bill-row')];
        const used = {};
        let count = 0;
        for (const row of rows) {
            const select = row.querySelector('.product-select');
            if (!select.value) continue;
            const n = rowNumbers(row);
            if (n.quantity < 1) {
                e.preventDefault();
                alert('Quantity must be at least 1.');
                return;
            }
            used[select.value] = (used[select.value] || 0) + n.quantity;
            const stock = parseInt(select.options[select.selectedIndex].getAttribute('data-stock'), 10);
            if (used[select.value] > stock) {
                e.preventDefault();
                alert(`Only ${stock} in stock for ${select.options[select.selectedIndex].text.split(' (')[0]}.`);
                return;
            }
            const details = {};
            row.querySelectorAll('.product-field').forEach(input => {
                if (input.value.trim()) details[input.dataset.field] = input.value.trim();
            });
            addHidden(form, 'items[]', select.value);
            addHidden(form, 'quantities[]', n.quantity);
            addHidden(form, 'prices[]', n.mrp);
            addHidden(form, 'discounts[]', n.discount);
            addHidden(form, 'details[]', JSON.stringify(details));
            count++;
        }
        if (!count) {
            e.preventDefault();
            alert('Please add at least one product to the bill.');
            return;
        }
        addHidden(form, 'additional_discount', document.getElementById('additionalDiscount').value || 0);
        addHidden(form, 'prescription_rows', JSON.stringify(collectPrescriptionRows()));
        addHidden(form, 'prescription_id', document.getElementById('prescriptionSelect').value || '');
        document.getElementById('generateBtn').disabled = true;
    }

    // ==================== EVENTS ====================
    document.querySelectorAll('.product-type-btn').forEach(btn =>
        btn.addEventListener('click', () => toggleProductType(btn.dataset.type)));

    document.getElementById('tablesContainer').addEventListener('click', e => {
        const remove = e.target.closest('[data-remove-section]');
        if (remove) return removeSection(remove.dataset.removeSection);
        const add = e.target.closest('[data-add-row]');
        if (add) return addRowToSection(add.dataset.addRow);
        if (e.target.classList.contains('remove-row')) {
            e.target.closest('tr').remove();
            updateAllTotals();
        }
    });
    document.getElementById('tablesContainer').addEventListener('change', e => {
        if (e.target.classList.contains('product-select')) onProductSelected(e.target);
        else updateAllTotals();
    });
    document.getElementById('tablesContainer').addEventListener('input', e => {
        if (e.target.matches('.quantity, .mrp, .discount')) updateAllTotals();
    });
    document.getElementById('prescriptionRows').addEventListener('click', e => {
        if (e.target.classList.contains('remove-row')) e.target.closest('tr').remove();
    });

    document.getElementById('additionalDiscount').addEventListener('input', updateAllTotals);
    document.getElementById('tax').addEventListener('input', updateAllTotals);
    document.getElementById('loadPrescriptionBtn').addEventListener('click', loadPrescription);
    document.getElementById('addPrescriptionRowBtn').addEventListener('click', () => addPrescriptionRow());
    document.getElementById('clearCustomerBtn').addEventListener('click', clearCustomer);
    document.getElementById('billForm').addEventListener('submit', onSubmit);

    customerSearch.addEventListener('input', () => searchCustomers(customerSearch.value.trim()));
    customerSearch.addEventListener('focus', () => searchCustomers(customerSearch.value.trim()));
    document.addEventListener('click', e => {
        if (!e.target.closest('.search-wrapper')) customerDropdown.style.display = 'none';
    });

    addPrescriptionRow();
    updateAllTotals();
})();
