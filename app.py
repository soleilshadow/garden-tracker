from flask import Flask, send_from_directory, request, jsonify
import os, json, anthropic, requests

app = Flask(__name__, static_folder="static")

# ── Config (set these as environment variables on Railway) ──
ANTHROPIC_API_KEY = os.environ.get("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", "")
SUPABASE_URL      = os.environ.get("https://serucsjjrgwaedwlnyxb.supabase.co", "")
SUPABASE_KEY      = os.environ.get("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlcnVjc2pqcmd3YWVkd2xueXhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwNjM0NzEsImV4cCI6MjA5MjYzOTQ3MX0.woxRyPI-BXoxkk6fP1gVrmV1-RnYn2deoKsxOHMPG58", "")
PLANTS_ROW_ID     = 1   # we store all plants in a single JSON row

# ── Anthropic client ────────────────────────────────────────
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
MODEL  = "claude-sonnet-4-6"

# ── Supabase helpers ────────────────────────────────────────
SUPA_HEADERS = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def supabase_get():
    """Load all plants from Supabase."""
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/plants?id=eq.{PLANTS_ROW_ID}&select=data",
            headers=SUPA_HEADERS(), timeout=10
        )
        rows = r.json()
        if rows and len(rows) > 0:
            return rows[0]["data"]
        return []
    except Exception as e:
        print(f"Supabase GET error: {e}")
        return []

def supabase_save(plants):
    """Save all plants to Supabase (upsert)."""
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/plants",
            headers={**SUPA_HEADERS(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json={"id": PLANTS_ROW_ID, "data": plants},
            timeout=10
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"Supabase SAVE error: {e}")
        return False


# ── Serve frontend ──────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


# ── Debug / health check ────────────────────────────────────
@app.route("/test-ai")
def test_ai():
    try:
        msg = client.messages.create(
            model=MODEL, max_tokens=50,
            messages=[{"role": "user", "content": "Say hello in one sentence."}]
        )
        return f"<h2>✅ AI is working!</h2><p>{msg.content[0].text}</p>"
    except anthropic.AuthenticationError:
        return "<h2>❌ Invalid API key</h2>"
    except Exception as e:
        return f"<h2>❌ Error</h2><pre>{str(e)}</pre>"

@app.route("/test-db")
def test_db():
    try:
        plants = supabase_get()
        return f"<h2>✅ Database connected!</h2><p>{len(plants)} plant(s) stored.</p>"
    except Exception as e:
        return f"<h2>❌ Database error</h2><pre>{str(e)}</pre>"


# ── Claude API proxy ────────────────────────────────────────
@app.route("/api/claude", methods=["POST"])
def claude_proxy():
    try:
        payload = request.get_json()
        print("Calling Claude API...")
        kwargs = {
            "model":      MODEL,
            "max_tokens": payload.get("max_tokens", 1000),
            "messages":   payload.get("messages", [])
        }
        if payload.get("system"):
            kwargs["system"] = payload["system"]
        msg = client.messages.create(**kwargs)
        print("Claude responded OK")
        return jsonify({"content": [{"type": "text", "text": msg.content[0].text}]})
    except anthropic.AuthenticationError:
        return jsonify({"error": "Invalid API key"}), 401
    except Exception as e:
        print(f"Claude proxy error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Plant data API (Supabase backend) ───────────────────────
@app.route("/api/plants", methods=["GET"])
def get_plants():
    return jsonify(supabase_get())

@app.route("/api/plants", methods=["POST"])
def save_plants():
    plants = request.get_json()
    ok = supabase_save(plants)
    return jsonify({"ok": ok})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False)
