const productSelect = document.getElementById('productSelect');
const currentStockDisplay = document.getElementById('currentStockDisplay');
const currentStockValue = document.getElementById('currentStockValue');
const priceInfo = document.getElementById('priceInfo');
const sellingPriceDisplay = document.getElementById('sellingPriceDisplay');
const purchasePriceDisplay = document.getElementById('purchasePriceDisplay');
const quantityInput = document.getElementById('quantity');
const previewAlert = document.getElementById('previewAlert');
const previewQuantity = document.getElementById('previewQuantity');
const previewNewStock = document.getElementById('previewNewStock');

productSelect.addEventListener('change', function() {
    const selectedOption = this.options[this.selectedIndex];

    if (this.value) {
        const currentQty = parseInt(selectedOption.dataset.quantity) || 0;
        const sellingPrice = parseFloat(selectedOption.dataset.selling) || 0;
        const purchasePrice = parseFloat(selectedOption.dataset.purchase) || 0;

        currentStockValue.textContent = currentQty;
        currentStockDisplay.style.display = 'block';

        sellingPriceDisplay.textContent = `₹${sellingPrice.toFixed(2)}`;
        purchasePriceDisplay.textContent = `₹${purchasePrice.toFixed(2)}`;
        priceInfo.style.display = 'block';

        updatePreview();
    } else {
        currentStockDisplay.style.display = 'none';
        priceInfo.style.display = 'none';
        previewAlert.style.display = 'none';
    }
});

quantityInput.addEventListener('input', updatePreview);

function updatePreview() {
    if (productSelect.value && quantityInput.value) {
        const selectedOption = productSelect.options[productSelect.selectedIndex];
        const currentQty = parseInt(selectedOption.dataset.quantity) || 0;
        const addQty = parseInt(quantityInput.value) || 0;

        if (addQty > 0) {
            const newStock = currentQty + addQty;
            previewQuantity.textContent = addQty;
            previewNewStock.textContent = newStock;
            previewAlert.style.display = 'block';
        } else {
            previewAlert.style.display = 'none';
        }
    } else {
        previewAlert.style.display = 'none';
    }
}

function resetForm() {
    if (confirm('Are you sure you want to reset the form?')) {
        document.getElementById('addStockForm').reset();
        currentStockDisplay.style.display = 'none';
        priceInfo.style.display = 'none';
        previewAlert.style.display = 'none';
    }
}

document.getElementById('addStockForm').addEventListener('submit', function(e) {
    if (!productSelect.value) {
        e.preventDefault();
        alert('Please select a product');
        return false;
    }

    const quantity = parseInt(quantityInput.value);
    if (!quantity || quantity < 1) {
        e.preventDefault();
        alert('Please enter a valid quantity (minimum 1)');
        return false;
    }
});

quantityInput.addEventListener('blur', function() {
    if (this.value) {
        let val = parseInt(this.value);
        if (val < 1) this.value = 1;
    }
});
