// Check if there's an error message from Flask
document.addEventListener('DOMContentLoaded', function() {
  const errorInput = document.getElementById('errorMessage');
  if (errorInput) {
    const errorMessage = errorInput.value;
    document.getElementById('errorModalMessage').textContent = errorMessage;

    // Show the modal
    const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
    errorModal.show();
  }
});

// Optional: Form validation before submit
document.getElementById('loginForm').addEventListener('submit', function(e) {
  const email = document.getElementById('email').value;
  const password = document.getElementById('password').value;

  if (!email || !password) {
    e.preventDefault();
    document.getElementById('errorModalMessage').textContent = 'Please fill in both email and password fields.';
    const errorModal = new bootstrap.Modal(document.getElementById('errorModal'));
    errorModal.show();
  }
});
