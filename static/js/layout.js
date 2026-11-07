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

// ---------- Phones and tablets: sidebar slides in from the left ----------
(function () {
    const sidebar = document.getElementById('sidebar');
    const toggle = document.getElementById('sidebarToggle');
    const closeBtn = document.getElementById('sidebarClose');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar || !toggle) return;

    function setOpen(open) {
        document.body.classList.toggle('sidebar-open', open);
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        backdrop.hidden = !open;
        if (open) sidebar.querySelector('.menu-item, a')?.focus?.();
    }
    toggle.addEventListener('click', () => setOpen(!document.body.classList.contains('sidebar-open')));
    closeBtn.addEventListener('click', () => setOpen(false));
    backdrop.addEventListener('click', () => setOpen(false));
    document.addEventListener('keydown', e => { if (e.key === 'Escape') setOpen(false); });
    window.matchMedia('(min-width: 992px)').addEventListener('change', e => { if (e.matches) setOpen(false); });

    // Keep the open submenu (current section) visible when the menu opens
    sidebar.querySelectorAll('.submenu-item.active, .menu-item.active').forEach(el => {
        const sub = el.closest('.submenu'); if (sub) sub.classList.add('show');
    });
})();

// ---------- Wide tables scroll sideways instead of breaking the page ----------
document.querySelectorAll('.main-content table').forEach(table => {
    const parent = table.parentElement;
    const scrolls = el => /(auto|scroll)/.test(getComputedStyle(el).overflowX);
    if (parent.classList.contains('table-responsive') || scrolls(parent)) return;
    const wrap = document.createElement('div');
    wrap.className = 'table-scroll';
    parent.insertBefore(wrap, table);
    wrap.appendChild(table);
});
