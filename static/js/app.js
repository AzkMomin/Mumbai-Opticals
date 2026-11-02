/* Shared page behaviour: CSRF protection for forms and fetch, and POST action links. */
(function () {
    'use strict';
    var meta = document.querySelector('meta[name="csrf-token"]');
    var token = meta ? meta.getAttribute('content') : '';

    function addToken(form) {
        if (!token || (form.method || '').toLowerCase() !== 'post') return;
        if (form.querySelector('input[name="csrf_token"]')) return;
        var input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrf_token';
        input.value = token;
        form.appendChild(input);
    }

    // Every POST form gets the token, including forms built later by page scripts
    document.addEventListener('submit', function (e) { addToken(e.target); }, true);
    var nativeSubmit = HTMLFormElement.prototype.submit;
    HTMLFormElement.prototype.submit = function () { addToken(this); return nativeSubmit.call(this); };

    // fetch() calls that change data send the token as a header
    if (window.fetch) {
        var nativeFetch = window.fetch;
        window.fetch = function (input, init) {
            init = init || {};
            var method = (init.method || 'GET').toUpperCase();
            if (method !== 'GET' && method !== 'HEAD' && token) {
                var headers = new Headers(init.headers || {});
                headers.set('X-CSRFToken', token);
                init.headers = headers;
            }
            return nativeFetch.call(this, input, init);
        };
    }

    // Links marked data-method="post" (delete/cancel) are sent as a POST form
    document.addEventListener('click', function (e) {
        var link = e.target.closest && e.target.closest('a[data-method="post"]');
        if (!link || e.defaultPrevented) return;
        e.preventDefault();
        var message = link.getAttribute('data-confirm');
        if (message && !window.confirm(message)) return;
        var form = document.createElement('form');
        form.method = 'post';
        form.action = link.getAttribute('href');
        form.style.display = 'none';
        document.body.appendChild(form);
        form.submit();
    });

    // Close success/info notices automatically after a few seconds
    setTimeout(function () {
        document.querySelectorAll('.flash-stack .alert-success, .flash-stack .alert-info').forEach(function (el) {
            if (window.bootstrap && bootstrap.Alert) bootstrap.Alert.getOrCreateInstance(el).close();
            else el.remove();
        });
    }, 6000);

    // Navigation helpers used by page scripts: postTo('/bills/delete/5')
    window.postTo = function (url) {
        var form = document.createElement('form');
        form.method = 'post';
        form.action = url;
        form.style.display = 'none';
        document.body.appendChild(form);
        form.submit();
    };
})();
