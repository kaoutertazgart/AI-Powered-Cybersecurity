# header_analyzer.py
# Input:  flat dict of headers  e.g. {"from": "...", "authentication-results": "..."}
# Output: structured result dict with individual checks + total risk score

import re
from email.utils import parseaddr


# ══════════════════════════════════════════════════════
# 1. PARSE — convert raw header dict to clean fields
# ══════════════════════════════════════════════════════
def parse_headers(raw: dict) -> dict:
    """
    The Gmail API returns headers as a flat dict with lowercase keys.
    We just pull out the fields we care about with safe fallbacks.
    """
    return {
        "from":        raw.get("from", ""),
        "return_path": raw.get("return-path", ""),
        "reply_to":    raw.get("reply-to", ""),
        "received":    raw.get("received", ""),
        "auth_results":raw.get("authentication-results", ""),
        "dkim_sig":    raw.get("dkim-signature", ""),
        "received_spf":raw.get("received-spf", ""),
        "date":        raw.get("date", ""),
        "subject":     raw.get("subject", ""),
    }
# ══════════════════════════════════════════════════════
# HELPER — extract root domain from a full domain string
# e.g. "bounce.linkedin.com" → "linkedin.com"
#      "mail.google.com"     → "google.com"
# ══════════════════════════════════════════════════════
def get_root_domain(domain: str) -> str:
    """
    Returns the registrable root domain (last two labels).
    Handles common two-part TLDs like .co.uk naively — good enough for email checks.
    """
    if not domain:
        return ""
    parts = domain.lower().strip().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain.lower().strip()

# ══════════════════════════════════════════════════════
# 2. SPF CHECK
# ══════════════════════════════════════════════════════
#
# Official values per RFC 7208 §2.6 and RFC 8601 §2.7.2:
#   none      → No SPF record found, or no valid domain in SMTP session
#   neutral   → Domain makes no assertion about the sending server (+/-)
#   pass      → Server IS authorized by the domain
#   fail      → Server is NOT authorized (hard fail)
#   softfail  → Server is probably not authorized (weak fail, ~all)
#   temperror → Transient DNS error — try again later
#   permerror → Permanent DNS error — SPF record is malformed
#   policy    → RFC 8601 §2.7.2: result violates local policy (rare, added by some MTAs)

def check_spf(auth_results: str) -> dict:
    combined = (auth_results).lower()
 
    # Extract the spf= value with a proper word-boundary regex
    # This matches: spf=pass, spf=fail, spf=softfail etc.
    match = re.search(r"spf=(pass|fail|softfail|neutral|none|temperror|permerror|policy)\b", combined)
 
    if not match:
        # No spf= token found at all in  header
        return {
            "status": "missing",
            "score":  15,
            "detail": "No SPF result found in headers — sender cannot be verified."
        }
 
    result = match.group(1)  # the exact RFC value
 
    # Score and explanation for each RFC-defined value
    SPF_RESULTS = {
        "pass": {
            "score": 0,
            "detail": "SPF pass — sending server is explicitly authorized by the domain."
        },
        "fail": {
            # Hard fail: domain explicitly says this server is NOT allowed
            "score": 40,
            "detail": "SPF fail — sending server is explicitly NOT authorized. Strong phishing signal."
        },
        "softfail": {
            # ~all: probably not authorized, but domain didn't use hard fail
            "score": 20,
            "detail": "SPF softfail — server is probably not authorized (~all). Suspicious."
        },
        "neutral": {
            # +/- doesn't matter, domain makes no claim
            "score": 5,
            "detail": "SPF neutral — domain makes no assertion about this server. Low risk alone."
        },
        "none": {
            # No SPF record exists — common for small/old domains, not alarming alone
            "score": 15,
            "detail": "SPF none — no SPF record published. Sender cannot be verified."
        },
        "temperror": {
            # Transient DNS error — could retry later, not necessarily malicious
            "score": 15,
            "detail": "SPF temperror — temporary DNS error during lookup. Try again later."
        },
        "permerror": {
            # Permanent misconfiguration — always suspicious
            "score": 25,
            "detail": "SPF permerror — domain's SPF record is malformed or too complex. DNS operator must fix."
        },
        "policy": {
            # Added by some MTAs when result violates their local policy
            "score": 20,
            "detail": "SPF policy — result was altered by local mail server policy."
        },
    }
 
    info = SPF_RESULTS[result]
    return {
        "status": result,
        "score":  info["score"],
        "detail": info["detail"]
    }
 
 
