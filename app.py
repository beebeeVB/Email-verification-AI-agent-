"""
Flask web interface for tamor-contact-agent.
Run with: python app.py
Then open: http://localhost:5000
"""

import json
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify

from src.dns_router import get_mx_server
from src.permutator import generate_candidates
from src.smtp_verifier import verify

app = Flask(__name__)

# in-memory job state
job = {
    "running": False,
    "log": [],
    "results": []
}


def run_job(targets):
    job["running"] = True
    job["log"] = []
    job["results"] = []

    def log(msg):
        job["log"].append(msg)

    for t in targets:
        first = t["first_name"]
        last = t["last_name"]
        company = t["company"]
        domain = t["domain"]
        role = t.get("role", "")

        log(f"→ {first} {last} | {role} @ {company}")

        mx = get_mx_server(domain)
        if not mx:
            log(f"  ✗ DNS failed for {domain}")
            job["results"].append({"name": f"{first} {last}", "company": company,
                                   "role": role, "email": "—", "status": "DNS_FAILED"})
            continue

        candidates = generate_candidates(first, last, domain)

        found = False
        for candidate in candidates:
            log(f"  trying {candidate}")
            status = verify(mx, candidate, domain)
            log(f"  smtp → {status}")

            if status == "VALID":
                log(f"  ✓ confirmed: {candidate}")
                job["results"].append({"name": f"{first} {last}", "company": company,
                                       "role": role, "email": candidate, "status": "VALID"})
                found = True
                break

            if status == "CATCH_ALL":
                log(f"  ~ catch-all domain, best guess: {candidates[0]}")
                job["results"].append({"name": f"{first} {last}", "company": company,
                                       "role": role, "email": candidates[0], "status": "CATCH_ALL"})
                found = True
                break

            if status in ("UNREACHABLE", "TIMEOUT"):
                log(f"  ✗ mail server unreachable")
                job["results"].append({"name": f"{first} {last}", "company": company,
                                       "role": role, "email": "—", "status": status})
                found = True
                break

        if not found:
            job["results"].append({"name": f"{first} {last}", "company": company,
                                   "role": role, "email": "—", "status": "NOT_FOUND"})

    log("— done —")
    job["running"] = False

    # save results
    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/results.json", "w") as f:
        json.dump(job["results"], f, indent=2)


@app.route("/")
def index():
    targets = []
    try:
        with open("config/targets.json") as f:
            targets = json.load(f)
    except Exception:
        pass
    return render_template("index.html", targets=targets)


@app.route("/api/targets", methods=["GET"])
def get_targets():
    try:
        with open("config/targets.json") as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify([])


@app.route("/api/targets", methods=["POST"])
def save_targets():
    targets = request.json
    with open("config/targets.json", "w") as f:
        json.dump(targets, f, indent=2)
    return jsonify({"ok": True})


@app.route("/api/run", methods=["POST"])
def run():
    if job["running"]:
        return jsonify({"error": "already running"}), 400
    with open("config/targets.json") as f:
        targets = json.load(f)
    thread = threading.Thread(target=run_job, args=(targets,))
    thread.daemon = True
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/status")
def status():
    return jsonify({
        "running": job["running"],
        "log": job["log"],
        "results": job["results"]
    })

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
