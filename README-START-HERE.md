# S.A.B Trader — Website, Admin aur Developer Support

Yeh real local website hai, static demo nahi. Website ke saath Python API aur SQLite database shamil hain.

## First run: tumhara Admin login

1. ZIP extract karo aur project folder kholo.
2. Python 3 install karo.
3. Project folder mein PowerShell khol kar yeh chalao:

```powershell
python .\scripts\sabtrader_web.py create-admin --username admin --name "Business Admin"
```

Password prompt par `admin 111` type karo. Yeh sirf temporary first-run password hai. Pehli login par **Admin panel** mein foran naya password set karna zaroori hoga; naya password kam az kam 12 characters ka ho.

Phir server chalao:

```powershell
python .\scripts\sabtrader_web.py serve
```

Browser mein `http://127.0.0.1:8765` kholo. PowerShell window website chalne tak khuli rehni chahiye. Server rokne ke liye `Ctrl+C` dabao. `web\index.html` par double-click na karo; us se API/database login kaam nahi karega.

## Admin panel

Admin login ke baad sidebar mein **Admin panel** kholo. Yahan Admin username/password badal sakte ho, staff add kar sakte ho, aur staff access remove/restore kar sakte ho. Staff ka access remove hote hi uske active sessions band ho jate hain. Product, customer aur supplier rows mein Delete/Restore controls hain. Jis record ka transaction, balance, payment ya stock history ho, woh archive hoga taake purana hisaab mehfooz rahe. Sales/purchases mein cancel, return ya reverse controls istemal karo.

## Developer support

Admin aur Staff dono **Developer support** se complaint, technical issue, account help ya feature request save kar sakte hain. Ticket ke WhatsApp button se WEB BY ZAINI ko pre-filled request bheji ja sakti hai. WhatsApp agent ka response is local app mein automatic receive nahi ho sakta jab tak WhatsApp Business API/webhook configure na ho. Response milne ke baad Admin ticket par **Add solution** se jawab aur status save kar sakta hai; woh solution user ko ticket details mein nazar aayega.

## Data aur GitHub

SQLite file `%LOCALAPPDATA%\SABTrader\data\sabtrader.sqlite` mein rehti hai. GitHub Pages Python API/SQLite nahi chala sakta. GitHub ko private source repository ke liye use karo; database, backups, passwords aur customer data repository mein kabhi upload na karo.

Windows installer, Android APK/offline sync, scheduled backups aur physical 80mm printer test abhi is website ZIP mein nahi hain. Zyada tafseel, purane workflow verification notes aur known limitations `README.md` mein hain.
