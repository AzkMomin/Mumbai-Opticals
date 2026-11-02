// Initialize modals
let imagePreviewModal;
let deleteModal;

// Image zoom variables
let currentZoom = 1;
let isDragging = false;
let startX, startY;
let translateX = 0, translateY = 0;
const zoomStep = 0.25;
const maxZoom = 3;
const minZoom = 0.5;

// Debounce timer for filter
let filterTimeout;

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    imagePreviewModal = new bootstrap.Modal(document.getElementById('imagePreviewModal'));
    deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));

    // Debug: Log all image paths
    document.querySelectorAll('.prescription-image').forEach(img => {
        console.log('Image path:', img.src);
        console.log('Image exists?', img.complete ? 'Yes' : 'No');

        img.onerror = function() {
            console.log('Failed to load:', this.src);
            this.style.display = 'none';
            // Create and insert placeholder
            const placeholder = document.createElement('div');
            placeholder.className = 'image-placeholder me-3';
            placeholder.innerHTML = '<i class="fas fa-prescription"></i>';
            placeholder.onclick = function() { previewImage(null); };
            this.parentNode.insertBefore(placeholder, this);
        };

        img.onload = function() {
            console.log('Successfully loaded:', this.src);
        };
    });

    // Initialize image element event listeners
    const modalImage = document.getElementById('modalPreviewImage');
    if (modalImage) {
        modalImage.addEventListener('load', function() {
            const dimensions = `${this.naturalWidth} x ${this.naturalHeight} px`;
            document.getElementById('imageDimensions').textContent = dimensions;
        });

        modalImage.addEventListener('mousedown', startDrag);
        modalImage.addEventListener('mousemove', drag);
        modalImage.addEventListener('mouseup', stopDrag);
        modalImage.addEventListener('mouseleave', stopDrag);
    }

    // Apply initial filters
    applyFilters();
});

// Image Preview Function
function previewImage(imagePath) {
    console.log('Preview image called with path:', imagePath);

    const modalImage = document.getElementById('modalPreviewImage');
    const downloadBtn = document.getElementById('downloadImageBtn');

    // Reset zoom for new image
    resetZoom();

    if (imagePath && imagePath !== '#' && imagePath !== 'null') {
        modalImage.src = imagePath;
        downloadBtn.href = imagePath;

        modalImage.onload = function() {
            console.log('Modal image loaded successfully');
        };

        modalImage.onerror = function() {
            console.log('Modal image failed to load, using placeholder');
            modalImage.src = 'https://via.placeholder.com/800x600?text=Image+Not+Found';
            downloadBtn.href = '#';
        };
    } else {
        console.log('No image path provided, showing placeholder');
        modalImage.src = 'https://via.placeholder.com/800x600?text=No+Image+Uploaded';
        downloadBtn.href = '#';
    }

    if (imagePreviewModal) {
        imagePreviewModal.show();
    } else {
        console.error('Modal not initialized');
        // Fallback
        const modalElement = document.getElementById('imagePreviewModal');
        if (modalElement) {
            const modal = new bootstrap.Modal(modalElement);
            modal.show();
        }
    }
}

// Zoom Functions
function zoomIn() {
    const img = document.getElementById('modalPreviewImage');
    if (currentZoom < maxZoom) {
        currentZoom += zoomStep;
        updateImageTransform(img);
        img.style.cursor = currentZoom > 1 ? 'zoom-out' : 'zoom-in';
        updateZoomLevel();
    }
}

function zoomOut() {
    const img = document.getElementById('modalPreviewImage');
    if (currentZoom > minZoom) {
        currentZoom -= zoomStep;
        updateImageTransform(img);
        img.style.cursor = currentZoom > 1 ? 'zoom-out' : 'zoom-in';
        updateZoomLevel();
    }
}

function resetZoom() {
    const img = document.getElementById('modalPreviewImage');
    currentZoom = 1;
    translateX = 0;
    translateY = 0;
    img.style.transform = 'scale(1) translate(0px, 0px)';
    img.style.cursor = 'zoom-in';
    updateZoomLevel();
}

function toggleZoom(img) {
    if (currentZoom === 1) {
        zoomIn();
    } else {
        resetZoom();
    }
}

function updateZoomLevel() {
    document.getElementById('zoomLevel').textContent = Math.round(currentZoom * 100) + '%';
}

