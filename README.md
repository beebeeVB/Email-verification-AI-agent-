# tamor-contact-agent

A zero-cost email verification agent for B2B market research. No paid APIs. No subscriptions. Finds and verifies corporate email addresses by combining domain pattern detection with direct SMTP handshakes against live mail servers — the same method Hunter.io charges $49/month for.

---

## How It Works

Most email finders guess an address and hope it doesn't bounce. This agent verifies before you ever send. The pipeline runs three steps per target:

```
[Name + Domain] → [Pattern Detection] → [Candidate Construction] → [SMTP Handshake] → [Result]
```

### Step 1 — Pattern Detection

The agent scrapes [email-format.com](https://email-format.com) to find the verified email format for the target domain. For example, `amfori.org` uses `{first}.{last}` — so `Mathias Luyten` becomes `mathias.luyten@amfori.org`.

If the domain isn't indexed on email-format.com, the agent falls back to a ranked list of the most common corporate email patterns in order of global prevalence:

| Priority | Pattern | Example |
|---|---|---|
| 1 | first.last | mathias.luyten@domain.com |
| 2 | flast | mluyten@domain.com |
| 3 | first_last | mathias_luyten@domain.com |
| 4 | firstlast | mathiasluyten@domain.com |
| 5 | f.last | m.luyten@domain.com |
| 6 | first | mathias@domain.com |

### Step 2 — SMTP Handshake

This is where the verification actually happens. The agent:

1. Looks up the domain's MX record (its mail server address) via DNS
2. Opens a raw TCP connection to that mail server on port 25
3. Sends a `RCPT TO:<candidate@domain.com>` command
4. Reads the server's response code

A `250` response means the mailbox exists and is active. A `550` means it doesn't exist. The agent never actually sends an email — it drops the connection after reading the code.

### Step 3 — Catch-All Detection

Before testing any real address, the agent first tests a provably fake address against the mail server (e.g. `zzznobody99182@domain.com`). If the server returns `250` for that fake address, the domain is configured as **catch-all** — meaning it accepts all incoming mail without revealing which addresses are real. In that case, SMTP verification is unreliable for that domain and the agent flags the result accordingly.

---

## Status Codes

| Status | Meaning | What to do |
|---|---|---|
| `VALID` | SMTP confirmed the mailbox exists. Safe to send. | Send the email |
| `CATCH_ALL` | Server accepts everything. Email is best-guess from pattern. | Send anyway — it won't hard bounce |
| `NOT_FOUND` | All patterns were rejected by the server. | Person may have left, or name/domain is wrong |
| `UNREACHABLE` | Mail server didn't respond or port 25 is blocked. | Run from a different network |
| `DNS_FAILED` | Couldn't resolve the domain's MX record. | Check the domain is correct |

---

## Project Structure

```
tamor-contact-agent/
├── app.py                  # Flask web interface (run this for the UI)
├── main.py                 # CLI pipeline (alternative to the web UI)
├── Procfile                # For Railway deployment
├── requirements.txt
├── config/
│   └── targets.json        # Your input — list of people to find
├── src/
│   ├── dns_router.py       # MX record lookup via dnspython
│   ├── permutator.py       # Pattern scraping + candidate email generation
│   └── smtp_verifier.py    # Direct SMTP handshake engine
├── templates/
│   └── index.html          # Web UI
└── outputs/
    ├── results.csv         # Output after each run
    └── results.json        # Same output in JSON format
```

---

## Setup

### Requirements

- Python 3.10+
- Network access on port 25 (your home/office network — not a cloud server)

### Install

```bash
git clone https://github.com/beebeeVB/Email-verification-AI-agent-.git
cd Email-verification-AI-agent-
pip3 install -r requirements.txt
```

---

## Usage

### Web Interface (recommended)

```bash
python3 app.py
```

Open `http://localhost:5000` in your browser.

The UI lets you:
- Add targets by name, company, domain, and role
- Save targets directly to `config/targets.json`
- Run the agent and watch live logs as it processes each target
- See results in a color-coded table (green = valid, yellow = catch-all, red = failed)

### Command Line

```bash
python3 main.py
```

Reads from `config/targets.json`, prints logs to terminal, saves output to `outputs/`.

---

## Input Format

Edit `config/targets.json` directly or use the web UI to add targets. JSON format:

```json
[
  {
    "company": "amfori",
    "domain": "amfori.org",
    "first_name": "Mathias",
    "last_name": "Luyten",
    "role": "Head of Digital"
  },
  {
    "company": "Example Corp",
    "domain": "example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "role": "CFO"
  }
]
```

Fields:
- `company` — company name (used for display and logging only)
- `domain` — bare domain without `www` or `https` (e.g. `amfori.org` not `www.amfori.org`)
- `first_name` — first name exactly as it appears professionally
- `last_name` — last name
- `role` — job title (display only, doesn't affect verification)

---

## Output Format

Results are saved to `outputs/results.csv` and `outputs/results.json` after every run.

CSV columns:

| Column | Description |
|---|---|
| `name` | Full name of the target |
| `company` | Company name |
| `role` | Job title |
| `email` | Email address found (or — if not found) |
| `status` | VALID, CATCH_ALL, NOT_FOUND, UNREACHABLE, DNS_FAILED |

---

## Important Constraints

### Port 25 and Network

SMTP verification runs on port 25. Most cloud platforms (Railway, Heroku, Vercel, Render, AWS, GCP) block outbound port 25 to prevent spam abuse. This means the agent must be run locally from your own machine or from a VPS provider that explicitly permits port 25 (DigitalOcean allows it after a support request).

If you see a lot of UNREACHABLE results when running locally, your ISP may be blocking port 25. Try switching networks (e.g. your phone's hotspot).

### Catch-All Domains

Large enterprise companies — especially those using Microsoft 365 or Google Workspace — often configure their mail servers as catch-all. This is a deliberate security choice to prevent exactly the kind of enumeration this tool does. When you see CATCH_ALL, the constructed email is still your best option. Send it. It won't hard bounce, and if the pattern is correct it will reach the inbox.

### Rate Limiting and Delays

The agent adds delays between requests to avoid triggering rate limits on email-format.com and to avoid getting flagged as a scanner by mail servers. Do not remove the time.sleep() calls or run multiple instances simultaneously against the same domain.

### Name Accuracy

The agent constructs emails from the exact name you provide. If the person goes by a nickname professionally (e.g. "Bob" instead of "Robert"), use the nickname. Verify names on LinkedIn before adding targets.

---

## Tips for Better Results

- **Verify names on LinkedIn first.** The tool finds emails, not names. If you have the wrong name the email will be wrong regardless of how good the SMTP check is.
- **Check the domain carefully.** Some companies use different domains for email than for their website. Look for email addresses in press releases or on the website.
- **CATCH_ALL is not a failure.** For large enterprise targets, catch-all is nearly universal. The constructed email from the verified pattern is still accurate — you just don't get SMTP confirmation. Send it.
- **For NOT_FOUND results,** double check: (1) the person still works there, (2) the domain is correct, (3) the name matches what they use professionally.

---

## Architecture Notes

The SMTP verification approach is identical to what commercial tools like Hunter.io and ZeroBounce sell as a premium feature. The difference is that those tools run the handshake from IP addresses with clean sender reputations and verified PTR records, which makes some enterprise mail servers more cooperative. From a residential IP, some servers will refuse the connection at the EHLO stage. This is why UNREACHABLE sometimes appears for domains that would return VALID from a commercial tool's infrastructure.

For market research at the scale of tens to low hundreds of contacts, the local approach is sufficient. At 1000+ targets, investing in Hunter.io's API or a dedicated VPS becomes worthwhile.
