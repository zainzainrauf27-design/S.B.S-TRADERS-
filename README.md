# S.A.B Trader — GitHub Pages demo

This is a static, browser-only preview of the cosmetics wholesale management website. It has no server, database, secure login, or synchronization between devices. Sample edits are saved in this browser's localStorage. Do not enter real shop, customer, supplier, staff, or financial information.

## Demo sign-in

- Admin: `admin` / `Demo-Admin-2026!`
- Staff: `staff` / `Demo-Staff-2026!`

These are public demo credentials and are not security controls. The staff view has limited navigation, but a static public website must never be used to protect sensitive business data.

## Publish on GitHub Pages

1. Create a GitHub repository.
2. Upload all five files in this folder to the repository root: `index.html`, `app.js`, `styles.css`, `favicon.svg`, and `README.md`.
3. In the repository, open **Settings → Pages**.
4. Under **Build and deployment**, select **Deploy from a branch**, choose your default branch and **/(root)**, then save.
5. Open the published Pages URL shown in that settings page.

The asset links are relative, so the site works from a repository Pages URL such as `https://username.github.io/repository/`.

## What the preview demonstrates

- Dashboard, cosmetics product catalog, customer and supplier lists
- Sample inventory adjustments, sales orders, invoices, customer payment entries
- Supplier purchases, staff view, attendance view, settings and demo-data export/reset
- Browser-only persistence for edits in the same browser profile

Some workflows are preview-only. GitHub Pages cannot run the included SQLite/Python backend. This package is not the full production deployment from the original business requirements. For live multi-user use, deploy the Python/SQLite application on a private server or replace the backend with an authenticated hosted API and database before entering real data.