# ══════════════════════════════════════════════════════
# 3. DKIM CHECK
# ══════════════════════════════════════════════════════
#
# Official values per RFC 6376 and RFC 8601 §2.7.1:
#   none      → No DKIM signature present
#   pass      → Signature verified successfully
#   fail      → Signature present but verification failed (tampered or forged)
#   policy    → Signature valid but violates the signing domain's stated policy
#   neutral   → Signature present but not verifiable (e.g. key revoked)
#   temperror → Transient error during DNS key lookup
#   permerror → Permanent error — key record malformed or algorithm unsupported
#
# IMPORTANT: RFC 8601 says "neutral" or "none" means the message is treated
# as if it had no signature at all — the verifier cannot make a trust decision.

def check_dkim(auth_results: str, dkim_sig: str, from_header: str) -> dict:
    combined = auth_results.lower()
 
    # Extract the dkim= result value using RFC 8601 registered values only
    match = re.search(r"dkim=(pass|fail|neutral|none|policy|temperror|permerror)\b", combined)
 
    # Extract the signing domain from the DKIM-Signature header (d= tag)
    dkim_domain_match = re.search(r"\bd=([^;\s]+)", dkim_sig, re.IGNORECASE)
    dkim_domain = dkim_domain_match.group(1).strip().lower().rstrip(".") if dkim_domain_match else None
 
    # Extract the From: domain using parseaddr (handles "Display Name <email>" format safely)
    _, addr = parseaddr(from_header)
    from_domain = addr.split("@")[1].strip().lower() if "@" in addr else None
 
    # Relaxed alignment check per RFC 7489 §3.1.1:
    # dkim_domain must equal from_domain OR be a subdomain of from_domain (or vice versa)
    def relaxed_aligned(dkim_d, from_d):
        if not dkim_d or not from_d:
            return False
        return (
            dkim_d == from_d or
            dkim_d.endswith("." + from_d) or
            from_d.endswith("." + dkim_d)
        )
 
    aligned = relaxed_aligned(dkim_domain, from_domain)
 
    if not match:
        # No dkim= token in Authentication-Results at all
        return {
            "status": "missing",
            "score":  10,
            "detail": "No DKIM result in headers — message integrity cannot be verified.",
            "dkim_domain": dkim_domain
        }
 
    result = match.group(1)
 
    # Handle each RFC value
    if result == "pass":
        if aligned:
            return {
                "status": "pass",
                "score":  0,
                "detail": f"DKIM pass — message is authentic and unmodified. Signing domain '{dkim_domain}' aligns with From domain.",
                "dkim_domain": dkim_domain
            }
        else:
            # DKIM passed but domains don't align — this is a spoofing signal
            # per RFC 7489: DMARC alignment requires the d= to match the From domain
            return {
                "status": "pass_misaligned",
                "score":  35,
                "detail": (
                    f"DKIM pass but domain mismatch: signature is from '{dkim_domain}' "
                    f"while From domain is '{from_domain}'. "
                    f"This fails DMARC alignment and is a spoofing indicator."
                ),
                "dkim_domain": dkim_domain
            }
 
    elif result == "fail":
        return {
            "status": "fail",
            "score":  35,
            "detail": "DKIM fail — signature is invalid. Message was likely tampered with in transit or forged.",
            "dkim_domain": dkim_domain
        }
 
    elif result == "policy":
        # Valid signature but violates the domain's declared signing policy
        return {
            "status": "policy",
            "score":  20,
            "detail": "DKIM policy — signature is technically valid but violates the signing domain's policy.",
            "dkim_domain": dkim_domain
        }
 
    elif result == "neutral":
        # Per RFC 8601: treat as unsigned — verifier cannot make trust decision
        return {
            "status": "neutral",
            "score":  10,
            "detail": "DKIM neutral — signature present but cannot be verified (e.g. key revoked or unavailable).",
            "dkim_domain": dkim_domain
        }
 
    elif result == "none":
        # No signature present at all
        return {
            "status": "none",
            "score":  10,
            "detail": "DKIM none — no DKIM signature present on this message.",
            "dkim_domain": None
        }
 
    elif result == "temperror":
        return {
            "status": "temperror",
            "score":  10,
            "detail": "DKIM temperror — temporary DNS error during key lookup. Not necessarily malicious.",
            "dkim_domain": dkim_domain
        }
 
    elif result == "permerror":
        return {
            "status": "permerror",
            "score":  20,
            "detail": "DKIM permerror — DKIM key record is malformed or algorithm is unsupported.",
            "dkim_domain": dkim_domain
        }
 
    # Should never reach here given the regex above, but safe fallback
    return {
        "status": result,
        "score":  10,
        "detail": f"DKIM unknown result: {result}",
        "dkim_domain": dkim_domain
    }
 
 
