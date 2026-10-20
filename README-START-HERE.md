# S.A.B Trader — Asal Website Source

Yeh static demo nahi hai. ZIP mein actual responsive website, Python local API, SQLite migration aur setup guide shamil hain. Business records backend mein save hote hain. Koi demo username ya password nahi.

## Windows par start karna

1. ZIP ko extract karein aur extracted project folder kholein.
2. Python 3 install karein.
3. PowerShell ko project folder mein open karein.
4. Pehli dafa Admin account banayein:

```powershell
python .\scripts\sabtrader_web.py create-admin --username admin --name "Business Admin"
```

Apna strong password prompt par dein (kam az kam 12 characters). Password source files mein save nahi hota.

5. Local website/backend start karein:

```powershell
python .\scripts\sabtrader_web.py serve
```

6. Browser mein `http://127.0.0.1:8765` kholein aur apne Admin credentials se login karein. PowerShell window chalta rehna chahiye. Website rokne ke liye PowerShell mein `Ctrl+C` dabayein.

`web\index.html` par double-click na karein. Website ko Python server se kholna zaroori hai, warna login API/database connect nahi honge. Is version mein CSS paths relative hain; browser mein server URL use karein.

## Admin panel aur delete controls

Admin login ke baad sidebar mein **Admin panel** kholein. Wahan se staff add kar sakte hain, access remove kar sakte hain aur baad mein restore kar sakte hain. Products, customers aur suppliers mein Delete/Restore controls hain. Jis record ki financial, stock ya transaction history ho, woh permanently erase hone ke bajaye archive hota hai taake purane invoices, balances aur reports mehfooz rahen. Sales/purchases ko delete karne ke bajaye Cancel/Return/Reverse actions istemal karein.

## Data location

SQLite database default tor par Windows ke `%LOCALAPPDATA%\SABTrader\data\sabtrader.sqlite` mein banti hai. Is database, backups, passwords ya customer information ko GitHub par upload na karein.

## GitHub par source rakhna

1. GitHub par private repository banayein.
2. ZIP extract karke tamam source files repository mein upload karein.
3. `.gitignore` database, backups aur local secrets ko exclude karta hai; phir bhi upload se pehle check karein ke koi customer data ya password shamil nahi.

GitHub Pages Python API/SQLite nahi chala sakta. GitHub source/version control ke liye hai, application ka backend Windows computer par chalta hai. Is backend ko public internet par seedha expose na karein.

## Included aur abhi baqi

Website milestone mein login, Admin/Staff permissions, dashboard, products/stock, customers/ledger, sales/invoices, suppliers/purchases, attendance, reports, settings, manual SQLite backup/restore aur record archive/delete controls shamil hain. Windows installer, Android APK/offline sync, scheduled backups, supplier payment ledger aur physical 80mm printer test abhi deliver nahi huay. `README.md` mein tamam known limitations aur prior verification notes hain.
