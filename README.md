# S.A.B Trader

Local-first cosmetics wholesale and supply management for S.A.B Trader. The current build is a Node.js web application backed by SQLite. It has no cloud dependency, seeded demo data, default passwords, or included business records.

## Current capabilities

- Admin and Staff sign-in, first Admin setup, forced password changes for new/reset Staff accounts, session expiry, role checks, and sign-in throttling.
- Product catalog, category and brand management, product history, inventory adjustments, active/archive state, and stock ledger.
- Customer records, duplicate-phone confirmation, customer statements, invoice balances, and customer payment posting/reversal.
- Sales orders, invoice numbering, partial/full payment, stock deduction, discounts for Admin, historical price/cost snapshots, receipt preview/printing, and order history.
- Supplier records, purchase receiving, supplier payments and balances, and controlled purchase reversal.
- Daily Staff check-in/out with duplicate prevention and date-range attendance.
- Admin dashboard and reports by date range, product/brand/category, Staff, and attendance; report CSV export.
- SQLite integrity checks, manual backup, validated restore with a pre-restore safety backup, and a Windows daily backup task helper.
- Responsive web UI served from the local application; server binds to `127.0.0.1` only.
- Android offline companion with SQLCipher-encrypted local storage for catalog/customer entries, queued customer creation, orders, and attendance. The Android app supports Admin-issued one-time pairing, pinned HTTPS, catalog bootstrap, queue sync, and device revocation.

A signed-in Admin can create pairing codes from Staff accounts once LAN sync is initialized. Android trust is pinned to the SHA-256 fingerprint shown by the Windows server; queued records are retained if the server rejects them. A Windows installer and physical printer validation are still outstanding. See “Device and deployment status.”

## Requirements and run

Install Node.js 24.15 or newer. The Windows/local web server uses Node's built-in `node:sqlite` and runs without third-party server packages. The Android build uses the packages recorded in `package-lock.json`.

```powershell
npm test
npm start
```

Open `http://127.0.0.1:4317`. Set `SAB_PORT` to change the port and `SAB_DATA_DIR` to choose the persistent database directory. Production defaults are `%LOCALAPPDATA%\SABTrader\data\sab-trader.sqlite3` on Windows and `$XDG_DATA_HOME/sab-trader/sab-trader.sqlite3` (or `~/.local/share/sab-trader/sab-trader.sqlite3`) on Linux/macOS.

On first launch the console prints a one-time setup token. Use the web setup screen to create the owner Admin account. This token is not a password and is invalidated after setup.

## GitHub Pages information site

The static project overview is in `docs/`. To publish it, push the project to your GitHub repository, then open **Settings → Pages** and choose **Deploy from a branch**, your default branch, and `/docs`. GitHub Pages presents project information only; the live sales, inventory, customer, and staff workflows require the local Windows server. Never publish production database files, backups, credentials, pairing codes, certificates, or customer records. The business and developer contact numbers shown on the site were provided for this project and will be visible publicly if you publish the site.

## Backups

Use **Backups & restore** while signed in as Admin to create a database backup or restore a listed backup. Restore validates the selected SQLite file and creates a safety backup first. Backups are stored separately from the database under the application data directory. The CLI command `npm run backup` creates and verifies a backup and prunes backups past configured retention. `SAB_DATA_DIR` may be set for both application and CLI.

On Windows, register the daily 2:00 AM task from an elevated PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Register-DailyBackupTask.ps1
```

Use `-Remove` to unregister it; `-WhatIf` previews changes.

## Android debug build

With Android Studio's SDK installed and JDK 21 available at `C:\Users\DREAM\.jdks\jbr-21.0.11`, build a debug APK with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Build-Android.ps1
```

The command places the APK at `android\app\build\outputs\apk\debug\app-debug.apk`. `outputs\SAB-Trader-Android-debug.apk` is a debug-signed installable build, not a release-store artifact. The Android database key is held by the SQLite plugin's Android encrypted preferences.

## Windows and Android LAN sync

Run `scripts\Initialize-LanSync.ps1` once in the Windows account that will run the business server. It creates a self-signed certificate and keeps its PFX passphrase DPAPI-protected for that account under `%LOCALAPPDATA%\SABTrader\sync`. Start the server with `scripts\Start-LocalServer.ps1`; leave its console open. The sync listener uses port 4318 on the LAN and accepts only `/api/sync/*`; the web app remains on local port 4317. Allow Node.js on a **Private** Windows network when Windows Firewall asks. Do not forward the port on the router. Copy the printed SHA-256 fingerprint into the Android app. In Admin → Staff accounts, create a one-use pairing code for an active Staff account that has completed password setup, then enter the sync URL, fingerprint, and code on Android.

## Data and security notes

- Money is stored as integer Pakistani paisa. Quantities use integer thousandths.
- Completed sales and purchases preserve item and price/cost snapshots. Stock changes are ledger entries; reversals add compensating entries.
- The business web server uses `127.0.0.1`; the separate optional Android listener is encrypted and device-token protected. Device certificates are manually pinned. Keep the Android app installed until its queue is synced or securely exported.
- Use strong unique passwords. The application does not contain or print a reusable default credential.
- Keep the database, backups, secrets, and customer records out of source control and shared folders.

## Device and deployment status

The desktop browser interface and local API are implemented, but there is no packaged Windows installer yet. LAN sync now has code and setup scripts, but must still be exercised on the owner's Windows LAN and Android phone before production use. The receipt has an 80 mm print layout with a 58 mm option, but it has not been verified on a physical printer.

Business defaults include S.A.B Trader and phone `03336447526`, PKR, `Asia/Karachi`, invoice and purchase number prefixes, and the requested optional receipt footer. Change configurable business details in **Business settings** before live use.