function toggleFullScreen() {
    const modalBody = document.querySelector('.modal-body');
    if (!document.fullscreenElement) {
        modalBody.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

// Pan Functions
function startDrag(e) {
    if (currentZoom > 1) {
        isDragging = true;
        startX = e.clientX - translateX;
        startY = e.clientY - translateY;
        e.target.style.cursor = 'grabbing';
    }
}

function drag(e) {
    if (isDragging && currentZoom > 1) {
        e.preventDefault();
        translateX = e.clientX - startX;
        translateY = e.clientY - startY;

        // Constrain panning based on zoom level
        const img = document.getElementById('modalPreviewImage');
        const container = document.getElementById('imageContainer');

        // Calculate max pan distance based on zoom
        const imgWidth = img.naturalWidth * currentZoom;
        const imgHeight = img.naturalHeight * currentZoom;
        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;

        const maxTranslateX = Math.max(0, (imgWidth - containerWidth) / 2);
        const maxTranslateY = Math.max(0, (imgHeight - containerHeight) / 2);

        translateX = Math.min(Math.max(translateX, -maxTranslateX), maxTranslateX);
        translateY = Math.min(Math.max(translateY, -maxTranslateY), maxTranslateY);

        updateImageTransform(img);
    }
}

function stopDrag(e) {
    isDragging = false;
    e.target.style.cursor = currentZoom > 1 ? 'zoom-out' : 'zoom-in';
}

function updateImageTransform(img) {
    img.style.transform = `scale(${currentZoom}) translate(${translateX}px, ${translateY}px)`;
}

// Keyboard shortcuts for zoom
document.addEventListener('keydown', function(e) {
    const modalElement = document.getElementById('imagePreviewModal');
    if (modalElement && modalElement.classList.contains('show')) {
        // Zoom in with + or =
        if (e.key === '+' || e.key === '=') {
            e.preventDefault();
            zoomIn();
        }
        // Zoom out with - or _
        else if (e.key === '-' || e.key === '_') {
            e.preventDefault();
            zoomOut();
        }
        // Reset zoom with 0
        else if (e.key === '0') {
            e.preventDefault();
            resetZoom();
        }
        // Escape to reset zoom
        else if (e.key === 'Escape') {
            resetZoom();
        }
    }
});

// Reset zoom when modal is hidden
document.getElementById('imagePreviewModal').addEventListener('hidden.bs.modal', function () {
    resetZoom();
});

// CRUD Functions
function viewPrescription(id) {
    window.open(`/prescriptions/view/${id}`, '_blank');
}

function editPrescription(id) {
    window.location.href = `/prescriptions/edit/${id}`;
}

function printPrescription(id) {
    window.open(`/prescriptions/print/${id}`, '_blank');
}

function confirmDelete(id) {
    document.getElementById('confirmDeleteBtn').href = `/prescriptions/delete/${id}`;
    if (deleteModal) {
        deleteModal.show();
    }
}

// Filter Function - Real-time with debounce
function applyFilters() {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(function() {
        const searchTerm = document.getElementById('searchPrescription').value.toLowerCase();
        const dateFilter = document.getElementById('dateFilter').value;
        const eyeFilter = document.getElementById('eyeFilter').value;

        const prescriptions = document.querySelectorAll('.prescription-card');
        let visibleCount = 0;

        prescriptions.forEach(prescription => {
            let show = true;
            const text = prescription.textContent.toLowerCase();
            const presDate = prescription.getAttribute('data-date');
            const presEye = prescription.getAttribute('data-eye');

            // Search filter
            if (searchTerm && !text.includes(searchTerm)) {
                show = false;
            }

            // Date filter
            if (dateFilter && presDate !== dateFilter) {
                show = false;
            }

            // Eye filter
            if (eyeFilter && presEye !== eyeFilter) {
                show = false;
            }

            prescription.style.display = show ? 'block' : 'none';
            if (show) visibleCount++;
        });

        // Show message if no results
        const listDiv = document.getElementById('prescriptionsList');
        let noResultsMsg = document.getElementById('noResultsMsg');

        if (visibleCount === 0 && prescriptions.length > 0) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.id = 'noResultsMsg';
                noResultsMsg.className = 'text-center p-5';
                noResultsMsg.innerHTML = `
                    <i class="fas fa-search fa-4x mb-3" style="color: #e1e9f0;"></i>
                    <h5>No Matching Prescriptions</h5>
                    <p class="text-muted">Try adjusting your filters.</p>
                `;
                listDiv.appendChild(noResultsMsg);
            }
        } else if (noResultsMsg) {
            noResultsMsg.remove();
        }
    }, 300);
}