# ══════════════════════════════════════════════════════
# 4. DMARC CHECK
# ══════════════════════════════════════════════════════
#
# Official result values per RFC 7489 §11.2 and RFC 8601:
#   pass  → At least one of SPF or DKIM passed WITH alignment to the From domain
#   fail  → Neither SPF nor DKIM passed with alignment
#
# That's it — only two result values. DMARC is binary.
#
# The POLICY (p=) is separate from the result. It lives inside parentheses
# in the Authentication-Results header, e.g.:
#   dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from=google.com
#   dmarc=fail (p=QUARANTINE) header.from=evil.com
#
# Policy values per RFC 7489 §6.3: none | quarantine | reject
#
# NOTE: "bestguesspass" is a non-standard Gmail-specific extension.
# It is NOT in the RFC. We handle it but flag it as weak.
# ══════════════════════════════════════════════════════
def check_dmarc(auth_results: str) -> dict:
    combined = auth_results.lower()
 
    # Extract dmarc= result (only pass or fail per RFC 7489)
    result_match = re.search(r"dmarc=(pass|fail)\b", combined)
 
    # Extract policy p= from inside the parentheses after dmarc=result
    # Real format: dmarc=pass (p=REJECT sp=REJECT dis=NONE)
    # We anchor p= to appear after dmarc= to avoid false matches
    policy_match = re.search(r"dmarc=(?:pass|fail)[^;]*\bp=(none|quarantine|reject)\b", combined)
    policy = policy_match.group(1) if policy_match else None
 
    # Handle Gmail-specific non-standard "bestguesspass"
    if not result_match and "dmarc=bestguesspass" in combined:
        return {
            "status": "bestguesspass",
            "score":  15,
            "policy": policy,
            "detail": (
                "DMARC bestguesspass — non-standard Gmail result. "
                "No DMARC record exists but authentication looks plausible. Weak signal."
            )
        }
 
    if not result_match:
        # No dmarc= token at all — domain has not published a DMARC record
        return {
            "status": "missing",
            "score":  10,
            "policy": None,
            "detail": "No DMARC record — domain has not published an email policy. Cannot enforce."
        }
 
    result = result_match.group(1)
 
    if result == "pass":
        return {
            "status": "pass",
            "score":  0,
            "policy": policy,
            "detail": (
                f"DMARC pass — email is aligned and authenticated. "
                f"Domain policy: {policy.upper() if policy else 'unknown'}."
            )
        }
 
    elif result == "fail":
        # Score varies by the published policy — a reject policy failing is more alarming
        policy_score = {
            "reject":     45,
            "quarantine": 35,
            "none":       20,
            None:         25,
        }
        score = policy_score.get(policy, 25)
 
        return {
            "status": "fail",
            "score":  score,
            "policy": policy,
            "detail": (
                f"DMARC fail — neither SPF nor DKIM aligned with the From domain. "
                f"Domain policy is '{policy or 'unknown'}' — "
                f"{'email should be rejected.' if policy == 'reject' else 'email may be quarantined or delivered.'}"
            )
        }
 
 
