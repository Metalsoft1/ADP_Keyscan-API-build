import os
import json
import sys
import requests

# ---- CONFIG (set these via environment variables) ----
BASE_URL = os.getenv("ADP_BASE_URL", "https://api.adp.com").rstrip("/")
TOKEN = os.getenv("ADP_ACCESS_TOKEN", "").strip()

# mTLS: either provide CERT+KEY, or a single PFX (CERT will work with requests if it's PEM)
CERT_PEM = os.getenv("ADP_MTLS_CERT_PEM", "").strip()   # e.g. C:\path\client.crt
KEY_PEM  = os.getenv("ADP_MTLS_KEY_PEM", "").strip()    # e.g. C:\path\client.key
PFX_PATH = os.getenv("ADP_MTLS_PFX", "").strip()        # optional (requests may not support .pfx directly)
VERIFY   = os.getenv("ADP_VERIFY", "true").strip().lower()  # "true" | "false" | path to CA bundle

META_PATH = "/events/time/v1/data-collection-entries.process/meta" # read-only

def parse_verify(v: str):
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    return v  # treat as CA bundle path

def build_cert():
    # Prefer CERT+KEY PEM pair (most reliable in requests)
    if CERT_PEM and KEY_PEM:
        return (CERT_PEM, KEY_PEM)

    # If you only have PFX: requests typically does NOT use .pfx directly.
    # If you’re currently doing mTLS successfully in python, you probably already have PEM paths.
    if PFX_PATH:
        raise SystemExit(
            "ADP_MTLS_PFX is set, but requests usually can’t use .pfx directly.\n"
            "Use PEM files: set ADP_MTLS_CERT_PEM and ADP_MTLS_KEY_PEM.\n"
            "If you already have a working token script that uses certs, copy its cert settings here."
        )

    raise SystemExit("Missing mTLS cert config. Set ADP_MTLS_CERT_PEM and ADP_MTLS_KEY_PEM.")

def main():
    if not TOKEN:
        raise SystemExit("Missing ADP_ACCESS_TOKEN env var (bearer token).")

    url = f"{BASE_URL}{META_PATH}"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
    }

    cert = build_cert()
    verify = parse_verify(VERIFY)

    try:
        r = requests.get(url, headers=headers, cert=cert, verify=verify, timeout=60)
    except requests.exceptions.SSLError as e:
        raise SystemExit(f"SSL/mTLS error: {e}")
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Request error: {e}")

    print("GET", url)
    print("Status:", r.status_code)

    # Save full response for inspection
    os.makedirs("output", exist_ok=True)
    out_path = os.path.join("output", "clock_punch_meta_response.json")

    try:
        data = r.json()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print("Saved:", out_path)
        # Show a small preview to confirm "response shape"
        print("\nPreview keys:", list(data.keys())[:20])
    except ValueError:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Saved (non-JSON):", out_path)
        print("\nBody preview:\n", r.text[:600])

    # Non-200 guidance
    if r.status_code != 200:
        print("\n--- Troubleshooting quick hints ---")
        if r.status_code == 401:
            print("401 = token invalid/expired or wrong audience/scope.")
        elif r.status_code == 403:
            print("403 = mTLS missing/mismatched OR scopes/permissions denied.")
        elif r.status_code == 404:
            print("404 = endpoint not enabled for your tenant or wrong base/path.")
        else:
            print("See output/clock_punch_meta_response.json for details.")
        sys.exit(2)

if __name__ == "__main__":
    main()