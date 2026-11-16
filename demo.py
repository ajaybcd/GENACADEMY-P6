"""First Presidio example. Synthetic input only; no LLM or database call."""
import json
from gateway import get_sanitizer

TEXT = "Please contact Alex Johnson at alex.johnson@example.com or 212-555-0187."

if __name__ == "__main__":
    print("BEFORE (synthetic example):", TEXT)
    print("AFTER:", json.dumps(get_sanitizer().sanitize(TEXT), indent=2))