# ══════════════════════════════════════════════════════
# 5. TIMEZONE CHECK
# ══════════════════════════════════════════════════════
def check_timezone(received_header: str, date_header: str) -> dict:
    """
    Legitimate emails should have consistent timezone info.
    We check for:
      - Impossible offsets (beyond ±12h = beyond ±1200)
      - Mismatch between the Received header and Date header timezones
    """
    if not received_header:
        return {"status": "unknown", "score": 10, "detail": "No Received header to check."}

    # Extract timezone from Received header  e.g. "+0500" or "-0800"
    received_tz_match = re.search(r"([+-]\d{4})\s", received_header)
    date_tz_match     = re.search(r"([+-]\d{4})\s", date_header) if date_header else None

    if not received_tz_match:
        return {"status": "unknown", "score": 10, "detail": "Timezone not found in Received header."}

    received_tz = received_tz_match.group(1)
    date_tz     = date_tz_match.group(1) if date_tz_match else None
    offset_val  = int(received_tz)

    # Flag: impossible timezone offset (valid range is -1200 to +1400)
    if abs(offset_val) > 1400:
        return {
            "status": "invalid",
            "score":  40,
            "detail": f"Impossible timezone offset: {received_tz}. No real timezone is this far off."
        }

    # Flag: timezone mismatch between Received and Date headers
    if date_tz and received_tz != date_tz:
        return {
            "status": "mismatch",
            "score":  30,
            "detail": f"Timezone mismatch — Received says {received_tz}, Date says {date_tz}.",
            "received_tz": received_tz,
            "date_tz":     date_tz
        }

    return {
        "status": "ok",
        "score":  0,
        "detail": f"Timezone looks normal ({received_tz}).",
        "received_tz": received_tz
    }



# ══════════════════════════════════════════════════════
# 6. DOMAIN MISMATCH CHECK
# ══════════════════════════════════════════════════════

# Known brand patterns — detect lookalike/impersonation domains
BRAND_PATTERNS = [
    (r"paypa[l1]|pay-pal",            "PayPal"),
    (r"amaz[o0]n(?!\.com)",           "Amazon"),
    (r"g[o0]{2}gl[e3]",              "Google"),
    (r"micr[o0]s[o0]ft|micros0ft",   "Microsoft"),
    (r"app1e|appl[e3]\.(?!com)",     "Apple"),
    (r"netfl[i1]x",                  "Netflix"),
    (r"faceb[o0]{2}k",               "Facebook"),
    (r"inst[a4]gr[a4]m",             "Instagram"),
]

# Legitimate root domains per brand
BRAND_ROOTS = {
    "PayPal":    "paypal.com",
    "Amazon":    "amazon.com",
    "Google":    "google.com",
    "Microsoft": "microsoft.com",
    "Apple":     "apple.com",
    "Netflix":   "netflix.com",
    "Facebook":  "facebook.com",
    "Instagram": "instagram.com",
}

