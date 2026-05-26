"""
Flask application for an admin‑only CatchMail dashboard (mobile friendly).

This variant generates a single random email address from the
configured domain list each time the home page is loaded.  The
interface is designed to work well on both desktop and mobile: the
email inbox occupies the full width of the page, and on narrow
screens the message list stacks vertically above the message content
for better readability.  The inbox polls the CatchMail API every few
seconds, updating automatically without manual refresh.  Clicking a
message reveals its contents and any OTP detected in the body.  No
login is required — simply load the page and an email is generated.
"""

import json
import os
import random
import re
from flask import Flask, jsonify, render_template_string, request
import requests

# Configuration -----------------------------------------------------------------
API_MAILBOX = "https://api.catchmail.io/api/v1/mailbox"
API_MESSAGE = "https://api.catchmail.io/api/v1/message/{}"

DOMAINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "domains.json")

# Vietnamese style name components (without diacritics)
HO = [
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan",
    "vu", "vo", "dang", "bui", "do", "ho", "ngo", "duong", "ly",
]
TEN_DEM = [
    "van", "minh", "quang", "duc", "gia", "thanh", "tuan",
    "bao", "anh", "nhat", "hoai", "trung", "ngoc", "huu",
]
TEN = [
    "anh", "hieu", "huy", "long", "nam", "phuc", "khang",
    "dat", "son", "duy", "tuan", "phong", "linh", "trang",
    "vy", "ngan", "thao", "han", "nhi", "my",
]


def load_domains():
    """Read domains from the JSON file.  Returns a list of unique domain names."""
    try:
        with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        domains = [d.strip().lower() for d in data if d and isinstance(d, str)]
        return list(dict.fromkeys(domains))  # remove duplicates preserving order
    except Exception:
        return []


def random_email(domain: str) -> str:
    """Generate a random Vietnamese-style username at the given domain."""
    ho = random.choice(HO)
    dem = random.choice(TEN_DEM)
    ten = random.choice(TEN)
    suffix = random.randint(1000, 9999)
    return f"{ho}{dem}{ten}{suffix}@{domain}"


def parse_otp(text: str):
    """Extract an OTP (prefer 6 digits, else 4-8) from a text body."""
    if not text:
        return None
    m6 = re.search(r"\b\d{6}\b", text)
    if m6:
        return m6.group(0)
    m = re.search(r"\b\d{4,8}\b", text)
    return m.group(0) if m else None


app = Flask(__name__)


@app.route("/")
def index():
    """Serve the home page with one random email and its inbox."""
    domains = load_domains()
    if not domains:
        return render_template_string("""
        <h2>Lỗi cấu hình</h2>
        <p>domains.json trống hoặc thiếu, cần ít nhất 1 domain.</p>
        """)
    # Choose one domain at random
    domain = random.choice(domains)
    email = random_email(domain)
    return render_template_string(TEMPLATE, email=email)


