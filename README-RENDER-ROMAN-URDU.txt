S.A.B TRADER — GITHUB + RENDER QUICK GUIDE (Roman Urdu)

Maqsad
GitHub repo mein app ka source rakhna hai. Render par Python backend ke saath web app chalani hai. GitHub Pages ka URL alag rahega; rozmarra istemal ke liye Render ka URL kholna hai kyun ke wahi API aur database se connected hoga.

ZIP MEIN KYA HAI
- scripts/: Python API/server aur database migration tool
- db/migrations/: database ka schema
- web/: website ke HTML/CSS/JavaScript files
- README.md aur .gitignore

PART 1 — ZIP ko apne GitHub repository mein dalna
1. Is ZIP ko download karke Extract All karein.
2. GitHub Desktop install karein: https://desktop.github.com/
3. GitHub Desktop khol kar File > Clone repository > URL chunein.
4. Repository URL paste karein: https://github.com/zainzainrauf27-design/S.B.S-TRADERS-
5. Local folder location chunein aur Clone dabayein. Is qadam se sirf code ki working copy PC par aati hai; website ka database aapke PC par automatically nahi banega.
6. Extract ki hui ZIP mein se `db`, `scripts`, `web`, `.gitignore`, `README.md` ko cloned repository folder mein copy karein. Existing same-name files ke liye Replace chunein. `work`, `outputs`, `.sqlite`, `.db`, customer records ya backups upload na karein.
7. GitHub Desktop mein changes nazar aayenge. Summary mein `Add Render deployment files` likhein, Commit to main dabayein, phir Push origin dabayein.
8. Browser mein repository khol kar dekhein ke `db`, `scripts`, `web` folders aur unke files aa gaye hain.

Agar GitHub Desktop install nahi karna:
GitHub repo > Add file > Upload files khol kar ZIP extract karne ke baad `db`, `scripts`, `web` folders aur `.gitignore` upload karne honge. ZIP file ko seedha GitHub par upload karne se GitHub usay extract nahi karta. Folder upload browser ke mutabiq mushkil ho sakta hai, is liye GitHub Desktop aasaan hai.

PART 2 — Render par web service banana
1. https://render.com/ par Sign Up karein. GitHub ke saath continue kar sakte hain.
2. Render dashboard mein New + > Web Service chunein.
3. GitHub account connect/authorize karein aur `S.B.S-TRADERS-` repository select karein.
4. Settings:
   - Name: sab-trader (ya koi available naam)
   - Branch: main
   - Root Directory: khaali chhorein
   - Runtime: Python 3
   - Build Command: `python --version`
   - Start Command: `python scripts/sabtrader_web.py serve --host 0.0.0.0 --port $PORT --db /var/data/sabtrader.sqlite`
5. Advanced section mein Health Check Path ho to `/api/health` likhein.
6. Environment Variables mein yeh values add karein:
   - `SAB_DB_PATH` = `/var/data/sabtrader.sqlite`
   - `SAB_ADMIN_USERNAME` = `admin`
   - `SAB_ADMIN_NAME` = `Business Admin`
   - `SAB_ADMIN_PASSWORD` = `admin 111`
     Isay Secret/Hidden value ke tor par save karein. Password repo, chat, screenshot ya public jagah par na likhein. Pehli login par system foran naya password set karne ko kahega; naya password kam az kam 12 characters ka rakhein.
7. Persistent Disk lagayein: Advanced > Disk > Add Disk; Mount Path `/var/data`; Size kam az kam 1 GB. Disk ke baghair deploy/restart ke baad SQLite data kho sakta hai.
8. Create Web Service dabayein. Deploy successful hone tak intezar karein. Render URL `https://...onrender.com` dega. Isi Render URL ko khol kar login karein; GitHub Pages wala URL abhi API login nahi chalayega.\n9. Pehli dafa Admin login karke naya password set karne ke baad Render > Environment mein se `SAB_ADMIN_USERNAME`, `SAB_ADMIN_NAME`, `SAB_ADMIN_PASSWORD` hata dein aur save/redeploy karein. `SAB_DB_PATH` ko rehne dein. Admin account database mein bana rahega; bootstrap password environment mein rakhne ki zaroorat nahi.
9. Login ke baad pehli cheez Admin password change karein. Phir `Business settings` mein business details set karein.

PART 3 — Rozana istemal aur Sunday ko local software par shift
- Roz Render ke Render URL se website kholein.
- Admin panel mein users/staff set karein.
- Admin ke Backup & Restore se regular SQLite backup banayein aur apne PC par download/store karein. Customer/business database ko GitHub repository mein upload na karein.
- Sunday local shift se pehle aakhri backup lein aur PC wali local app mein restore karke records verify karein. Verification ke baad hi Render service band/delete karein.
- Android app ke liye SQLite backup ko seedha APK mein copy karna conversion nahi hota; Android import/restore feature aur device-specific storage alag se implement/verify karna hoga. PC aur Android mein automatic shared data ke liye sync bhi alag feature hai.

COST / DATA
Render ki free web service persistent disk attach nahi kar sakti. Is app ke SQLite records preserve karne ke liye paid web service + persistent disk darkar ho sakti hai. Current rates aur billing Render ki official pricing par check karein: https://render.com/pricing . Disk details: https://render.com/docs/disks . Render filesystem bina persistent disk ke ephemeral hoti hai: https://render.com/docs/web-services . Koi paid plan select karne se pehle price dashboard par dekh lein.

IMPORTANT
- Render par yeh package frontend + backend ko ek hi origin par serve karta hai; GitHub Pages ka alag URL sirf static copy hai aur login API us par nahi chalegi.
- Admin password, database file ya backup ko GitHub par kabhi upload na karein.
- Render dashboard account mein 2-step verification lagana behtar hai.
- Yeh package Sunday ke PC/Android conversion ko khud se nahi karta; us ke liye baad mein local PC build, Android app aur verified data import/restore ka kaam karna hoga.

