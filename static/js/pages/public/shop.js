/* Public shop: photo galleries, catalogue filters/search/sort, product page reviews and rows. */
(function () {
    'use strict';

    // ---------------- photo galleries (cards and product page) ----------------
    function setupGallery(gallery) {
        const images = Array.from(gallery.querySelectorAll('.gallery__img'));
        if (images.length < 2) return;
        const dots = Array.from(gallery.querySelectorAll('.gallery__dots span'));
        const counter = gallery.querySelector('[data-current]');
        const thumbs = gallery.closest('.detail__gallery')
            ? Array.from(gallery.closest('.detail__gallery').querySelectorAll('.thumbs__item')) : [];
        let index = 0;

        function show(next) {
            index = (next + images.length) % images.length;
            images.forEach((img, i) => img.classList.toggle('is-active', i === index));
            dots.forEach((dot, i) => dot.classList.toggle('is-active', i === index));
            thumbs.forEach((t, i) => t.classList.toggle('is-active', i === index));
            if (counter) counter.textContent = index + 1;
            images[index].loading = 'eager';
        }

        gallery.querySelectorAll('.gallery__arrow').forEach(btn => btn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            show(index + parseInt(btn.dataset.step, 10));
        }));
        thumbs.forEach((t, i) => t.addEventListener('click', () => show(i)));

        // Swipe on touch screens
        let startX = null;
        gallery.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') startX = e.clientX; });
        gallery.addEventListener('pointerup', e => {
            if (startX === null) return;
            const dx = e.clientX - startX;
            startX = null;
            if (Math.abs(dx) > 35) show(index + (dx < 0 ? 1 : -1));
        });

        // Keyboard on the product page gallery
        if (gallery.classList.contains('gallery--large')) {
            document.addEventListener('keydown', e => {
                if (e.target.closest('input, textarea, select')) return;
                if (e.key === 'ArrowRight') show(index + 1);
                if (e.key === 'ArrowLeft') show(index - 1);
            });
        }
    }
    document.querySelectorAll('[data-gallery]').forEach(setupGallery);

    // ---------------- catalogue (home page): one section per product type ----------------
    const sections = Array.from(document.querySelectorAll('.type-section'));
    const search = document.getElementById('shopSearch');
    const sort = document.getElementById('shopSort');
    if (sections.length && search) {
        const empty = document.getElementById('emptyState');
        const grids = sections.map(section => {
            const grid = section.querySelector('.grid');
            return { section, grid, tiles: Array.from(grid.querySelectorAll('.product-tile')) };
        });

        search.addEventListener('input', () => {
            const words = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
            let shown = 0;
            grids.forEach(({ section, tiles }) => {
                let inSection = 0;
                tiles.forEach(tile => {
                    const visible = words.every(w => tile.dataset.search.includes(w));
                    tile.hidden = !visible;
                    if (visible) inSection++;
                });
                section.hidden = inSection === 0;
                shown += inSection;
            });
            if (empty) empty.hidden = shown > 0;
        });

        sort.addEventListener('change', () => {
            const num = (tile, key) => parseFloat(tile.dataset[key]) || 0;
            grids.forEach(({ grid, tiles }) => {
                const ordered = tiles.slice();
                if (sort.value === 'low') ordered.sort((a, b) => num(a, 'price') - num(b, 'price'));
                if (sort.value === 'high') ordered.sort((a, b) => num(b, 'price') - num(a, 'price'));
                if (sort.value === 'rating') ordered.sort((a, b) => num(b, 'rating') - num(a, 'rating'));
                ordered.forEach(tile => grid.appendChild(tile));
            });
        });
    }

    // ---------------- product page ----------------
    document.querySelectorAll('[data-toggle-form]').forEach(btn => btn.addEventListener('click', () => {
        const form = document.getElementById(btn.dataset.toggleForm);
        if (!form) return;
        form.hidden = !form.hidden;
        if (!form.hidden) {
            form.scrollIntoView({ behavior: 'smooth', block: 'center' });
            const first = form.querySelector('input:not([type=hidden]):not([tabindex="-1"]), textarea');
            if (first) setTimeout(() => first.focus({ preventScroll: true }), 300);
        }
    }));

    const reviews = Array.from(document.querySelectorAll('.review'));
    const more = document.getElementById('moreReviews');
    const note = document.getElementById('reviewFilterNote');
    if (more) more.addEventListener('click', () => {
        reviews.forEach(r => { r.hidden = false; });
        more.remove();
    });
    document.querySelectorAll('[data-filter-stars]').forEach(row => row.addEventListener('click', () => {
        const stars = row.dataset.filterStars;
        const active = row.classList.toggle('is-active');
        document.querySelectorAll('[data-filter-stars]').forEach(r => { if (r !== row) r.classList.remove('is-active'); });
        reviews.forEach(r => { r.hidden = active ? r.dataset.stars !== stars : r.classList.contains('is-extra') && !!more && document.body.contains(more); });
        if (note) {
            note.hidden = !active;
            note.textContent = active ? `Showing ${stars}-star reviews` : '';
        }
        document.getElementById('reviews').scrollIntoView({ behavior: 'smooth' });
    }));

    document.querySelectorAll('.rec-row').forEach(row => {
        const track = row.querySelector('.rec-row__track');
        row.querySelectorAll('[data-scroll]').forEach(btn => btn.addEventListener('click', () => {
            track.scrollBy({ left: parseInt(btn.dataset.scroll, 10) * track.clientWidth * 0.85 });
        }));
    });
})();
