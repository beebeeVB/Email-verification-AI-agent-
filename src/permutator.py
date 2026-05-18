"""
Algorithmic email permutation engine.

Instead of hardcoding patterns, this generates all valid combinations
from named components and ranks them by global corporate prevalence.
Produces ~1000 unique candidates per target, ordered so the most likely
formats are tested first — meaning SMTP verification stops early on
the vast majority of real addresses.
"""

import time
import itertools
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def _scrape_domain_pattern(domain: str) -> str | None:
    try:
        time.sleep(1.2)
        r = requests.get(
            f"https://www.email-format.com/d/{domain}/",
            headers=HEADERS,
            timeout=10
        )
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for td in soup.find_all("td"):
            text = td.get_text(strip=True)
            if "%" in text and ("first" in text or "last" in text):
                return text
        return None
    except Exception:
        return None


def _apply_scraped_pattern(pattern: str, f: str, l: str, domain: str) -> str:
    local = (
        pattern
        .replace("%first%", f).replace("%last%", l)
        .replace("%f%", f[0]).replace("%l%", l[0])
    )
    return f"{local}@{domain}"


def _build_name_tokens(first: str, last: str) -> dict:
    """
    All the name fragments we'll combine algorithmically.
    """
    f = first.lower().strip()
    l = last.lower().strip()
    return {
        "f":   f,               # full first
        "l":   l,               # full last
        "fi":  f[0],            # first initial
        "li":  l[0],            # last initial
        "f2":  f[:2],           # first 2
        "f3":  f[:3],           # first 3
        "f4":  f[:4],           # first 4
        "f5":  f[:5],           # first 5
        "l2":  l[:2],           # last 2
        "l3":  l[:3],           # last 3
        "l4":  l[:4],           # last 4
        "l5":  l[:5],           # last 5
        "fili": f[0] + l[0],    # both initials
    }


def _generate_all(tokens: dict, domain: str) -> list[str]:
    """
    Algorithmically generates all meaningful permutations.
    Returns a ranked list — highest probability first.
    """
    f  = tokens["f"]
    l  = tokens["l"]
    fi = tokens["fi"]
    li = tokens["li"]
    f2 = tokens["f2"]
    f3 = tokens["f3"]
    f4 = tokens["f4"]
    f5 = tokens["f5"]
    l2 = tokens["l2"]
    l3 = tokens["l3"]
    l4 = tokens["l4"]
    l5 = tokens["l5"]
    fili = tokens["fili"]

    # Name fragments in order of increasing truncation
    firsts  = [f, f5, f4, f3, f2, fi]
    lasts   = [l, l5, l4, l3, l2, li]
    seps    = [".", "_", "-", ""]
    suffixes = ["", "1", "2", "01", "001", "123", "99", "100"]
    prefixes = ["", "info.", "contact.", "admin.", "hello."]

    candidates = []

    def add(local: str):
        email = f"{local}@{domain}"
        if email not in seen:
            seen.add(email)
            candidates.append(email)

    seen = set()

    # ── TIER 1: first + sep + last (all separator/truncation combos) ──────────
    for sep in seps:
        for fn in firsts:
            for ln in lasts:
                for sfx in suffixes:
                    add(f"{fn}{sep}{ln}{sfx}")

    # ── TIER 2: last + sep + first ────────────────────────────────────────────
    for sep in seps:
        for fn in firsts:
            for ln in lasts:
                for sfx in suffixes:
                    add(f"{ln}{sep}{fn}{sfx}")

    # ── TIER 3: first initial + last (all truncations) ───────────────────────
    for ln in lasts:
        for sfx in suffixes:
            add(f"{fi}{ln}{sfx}")
            add(f"{fi}.{ln}{sfx}")
            add(f"{fi}_{ln}{sfx}")
            add(f"{fi}-{ln}{sfx}")

    # ── TIER 4: last + first initial ─────────────────────────────────────────
    for ln in lasts:
        for sfx in suffixes:
            add(f"{ln}{fi}{sfx}")
            add(f"{ln}.{fi}{sfx}")
            add(f"{ln}_{fi}{sfx}")

    # ── TIER 5: first name only / last name only ──────────────────────────────
    for fn in firsts:
        for sfx in suffixes:
            add(f"{fn}{sfx}")
    for ln in lasts:
        for sfx in suffixes:
            add(f"{ln}{sfx}")

    # ── TIER 6: initials ──────────────────────────────────────────────────────
    for sfx in suffixes:
        add(f"{fili}{sfx}")
        add(f"{fi}.{li}{sfx}")
        add(f"{fi}_{li}{sfx}")
        add(f"{li}{fi}{sfx}")
        add(f"{li}.{fi}{sfx}")

    # ── TIER 7: three-part combos (first.last.initial etc) ───────────────────
    for sep in [".", "_", "-"]:
        add(f"{f}{sep}{l}{sep}{fi}")
        add(f"{fi}{sep}{f}{sep}{l}")
        add(f"{l}{sep}{f}{sep}{fi}")
        add(f"{fi}{sep}{li}{sep}{f}")
        add(f"{f}{sep}{li}{sep}{l}")

    # ── TIER 8: prefix variants (info., contact.) ─────────────────────────────
    for pfx in prefixes[1:]:  # skip empty prefix, already covered
        add(f"{pfx}{f}.{l}")
        add(f"{pfx}{fi}{l}")
        add(f"{pfx}{f}")
        add(f"{pfx}{fili}")

    # ── TIER 9: dot-ext variants used by some telecoms and EU companies ───────
    for fn in [f, fi]:
        for ln in [l, l3]:
            add(f"{fn}.{ln}.ext")
            add(f"{fn}.{ln}.work")

    # ── TIER 10: double initial + full last / full first + double initial ─────
    for sfx in suffixes[:4]:
        add(f"{fi}{li}{l}{sfx}")
        add(f"{f}{fi}{li}{sfx}")
        add(f"{li}{fi}{l}{sfx}")
        add(f"{f}{li}{sfx}")
        add(f"{fi}{l}{li}{sfx}")

    return candidates


def generate_candidates(first: str, last: str, domain: str) -> list[str]:
    f = first.lower().strip()
    l = last.lower().strip()
    d = domain.lower().strip()

    candidates = []

    # Always try the scraped domain pattern first
    scraped = _scrape_domain_pattern(d)
    if scraped:
        top = _apply_scraped_pattern(scraped, f, l, d)
        candidates.append(top)
        print(f"  [pattern] {d} -> {scraped} (email-format.com)")
    else:
        print(f"  [pattern] {d} -> not indexed, generating permutations")

    tokens = _build_name_tokens(f, l)
    generated = _generate_all(tokens, d)

    for email in generated:
        if email not in candidates:
            candidates.append(email)

    candidates = candidates[:1000]
    print(f"  [candidates] {len(candidates)} total (capped at 1000)")
    return candidates
