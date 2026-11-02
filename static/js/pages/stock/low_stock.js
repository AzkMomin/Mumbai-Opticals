const addStockModal = new bootstrap.Modal(document.getElementById('addStockModal'));

function addStock(productId) {
    document.getElementById('modalProductId').value = productId;
    addStockModal.show();
}
