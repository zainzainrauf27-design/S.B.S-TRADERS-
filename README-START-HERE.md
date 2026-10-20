# S.A.B Trader — Asal Website Source

Yeh static demo nahi hai. Is package mein asal responsive website, Python local API, SQLite database migration aur setup guide shamil hain. Login aur business records backend se chalte hain; koi demo username/password source mein set nahi.

## Windows par chalane ka tareeqa

1. Python 3 install karein.
2. PowerShell mein is project folder par aayein.
3. Pehli dafa Admin account banayein:

```powershell
python .\scripts\sabtrader_web.py create-admin --username admin --name "Business Admin"
```

Password prompt par apna strong password dein (kam az kam 12 characters). Password source ya GitHub par save nahi hota.

4. Website/backend start karein:

```powershell
python .\scripts\sabtrader_web.py serve
```

5. Isi computer ke browser mein `http://127.0.0.1:8765` kholein aur apne Admin credentials se login karein. Server band karne ke liye PowerShell mein `Ctrl+C` dabayein.

Database default tor par Windows ke `%LOCALAPPDATA%\SABTrader\data\sabtrader.sqlite` mein banti hai. Is folder ko GitHub par upload na karein.

## GitHub par source rakhna

1. GitHub par **private repository** banayein.
2. ZIP extract karke is folder ke tamam source files repository mein upload karein.
3. `data/`, `.sqlite`, backup files, passwords ya customer records kabhi upload na karein. `.gitignore` database aur secret files ko exclude karta hai.

GitHub Pages is application ko production website ke tor par nahi chala sakta, kyun ke Pages Python API ya SQLite database run nahi karta. Is project mein backend Windows computer par chalta hai aur data wahi rehta hai. GitHub source/version control ke liye hai. Isay public internet ya hosting par expose na karein.

## Included features aur hadain

Login, Admin/Staff permissions, dashboard, product/stock, customers/ledger, sales/invoices, supplier purchases, attendance, reports, settings aur manual SQLite backup/restore ka implemented web milestone shamil hai. Existing test notes aur baqi planned kaam `README.md` mein diye gaye hain. Windows installer, Android APK, persistent Android offline queue/sync, scheduled backups aur physical 80mm printer test is ZIP mein deliver nahi kiye gaye; inhein complete kehna durust nahi hoga.
