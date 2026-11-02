# Mumbai Opticals

Shop management app for Mumbai Opticals. Staff use it for customers, prescriptions,
products and stock, billing, and payments. Customers get a WhatsApp link to view
their bill.

Built with Flask and MySQL, hosted on PythonAnywhere.

## Project layout

```
flask_app.py              Entry point (PythonAnywhere's WSGI file imports `app` from here)
config.py                 Secrets: DB host/user/password, WEBHOOK_SECRET, ORDER_WHATSAPP (not in git)
requirements.txt

mumbai_opticals/          The application
  __init__.py             create_app(): settings, blueprints, error pages, security headers
  settings.py             Company details, upload folders, product fields, CDN versions
  db.py                   One DB connection per request; uncommitted work is rolled back
  auth.py                 Login checks, roles, password hashing
  security.py             CSRF protection for forms and fetch()
  schema.py               Adds new nullable columns the app needs (runs once per process)
  helpers.py              Uploads, pagination, stock movements, payment status
  images.py               Product photos: background removal and auto backdrop (Pillow only)
  routes/
    main.py               Dashboard (home page is served by shop.py)
    shop.py               Public shop: catalogue, product pages, reviews, questions, WhatsApp order links
    reviews.py            Staff: hide/delete reviews, answer customer questions
    auth.py               Login / logout
    users.py              Staff logins
    customers.py          Customers
    products.py           Products
    stock.py              Add stock, low stock, stock movement history
    bills.py              Bills (generate, view, edit, print, cancel, delete, WhatsApp)
    payments.py           Payments against bills
    prescriptions.py      Prescriptions
    portal.py             Customer-facing bill page (phone-number check)
    webhook.py            GitHub push -> PythonAnywhere auto-deploy

templates/
  layout/base.html        Shared page shell (head, Bootstrap, scripts); every page extends it
  layout/navbar.html      Sidebar
  <area>/*.html           One folder per area, matching routes/

static/
  css/layout.css          Sidebar styles
  css/pages/<area>/       One stylesheet per page
  js/app.js               Shared: adds CSRF token to forms/fetch, POST links (data-method="post")
  js/layout.js            Sidebar
  js/pages/<area>/        Page scripts
  Images/Logo/Logo.png
  uploads/                Product and prescription photos (not in git)
```

## How things work

- **Login**: passwords are stored as hashes. Old plain-text passwords are upgraded the
  next time that person logs in.
- **Deletes and cancels** only run as POST requests carrying the CSRF token. In
  templates, use `<a href="..." data-method="post" data-confirm="Are you sure?">`, or
  call `postTo(url)` from a script.
- **Stock** only changes through `helpers.change_stock()`, which also records the
  movement in `stock_transactions`.
- **Bill totals** are calculated on the server from the item rows. The browser's
  summary is only a preview.
- **Static files** are linked with `{{ asset('css/...') }}`. This adds a version number,
  so browsers fetch the new file after each deploy.

## Product photos

Each product can have up to 10 photos per upload (table `product_images`; `products.product_image`
always holds the main photo). On upload the background is removed when it is plain enough to separate
safely, and the product is placed on a soft backdrop chosen from its colour. The original is kept in
`originals/`, and staff can switch any photo back to the original on the Edit Product page.

## Deploying

Pushing to `main` deploys automatically. GitHub calls `/git-webhook`, which runs
`git pull` on PythonAnywhere and reloads the site. If `requirements.txt` changes, run
`pip install -r requirements.txt` in a PythonAnywhere console. The webhook doesn't
install packages.

## Running locally

```
pip install -r requirements.txt
# create config.py with HOST, USER, PASSWORD (and optionally DB_NAME, SECRET_KEY)
python flask_app.py
```
