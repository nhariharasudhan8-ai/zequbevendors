import csv
import html
import io
import json
import secrets
import socket
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "vendors.db"
SEED_PATH = ROOT / "vendors_seed.json"
PORT = 8765
ACCESS_CODE = secrets.token_urlsafe(8)
SESSIONS = set()
SESSION_LOCK = threading.Lock()
CAPABILITIES = [
    "3D printing", "3D printing materials", "CNC machining", "CNC components",
    "CNC tools / accessories", "VMC machining", "Sheet metal fabrication",
    "Laser cutting", "Spring manufacturing", "Embedded systems",
    "PCB fabrication / assembly", "Electronics manufacturing", "Electronics components",
    "Fabrication / welding", "Welding consumables", "Tooling / jigs / fixtures",
    "Gauges / special machines", "Metal / raw material supply", "Industrial materials",
    "Plastic products manufacturing", "Power tools / equipment supply", "Printing / labels",
    "Design / engineering", "Material supplier", "Other"
]


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect_db() as con:
        con.execute("CREATE TABLE IF NOT EXISTS vendors (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
        count = con.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
        if count == 0 and SEED_PATH.exists():
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            now = datetime.now(timezone.utc).isoformat()
            con.executemany(
                "INSERT INTO vendors (id, payload, updated_at) VALUES (?, ?, ?)",
                [(v["id"], json.dumps(v, ensure_ascii=False), now) for v in seed]
            )
            print(f"Loaded {len(seed)} starter vendor records into {DB_PATH}")


def all_vendors():
    with connect_db() as con:
        return [json.loads(row["payload"]) for row in con.execute("SELECT payload FROM vendors ORDER BY rowid")]


def clean_record(record, old=None):
    item = dict(old or {})
    item.update(record)
    item["id"] = str(item.get("id") or ("NEW-" + uuid.uuid4().hex[:10].upper()))
    item["vendorNo"] = str(item.get("vendorNo") or item["id"]).strip()
    item["name"] = str(item.get("name") or "").strip()
    item["gstin"] = str(item.get("gstin") or "").strip().upper()
    item["address"] = str(item.get("address") or "").strip()
    if not item["name"] or not item["gstin"] or not item["address"]:
        raise ValueError("Company name, GSTIN, and address are required.")
    caps = item.get("capabilities") or []
    if isinstance(caps, str):
        caps = [c.strip() for c in caps.split(";") if c.strip()]
    item["capabilities"] = list(dict.fromkeys(str(c).strip() for c in caps if str(c).strip()))
    for key in ("supplierType", "contact", "phone", "email", "website", "notes",
                "addressSourceUrl", "addressSourceLabel", "capabilitySourceUrl", "capabilitySourceLabel"):
        item[key] = str(item.get(key) or "").strip()
    if not item.get("mapUrl") or (old and item.get("address") != old.get("address")):
        from urllib.parse import quote_plus
        item["mapUrl"] = "https://www.google.com/maps/search/?api=1&query=" + quote_plus(item["address"])
    return item


def save_record(item, is_new=False):
    now = datetime.now(timezone.utc).isoformat()
    with connect_db() as con:
        if is_new:
            con.execute("INSERT INTO vendors (id, payload, updated_at) VALUES (?, ?, ?)",
                        (item["id"], json.dumps(item, ensure_ascii=False), now))
        else:
            con.execute("UPDATE vendors SET payload = ?, updated_at = ? WHERE id = ?",
                        (json.dumps(item, ensure_ascii=False), now, item["id"]))


class Handler(BaseHTTPRequestHandler):
    server_version = "ZeQubeLocalApp/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_bytes(self, status, body, content_type="application/json; charset=utf-8", extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value, extra_headers=None):
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), extra_headers=extra_headers)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 200_000:
            raise ValueError("Request is too large.")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def session_id(self):
        for part in self.headers.get("Cookie", "").split(";"):
            name, sep, value = part.strip().partition("=")
            if sep and name == "zq_session":
                return value
        return ""

    def authorized(self):
        sid = self.session_id()
        with SESSION_LOCK:
            return bool(sid and sid in SESSIONS)

    def require_auth(self):
        if not self.authorized():
            self.send_json(401, {"error": "Sign in with the access code shown on the PC."})
            return False
        return True

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            try:
                body = (ROOT / "index.html").read_bytes()
            except OSError:
                body = b"App page is missing."
                self.send_bytes(500, body, "text/plain; charset=utf-8")
                return
            self.send_bytes(200, body, "text/html; charset=utf-8")
            return
        if path == "/api/vendors":
            if self.require_auth():
                self.send_json(200, {"vendors": all_vendors(), "capabilities": CAPABILITIES})
            return
        if path == "/api/export.csv":
            if not self.require_auth():
                return
            fields = ["vendorNo", "name", "gstin", "address", "supplierType", "capabilities", "contact", "phone", "email", "website", "notes", "mapUrl", "addressSourceUrl", "capabilitySourceUrl"]
            labels = ["Vendor Number", "Company Name", "GSTIN", "Address", "Supplier Type", "Capabilities", "Contact Person", "Phone", "Email", "Website / Listing URL", "Notes", "Google Maps URL", "Address Source URL", "Capability Source URL"]
            stream = io.StringIO(newline="")
            writer = csv.writer(stream)
            writer.writerow(labels)
            for v in all_vendors():
                writer.writerow(["; ".join(v.get(k, [])) if k == "capabilities" else v.get(k, "") for k in fields])
            body = ("\ufeff" + stream.getvalue()).encode("utf-8")
            self.send_bytes(200, body, "text/csv; charset=utf-8", {"Content-Disposition": "attachment; filename=zeqube-vendors.csv"})
            return
        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/login":
            try:
                data = self.read_json()
            except Exception:
                self.send_json(400, {"error": "Invalid login request."})
                return
            if not secrets.compare_digest(str(data.get("code", "")), ACCESS_CODE):
                self.send_json(403, {"error": "That access code is not correct."})
                return
            sid = secrets.token_urlsafe(32)
            with SESSION_LOCK:
                SESSIONS.add(sid)
            self.send_json(200, {"ok": True}, {"Set-Cookie": f"zq_session={sid}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400"})
            return
        if path == "/api/logout":
            sid = self.session_id()
            with SESSION_LOCK:
                SESSIONS.discard(sid)
            self.send_json(200, {"ok": True}, {"Set-Cookie": "zq_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
            return
        if path == "/api/vendors":
            if not self.require_auth():
                return
            try:
                item = clean_record(self.read_json())
                save_record(item, is_new=True)
            except ValueError as exc:
                self.send_json(400, {"error": str(exc)})
                return
            except sqlite3.IntegrityError:
                self.send_json(409, {"error": "That vendor ID already exists."})
                return
            except Exception:
                self.send_json(400, {"error": "Could not save vendor data."})
                return
            self.send_json(201, {"vendor": item})
            return
        self.send_json(404, {"error": "Not found"})

    def do_PUT(self):
        if urlparse(self.path).path != "/api/vendors":
            self.send_json(404, {"error": "Not found"})
            return
        if not self.require_auth():
            return
        try:
            data = self.read_json()
            vendor_id = str(data.get("id", ""))
            with connect_db() as con:
                row = con.execute("SELECT payload FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
            if not row:
                self.send_json(404, {"error": "Vendor not found."})
                return
            item = clean_record(data, json.loads(row["payload"]))
            save_record(item)
        except ValueError as exc:
            self.send_json(400, {"error": str(exc)})
            return
        except Exception:
            self.send_json(400, {"error": "Could not save vendor data."})
            return
        self.send_json(200, {"vendor": item})


def lan_ipv4s():
    found = set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = item[4][0]
            if not ip.startswith("127."):
                found.add(ip)
    except OSError:
        pass
    return sorted(found)


if __name__ == "__main__":
    init_db()
    print("\nZeQube Vendor App is running on this PC.")
    print(f"PC access: http://127.0.0.1:{PORT}")
    ips = lan_ipv4s()
    if ips:
        for ip in ips:
            print(f"Phone / LAN access: http://{ip}:{PORT}")
    else:
        print("Phone access: find this PC's IPv4 address with ipconfig, then use http://<IPv4>:%d" % PORT)
    print(f"Team access code for this run: {ACCESS_CODE}")
    print("Use only on a trusted private Wi-Fi. Press Ctrl+C to stop.\n")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ZeQube Vendor App...")
    finally:
        server.server_close()

