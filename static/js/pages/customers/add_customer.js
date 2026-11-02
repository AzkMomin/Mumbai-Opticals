const messageModal = new bootstrap.Modal(document.getElementById('messageModal'));

function toggleSubmenu(id) {
  const submenu = document.getElementById(id);
  submenu.classList.toggle('show');
}

function showMessageModal(type, title, message) {
  const modalHeader = document.getElementById('modalHeader');
  const modalIcon = document.getElementById('modalIcon');
  const modalTitle = document.getElementById('modalTitle');
  const modalMessage = document.getElementById('modalMessage');
  const modalButton = document.getElementById('modalButton');

  modalHeader.className = 'modal-header';

  switch(type) {
    case 'error':
      modalHeader.classList.add('error-header');
      modalIcon.className = 'fas fa-exclamation-triangle';
      modalTitle.textContent = title || 'Error';
      modalButton.className = 'btn-modal btn-modal-error';
      break;
    case 'success':
      modalHeader.classList.add('success-header');
      modalIcon.className = 'fas fa-check-circle';
      modalTitle.textContent = title || 'Success';
      modalButton.className = 'btn-modal btn-modal-success';
      break;
    default:
      modalHeader.classList.add('info-header');
      modalIcon.className = 'fas fa-info-circle';
      modalTitle.textContent = title || 'Information';
      modalButton.className = 'btn-modal';
  }

  modalMessage.textContent = message;
  messageModal.show();
}

// Initialize intl-tel-input
const phoneInput = document.querySelector("#phone");
let iti;

// Combined window.onload function
window.onload = function() {
  // Initialize phone input with country selector
  iti = window.intlTelInput(phoneInput, {
    utilsScript: "https://cdnjs.cloudflare.com/ajax/libs/intl-tel-input/17.0.8/js/utils.js",
    separateDialCode: true,
    initialCountry: "in", // Default to India
    preferredCountries: ["in", "us", "gb", "ae"],
    geoIpLookup: function(callback) {
      fetch('https://ipinfo.io/json?token=your_token_here')
        .then(response => response.json())
        .then(data => callback(data.country))
        .catch(() => callback('in'));
    }
  });

  // Set initial value if exists
  if (phoneInput.value) {
    iti.setNumber(phoneInput.value);
    document.getElementById('fullPhone').value = iti.getNumber();
  }

  // Handle existing flash messages
  const flashMessages = document.querySelectorAll('.flash-message');
  flashMessages.forEach(flash => {
    const category = flash.dataset.category;
    const message = flash.dataset.message;

    if (category === 'error') {
      showMessageModal('error', 'Error', message);
    } else if (category === 'success') {
      showMessageModal('success', 'Success', message);
    } else {
      showMessageModal('info', 'Information', message);
    }
  });
};

// Validate phone number on blur
phoneInput.addEventListener('blur', function() {
  const phoneError = document.getElementById('phoneError');
  if (iti.isValidNumber()) {
    phoneError.classList.add('d-none');
    document.getElementById('fullPhone').value = iti.getNumber();
  } else {
    phoneError.classList.remove('d-none');
  }
});

// Validate on keyup as well
phoneInput.addEventListener('keyup', function() {
  const phoneError = document.getElementById('phoneError');
  if (iti.isValidNumber()) {
    phoneError.classList.add('d-none');
    document.getElementById('fullPhone').value = iti.getNumber();
  }
});

// Update form submission to use full international number
document.querySelector('form').addEventListener('submit', function(e) {
  if (!iti.isValidNumber()) {
    e.preventDefault();
    showMessageModal('error', 'Invalid Phone', 'Please enter a valid phone number with country code');
  } else {
    // Set the full international number before submitting
    document.getElementById('fullPhone').value = iti.getNumber();
  }
});