@app.route("/api/messages")
def api_messages():
    """Return list of messages for the given email."""
    email = request.args.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Missing email parameter"}), 400
    try:
        resp = requests.get(API_MAILBOX, params={"address": email}, timeout=10)
        data = resp.json() if resp.ok else {}
        messages = data.get("messages", []) if isinstance(data, dict) else []
        simplified = []
        for msg in messages:
            simplified.append({
                "id": msg.get("id"),
                "from": msg.get("from", ""),
                "subject": msg.get("subject", ""),
                "date": msg.get("date", ""),
                "size": msg.get("size", 0),
            })
        return jsonify({"messages": simplified, "count": len(simplified)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/message/<string:message_id>")
def api_message(message_id):
    """Return detailed message content and extracted OTP."""
    email = request.args.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "Missing email parameter"}), 400
    try:
        resp = requests.get(API_MESSAGE.format(message_id), params={"mailbox": email}, timeout=10)
        msg = resp.json() if resp.ok else {}
        body_data = msg.get("body", "")
        if isinstance(body_data, dict):
            body = body_data.get("text", "") or body_data.get("html", "") or ""
        else:
            body = str(body_data or "")
        return jsonify({
            "id": message_id,
            "subject": msg.get("subject", ""),
            "from": msg.get("from", ""),
            "date": msg.get("date", ""),
            "body": body,
            "otp": parse_otp(body),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------------------------------------------------------
# Additional endpoint to generate a new random email on demand.  Returns a
# JSON object with a new email address selected from the configured domains.
@app.route("/api/new-email")
def api_new_email():
    """
    Generate a new random email address using one of the configured domains.
    This endpoint is used by the front‑end to avoid reloading the page when
    the admin wants to start over with a fresh inbox.
    """
    domains = load_domains()
    if not domains:
        return jsonify({"error": "No domains configured"}), 500
    domain = random.choice(domains)
    email = random_email(domain)
    return jsonify({"email": email})


# HTML template with mobile responsive styles and JS
TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CatchMail Admin Mobile</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f7f7f7;
        }
        .container {
            padding: 16px;
        }
        .email-box {
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 16px;
            margin-bottom: 20px;
            width: 100%;
            box-sizing: border-box;
        }
        .header {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
        }
        .email-address {
            font-weight: bold;
            font-size: 1.1em;
            word-break: break-all;
        }
        .actions {
            margin-top: 8px;
        }
        .copy-btn, .refresh-btn, .new-btn {
            padding: 6px 10px;
            margin-left: 6px;
            border: none;
            border-radius: 4px;
            color: #fff;
            font-size: 0.9em;
            cursor: pointer;
        }
        .copy-btn {
            background-color: #4CAF50;
        }
        .refresh-btn {
            background-color: #9C27B0;
        }
        .copy-btn:hover { background-color: #45a049; }
        .refresh-btn:hover { background-color: #8e24aa; }
        .new-btn {
            background-color: #ff9800;
        }
        .new-btn:hover { background-color: #f57c00; }
        .inbox {
            display: flex;
            flex-direction: row;
            gap: 12px;
        }
        .message-list {
            width: 35%;
            max-height: 300px;
            overflow-y: auto;
            border-right: 1px solid #ddd;
            padding-right: 10px;
        }
        .message-list ul { list-style: none; padding: 0; margin: 0; }
        .message-item { padding: 6px; border-bottom: 1px solid #eee; cursor: pointer; }
        .message-item:hover { background-color: #f0f0f0; }
        .message-item.active { background-color: #e8f5e9; }
        .message-content {
            width: 65%;
            max-height: 300px;
            overflow-y: auto;
        }
        .otp {
            background-color: #ffeb3b;
            padding: 6px;
            border-radius: 4px;
            display: inline-block;
            margin-top: 8px;
            font-weight: bold;
        }
        .otp-copy {
            margin-left: 8px;
            padding: 4px 6px;
            background-color: #2196F3;
            color: #fff;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85em;
        }
        .otp-copy:hover { background-color: #1e88e5; }
        /* Responsive design for narrow screens */
        @media (max-width: 600px) {
            .inbox { flex-direction: column; }
            .message-list, .message-content { width: 100%; border-right: none; padding-right: 0; }
            .message-content { margin-top: 12px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="text-align:center;">CatchMail Admin Dashboard</h2>
        <div class="email-box" id="box-1" data-email="{{ email }}">
            <div class="header">
                <span class="email-address">{{ email }}</span>
                <div class="actions">
                    <button class="copy-btn" onclick="copyText('{{ email }}')">Copy email</button>
                    <button class="refresh-btn" onclick="manualRefresh('{{ email }}', 1)">Refresh</button>
                    <button class="new-btn" onclick="newEmail()">Tạo email mới</button>
                </div>
            </div>
            <div class="inbox">
                <div class="message-list" id="list-1">
                    <ul></ul>
                </div>
                <div class="message-content" id="content-1">
                    <em>No message selected.</em>
                </div>
            </div>
        </div>
    </div>
    <script>
        const emails = ["{{ email }}"];
        const POLL_INTERVAL = 3000;
        const state = {};
        emails.forEach((email) => { state[email] = { selectedId: null, timer: null }; });
        function copyText(text) {
            navigator.clipboard.writeText(text).then(() => alert('Đã copy: ' + text));
        }
        function manualRefresh(email, boxIndex) {
            fetchMessages(email, boxIndex, true);
        }
        function fetchMessages(email, boxIndex, manual=false) {
            fetch('/api/messages?email=' + encodeURIComponent(email))
            .then(r => r.json())
            .then(data => {
                const listEl = document.querySelector('#list-' + boxIndex + ' ul');
                const currentSelected = state[email].selectedId;
                listEl.innerHTML = '';
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach(msg => {
                        const li = document.createElement('li');
                        li.classList.add('message-item');
                        if (msg.id === currentSelected) li.classList.add('active');
                        li.dataset.messageId = msg.id;
                        li.innerHTML = `<strong>${msg.subject || '(no subject)'}</strong><br><small>From: ${msg.from || ''}</small>`;
                        li.addEventListener('click', () => {
                            state[email].selectedId = msg.id;
                            listEl.querySelectorAll('.message-item').forEach(item => item.classList.remove('active'));
                            li.classList.add('active');
                            fetchMessageDetail(email, msg.id, boxIndex);
                        });
                        listEl.appendChild(li);
                    });
                    if (!currentSelected) {
                        const firstId = data.messages[0].id;
                        state[email].selectedId = firstId;
                        listEl.querySelector('li').classList.add('active');
                        fetchMessageDetail(email, firstId, boxIndex);
                    } else if (manual) {
                        if (currentSelected) fetchMessageDetail(email, currentSelected, boxIndex);
                    }
                } else {
                    const li = document.createElement('li');
                    li.innerHTML = '<em>Không có mail.</em>';
                    listEl.appendChild(li);
                    document.getElementById('content-' + boxIndex).innerHTML = '<em>No message.</em>';
                    state[email].selectedId = null;
                }
            })
            .catch(err => console.error('Error fetching messages', err));
        }
        function fetchMessageDetail(email, messageId, boxIndex) {
            fetch(`/api/message/${messageId}?email=` + encodeURIComponent(email))
            .then(r => r.json())
            .then(data => {
                const contentEl = document.getElementById('content-' + boxIndex);
                if (data.error) {
                    contentEl.innerHTML = '<span style="color:red;">Error fetching message.</span>';
                    return;
                }
                const otpHtml = data.otp ? `<div class="otp">OTP: ${data.otp} <button class="otp-copy" onclick="copyText('${data.otp}')">Copy</button></div>` : '';
                const safeBody = data.body ? data.body.replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
                const formattedDate = data.date ? new Date(data.date).toLocaleString() : '';
                contentEl.innerHTML = `
                    <p><strong>Subject:</strong> ${data.subject || '(no subject)'}</p>
                    <p><strong>From:</strong> ${data.from || ''}</p>
                    <p><strong>Date:</strong> ${formattedDate}</p>
                    <pre style="white-space: pre-wrap;">${safeBody}</pre>
                    ${otpHtml}
                `;
            })
            .catch(err => console.error('Error fetching message detail', err));
        }
        // Generate a new random email without reloading the page.
        function newEmail() {
            // Save the current email for cleanup
            const currentEmail = emails[0];
            fetch('/api/new-email')
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert('Lỗi tạo email mới');
                    return;
                }
                const newAddr = data.email;
                // Update emails array
                emails[0] = newAddr;
                // Update UI elements with the new email
                document.querySelector('.email-address').textContent = newAddr;
                // Update buttons to reference the new email
                const copyBtn = document.querySelector('.copy-btn');
                copyBtn.setAttribute('onclick', "copyText('" + newAddr + "')");
                const refreshBtn = document.querySelector('.refresh-btn');
                refreshBtn.setAttribute('onclick', "manualRefresh('" + newAddr + "', 1)");
                // Reset state: clear old polling interval and delete state entry
                if (state[currentEmail] && state[currentEmail].timer) {
                    clearInterval(state[currentEmail].timer);
                }
                delete state[currentEmail];
                state[newAddr] = { selectedId: null, timer: null };
                // Clear inbox UI and show loading
                document.querySelector('#list-1 ul').innerHTML = '';
                document.getElementById('content-1').innerHTML = '<em>Đang tải...</em>';
                // Fetch messages for new email and restart polling
                fetchMessages(newAddr, 1);
                state[newAddr].timer = setInterval(() => fetchMessages(newAddr, 1), POLL_INTERVAL);
            })
            .catch(err => {
                console.error('Error generating new email', err);
            });
        }
        // Poll messages periodically
        emails.forEach((email) => {
            const boxIndex = 1;
            fetchMessages(email, boxIndex);
            state[email].timer = setInterval(() => fetchMessages(email, boxIndex), POLL_INTERVAL);
        });
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)