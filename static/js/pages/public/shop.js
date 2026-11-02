/* Shop page: category / type filters, search and sorting (all products are already on the page). */
(function () {
    'use strict';
    const grid = document.getElementById('productGrid');
    if (!grid) return;
    const tiles = Array.from(grid.querySelectorAll('.product-tile'));
    const search = document.getElementById('shopSearch');
    const sort = document.getElementById('shopSort');
    const empty = document.getElementById('emptyState');
    const state = { category: 'all', type: 'all', query: '' };

    function apply() {
        let shown = 0;
        tiles.forEach(tile => {
            const matchCat = state.category === 'all' || tile.dataset.category === state.category;
            const matchType = state.type === 'all' || tile.dataset.type === state.type;
            const matchQuery = !state.query || state.query.split(/\s+/).every(w => tile.dataset.search.includes(w));
            const visible = matchCat && matchType && matchQuery;
            tile.hidden = !visible;
            if (visible) shown++;
        });
        if (empty) empty.hidden = shown > 0 || tiles.length === 0;
    }

    document.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {
        document.querySelectorAll('.chip').forEach(c => c.classList.toggle('is-active', c === chip));
        const filter = chip.dataset.filter;
        state.category = filter === 'all' ? 'all' : filter.replace('cat-', '');
        state.type = 'all';
        document.querySelectorAll('.subfilters').forEach(row => {
            row.hidden = row.dataset.for !== filter;
            row.querySelectorAll('.subchip').forEach(s => s.classList.toggle('is-active', s.dataset.type === 'all'));
        });
        apply();
    }));

    document.querySelectorAll('.subchip').forEach(chip => chip.addEventListener('click', () => {
        chip.parentElement.querySelectorAll('.subchip').forEach(c => c.classList.toggle('is-active', c === chip));
        state.type = chip.dataset.type;
        apply();
    }));

    search.addEventListener('input', () => {
        state.query = search.value.trim().toLowerCase();
        apply();
    });

    const original = tiles.slice();
    sort.addEventListener('change', () => {
        let ordered = original.slice();
        if (sort.value !== 'new') {
            const dir = sort.value === 'low' ? 1 : -1;
            ordered.sort((a, b) => dir * (parseFloat(a.dataset.price) - parseFloat(b.dataset.price)));
        }
        ordered.forEach(tile => grid.appendChild(tile));
    });
})();
