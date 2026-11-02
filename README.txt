ZeQube Vendor App - PC-hosted, phone-accessible local app

START
1. Extract the complete ZeQubeVendorApp folder from the ZIP onto a Windows PC.
2. Double-click Start_ZeQube_Vendor_App.bat.
3. If Windows Firewall asks, allow access on Private networks only.
4. The window shows a PC link, phone/LAN link, and an access code. Keep the window open.
5. On a phone connected to the same trusted Wi-Fi, open the phone/LAN link and enter the code shown on the PC.
6. Bookmark the page or use the browser menu to add a shortcut to the phone home screen.

The app is responsive for phones. The database is stored in data\vendors.db on the PC. Added and edited vendor records are saved there and shared with browsers connected to that PC. The server must remain running, and the PC must stay on the same Wi-Fi. Press Ctrl+C in the PC window to stop it.

DATA AND BACKUPS
- Use Export Excel CSV in the app to download a spreadsheet that opens in Excel.
- To back up the database, stop the app and copy data\vendors.db to a safe location.
- The starter database is created from the 166 vendor records in vendors_seed.json the first time the app runs.

NETWORK AND ACCESS
- This version works only on the same local Wi-Fi/LAN. It is not reachable from outside the network.
- Use it only on a trusted private network. The local connection uses HTTP, so do not use a public/guest Wi-Fi for sensitive GSTIN and contact details.
- Do not forward port 8765 to the internet. For access outside the office/home network, use a secured HTTPS host with sign-in instead.
- The access code changes each time the app starts. Share the current code only with people who should use the directory.

TROUBLESHOOTING
- If the PC link opens but the phone link does not, check that both devices are on the same Wi-Fi and that Windows Firewall allowed Private network access.
- If no phone link appears in the window, run ipconfig on the PC and use its IPv4 Address as http://<IPv4-address>:8765.
- Do not delete data\vendors.db if you want to keep edits.
