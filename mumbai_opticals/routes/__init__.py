from . import auth, bills, customers, main, payments, portal, prescriptions, products, shop, stock, users, webhook

BLUEPRINTS = [
    main.bp, auth.bp, users.bp, customers.bp, products.bp, stock.bp,
    bills.bp, payments.bp, prescriptions.bp, portal.bp, shop.bp, webhook.bp,
]
