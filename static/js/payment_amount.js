/* Payment amount box (Receive Payment / Edit Payment).
 * <input data-max-amount="1234.50" data-limit-label="remaining amount">
 * Checks the amount when the box is left: if it's empty, zero or more than allowed,
 * a message shows under the box and the cursor goes back into it. Saving is blocked
 * until it's fixed; links and Back/Cancel still work.
 */
(function () {
    'use strict';
    const input = document.querySelector('[data-max-amount]');
    if (!input) return;
    const form = input.form;
    const max = Math.round(parseFloat(input.dataset.maxAmount) * 100) / 100;
    const limitLabel = input.dataset.limitLabel || 'the remaining amount on this bill';
    const money = v => '₹' + v.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    const message = document.createElement('div');
    message.className = 'invalid-feedback d-block amount-error';
    message.setAttribute('role', 'alert');
    message.hidden = true;
    (input.closest('.input-group') || input).insertAdjacentElement('afterend', message);

    function problem() {
        const raw = input.value.trim();
        const value = parseFloat(raw);
        if (!raw || isNaN(value)) return 'Enter the amount received.';
        if (value <= 0) return 'The amount must be more than ₹0.';
        if (Math.round(value * 100) / 100 > max) {
            return `You cannot receive more than ${money(max)}, ${limitLabel}.`;
        }
        return '';
    }

    function show(text) {
        message.textContent = text;
        message.hidden = !text;
        input.classList.toggle('is-invalid', !!text);
        input.setAttribute('aria-invalid', text ? 'true' : 'false');
    }

    // While typing: clear the message as soon as the amount becomes valid
    input.addEventListener('input', () => { if (!problem()) show(''); });

    // Leaving the box: check, and keep the cursor here until it's right
    input.addEventListener('blur', () => {
        const text = problem();
        show(text);
        if (text) setTimeout(() => { input.focus(); input.select(); }, 0);
    });

    // Never save an invalid amount
    form.addEventListener('submit', e => {
        const text = problem();
        if (text) {
            e.preventDefault();
            e.stopImmediatePropagation();
            show(text);
            input.focus();
            input.select();
        }
    }, true);
})();
