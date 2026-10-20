# S.A.B Trader Business Website

A responsive, local-first cosmetics wholesale management website for S.A.B Trader. Business records stay in SQLite on the owner's computer. This delivery is scoped to the website; Windows installer and Android APK are out of scope.

## Current status

This is an in-progress website milestone with a working local API and UI for sign-in, admin/staff access, dashboard, products, stock adjustments, customers, customer ledger/payments, suppliers, purchases, sales, invoices, full sale cancellation/return and payment reversal, attendance, reports, settings, manual verified backups, and validated restore with a safety backup. Automatic scheduled backups, partial item returns, separate supplier payments, category/brand management, advanced analytics, a durable browser offline queue, automated tests and deployment hardening are not complete. Do not call the whole system production-complete yet.

## Technology and local data

- Python standard-library HTTP server and SQLite; no external packages or cloud database are required.
- Responsive HTML/CSS/JavaScript site, served from the same local origin as the JSON API.
- Default listener is `127.0.0.1:8765`; it accepts connections only from this computer. Do not expose it to the public internet.
- Windows database default: `%LOCALAPPDATA%\\SABTrader\\data\\sabtrader.sqlite`. Use `--db` to choose a development/test path.
- Passwords use PBKDF2-HMAC-SHA256 with per-password random salts. Auth sessions expire after 12 hours and can be revoked by logout. The first Admin is created from the command line. The user-requested bootstrap credential `admin` / `admin 111` is accepted only as a temporary first-run password and forces a password change before any business API access; the new password must be at least 12 characters.
- Prices are integer paisa (100 paisa = Rs. 1). Sale stock and ledger changes run in a SQLite transaction. Product stock changes are recorded in an append-only movement ledger.

## Run locally (Windows PowerShell)

From this repository folder:

```powershell
python .\scripts\sabtrader_web.py create-admin --username admin --name "Business Admin"
python .\scripts\sabtrader_web.py serve
```

Do not double-click `web\index.html`: the website must be opened through its local Python server so the stylesheet, login API, and SQLite database all use the correct origin. After login, Admin controls are in the **Admin panel** navigation item. Admin can create staff users, remove their access, and restore it. Product, customer, and supplier rows have Delete/Restore actions. A record with sales, purchase, stock, payment, or opening-balance history is archived instead of permanently erased so reports and ledgers remain intact. Sales and purchases use their reversal actions rather than destructive deletion.

The first command securely prompts for the Admin password. To use the requested bootstrap login, enter `admin 111` at that prompt. Sign in as `admin`; the app will require a new 12+ character password in Admin panel before business pages are available. Open `http://127.0.0.1:8765` in a browser. Press Ctrl+C in the server window to stop it. For a development database within the workspace, append `--db .\\work\\sabtrader-dev.sqlite` to both commands.

## Roles

Admin can manage catalog, stock, customers and their financial ledger, orders, staff accounts, developer support replies, attendance, settings, reports, and manual backups. Admin can update the Admin username/password, add staff, revoke or restore staff access, and delete unused product/customer/supplier records. Records with ledger, invoice, stock, opening-balance, or payment history are archived instead of erased. Staff can create support requests and open a WhatsApp message to WEB BY ZAINI. WhatsApp conversations do not sync into this local app automatically; an Admin must record the developer's response on the ticket for the solution to appear in the app. The API checks roles server-side; hiding a menu is not considered authorization.

## Sync and offline limits

This website writes directly to the local SQLite database while the computer and local server are running. A browser offline queue that survives closure/device restart and synchronizes after reconnection is not implemented yet. If the local computer is shut down or unreachable, this website cannot save authoritative business records. Remote access should use a properly secured VPN/reverse proxy design; public port forwarding is not supported.

## Receipts

The website renders a dedicated compact 80mm receipt template and invokes the browser's print dialog. It includes the configured company phone and `WEB BY ZAINI` / `03327021212` attribution by default. Preview layout has not been verified on a physical thermal printer; select the correct 80mm printer and paper size in its Windows driver.

## Backups

Admin can create a backup using SQLite's online backup API and an integrity check. Restore validates integrity/schema compatibility, creates a timestamped safety backup, atomically replaces the database and asks Admin to sign in again. Enter absolute `.sqlite` or `.db` paths in Backup & Restore. Automatic daily backups are not scheduled by the website. Keep another copy on an owner-controlled external drive. A backup on the same physical drive will not protect against that drive failing.

## Database tables

The initial migration defines users/sessions, settings, categories/brands/products, stock movements, customers/suppliers, sales/items, purchases/items, payments, attendance, idempotent sync operations, audit events, and migration history. Schema is versioned under `db/migrations/`; the Python migration runner applies files in order.

## Verification so far

- Python source compilation and JavaScript syntax checks passed.
- Fresh migration applied; repeat migration was idempotent. SQLite integrity and foreign-key checks passed.
- Local HTTP workflow checks passed for Admin and Staff sign-in, Admin-only routes, product/customer creation, an order with partial payment, duplicate order replay, stock deduction, invoice retrieval, payment reversal, sale cancellation with stock restoration, supplier purchase receipt/reversal, manual verified backup, and restore with a safety copy.
- The UI sign-in page loaded in the in-app browser. Login with a real business account has not been exercised in the browser. Physical 80mm printer output, Windows Task Scheduler, and multi-device/offline workflows remain unverified.

## Security boundaries and limitations

- The server binds to loopback by default. LAN use is not enabled by default and this basic HTTP server is not configured for TLS.
- A session bearer token is held in the browser tab's session storage; protect the computer's browser profile and lock the computer when unattended.
- Login failures are delayed but not persistently rate-limited yet.
- Staff cannot see purchase cost through the product API or access admin-only reports, backups, settings, staff, or customer financial ledgers.
- Browser local storage is not used as the business database.
- Scheduled backups, partial item returns, supplier payments after purchase, category/brand management, deeper reports, and persistent offline website sync still need implementation before production use.
