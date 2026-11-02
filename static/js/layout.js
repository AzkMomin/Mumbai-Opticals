/* Sidebar navigation */
function toggleSubmenu(id) {
    const submenu = document.getElementById(id);
    submenu.classList.toggle('show');
}

// Close submenus when clicking outside
document.addEventListener('click', function(event) {
    if (!event.target.closest('.menu-item') && !event.target.closest('.submenu')) {
        document.querySelectorAll('.submenu.show').forEach(submenu => {
            submenu.classList.remove('show');
        });
    }
});