def check_domain_consistency(from_h: str, return_path: str, reply_to: str) -> dict:
    """
    Checks that the From, Return-Path, and Reply-To domains are consistent.
    A mismatch is a classic phishing technique.
    Also checks for brand impersonation in the From domain.

    FIX 1: Return-Path and Reply-To are compared using ROOT domains,
            not full subdomains — bounce domains like
            chime-notifications-apps.bounces.google.com are legitimate.

    FIX 2: Brand impersonation check is skipped when the from_domain
            is a real subdomain of the brand's legitimate root domain —
            classroom.google.com is not a Google impersonation.
    """
    def extract_domain(header_value: str) -> str | None:
        _, addr = parseaddr(header_value)
        if "@" in addr:
            return addr.split("@")[1].strip().lower()
        return None

    from_domain        = extract_domain(from_h)
    return_path_domain = extract_domain(return_path)
    reply_to_domain    = extract_domain(reply_to)

    flags  = []
    score  = 0

    # Compute root domains for comparison
    from_root        = get_root_domain(from_domain)        if from_domain        else None
    return_path_root = get_root_domain(return_path_domain) if return_path_domain else None
    reply_to_root    = get_root_domain(reply_to_domain)    if reply_to_domain    else None

    # 1 Check Return-Path mismatch using ROOT domains
    if return_path_root and from_root and return_path_root != from_root:
        flags.append(f"Return-Path domain ({return_path_domain}) ≠ From domain ({from_domain}).")
        score += 30

    # 2 Check Reply-To mismatch using ROOT domains
    if reply_to_root and from_root and reply_to_root != from_root:
        flags.append(f"Reply-To domain ({reply_to_domain}) ≠ From domain ({from_domain}). Replies go elsewhere.")
        score += 25

    # 3 — Check brand impersonation, but skip if it's a real subdomain
    impersonated_brand = None
    if from_domain:
        for pattern, brand in BRAND_PATTERNS:
            if re.search(pattern, from_domain, re.IGNORECASE):
                legitimate_root = BRAND_ROOTS.get(brand)
                if legitimate_root and get_root_domain(from_domain) == legitimate_root:
                    # Real subdomain of the brand — not an impersonation
                    break
                # Pattern matched AND root domain is not the real brand → flag it
                impersonated_brand = brand
                flags.append(f'From domain "{from_domain}" looks like a {brand} impersonation.')
                score += 40
                break

    return {
        "from_domain":        from_domain,
        "return_path_domain": return_path_domain,
        "reply_to_domain":    reply_to_domain,
        "impersonated_brand": impersonated_brand,
        "flags":              flags,
        "score":              score
    }

# ══════════════════════════════════════════════════════
# 7. FINAL SCORE + VERDICT
# ══════════════════════════════════════════════════════
def get_verdict(score: int) -> str:
    if score >= 70:
        return "phishing"
    elif score >= 40:
        return "suspicious"
    else:
        return "safe"


# ══════════════════════════════════════════════════════
# MAIN ENTRY POINT — called by app.py
# ══════════════════════════════════════════════════════
def analyze_headers(raw_headers: dict) -> dict:
    """
    Main function. Takes the flat headers dict from background.js.
    Returns a full structured result for the API to return to the extension.

    Args:
        raw_headers: dict with lowercase keys, e.g.
                     {"from": "...", "authentication-results": "...", ...}

    Returns:
        dict with spf, dkim, dmarc, timezone, domain checks, total score, verdict
    """
    h = parse_headers(raw_headers)

    spf      = check_spf(h["auth_results"])
    dkim     = check_dkim(h["auth_results"], h["dkim_sig"], h["from"])
    dmarc    = check_dmarc(h["auth_results"])
    timezone = check_timezone(h["received"], h["date"])
    domains  = check_domain_consistency(h["from"], h["return_path"], h["reply_to"])

    # Total score: sum all individual scores, cap at 100
    total_score = min(
        spf["score"] + dkim["score"] + dmarc["score"] +
        timezone["score"] + domains["score"],
        100
    )

    return {
        "header_score": total_score,
        "verdict":      get_verdict(total_score),
        "spf":          spf,
        "dkim":         dkim,
        "dmarc":        dmarc,
        "timezone":     timezone,
        "domains":      domains,
        # Flat list of all warning messages for the UI
        "all_flags": (
            ([spf["detail"]]   if spf["status"]   not in ("pass",)         else []) +
            ([dkim["detail"]]  if dkim["status"]  not in ("pass",)         else []) +
            ([dmarc["detail"]] if dmarc["status"] not in ("pass",)         else []) +
            domains["flags"] +
            ([timezone["detail"]] if timezone["status"] not in ("ok", "unknown") else [])
        )
    }