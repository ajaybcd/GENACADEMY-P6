"""Local teaching UI. User text stays in process; no external calls."""
import streamlit as st
from gateway import get_sanitizer, ENTITIES, THRESHOLD
import json
from pathlib import Path
from examples import EXAMPLES

st.set_page_config(page_title="Week 6 | PII Gateway", page_icon="🛡️", layout="wide")
st.title("PII Masking & Data Sanitization Gateway")
st.caption("Week 6 · Microsoft Presidio · local English-language demonstration")
st.info("Use synthetic examples only. Detection can miss PII. This demo does not call an LLM or vector database. On this hosted app, text is processed on the Streamlit server.")
examples = {
    "Name, email and phone": "Please contact Alex Johnson at alex.johnson@example.com or 212-555-0187.",
    "Credit card": "Test credit card: 4111 1111 1111 1111.",
    "IP address": "Client IP address is 192.168.1.10.",
    "No PII": "Please summarize the refund policy.",
    "Challenge: disguised email": "Email alex [at] example [dot] com.",
    "Challenge: full-width email": "Email alex＠example.com.",
    "Challenge: private alias": "My private account alias is blue-falcon-77.",
}
for entity, sample, value in EXAMPLES:
    examples[entity.replace("_", " ").title()] = sample
chosen = st.selectbox("Choose an example", list(examples))
if chosen.startswith("Challenge:"):
    st.warning("Disguised values deliberately test detection gaps. The full-width email and private alias were not masked in our saved tests; the bracketed email was only partially masked. These are observed misses, not successful redactions.")
text = st.text_area("Text to sanitize", value=examples[chosen], key="input_"+chosen, height=150, max_chars=20000)
if st.button("Detect and redact", type="primary"):
    if not text.strip():
        st.warning("Enter some text first.")
    else:
        try:
            result = get_sanitizer().sanitize(text)
        except Exception:
            st.error("Presidio could not start. Run setup.ps1 to install the model. Nothing was forwarded.")
        else:
            st.subheader("Sanitized text")
            st.code(result["sanitized_text"], language=None)
            st.subheader("Detected entity counts")
            st.json(result["detections"])
            st.caption("Counts are detector candidates before overlap resolution; replacements can be fewer.")
            st.download_button("Download sanitized text", result["sanitized_text"], "sanitized.txt")
if st.button("Run one example per PII type"):
    try:
        sanitizer = get_sanitizer()
        checks = []
        for entity, sample, value in EXAMPLES:
            result = sanitizer.sanitize(sample)
            checks.append({"Expected type":entity, "Synthetic input":sample,
                           "Sanitized output":result["sanitized_text"],
                           "Expected type detected":entity in result["detections"],
                           "Complete value removed":value not in result["sanitized_text"]})
        st.subheader("One example per PII type")
        st.dataframe(checks, hide_index=True, width="stretch")
        st.caption("Removal and correct classification are separate checks. These examples are demonstrations, not a held-out test set.")
    except Exception:
        st.error("Example run failed. Nothing was forwarded.")
with st.expander("How the gateway works"):
    st.write("Input → Presidio Analyzer → entity placeholders → configured LLM or vector-ingestion receiver")
    st.write(f"Server policy: English; threshold {THRESHOLD}. Categories: {', '.join(ENTITIES)}.")
    st.write("Use the separate API to test forwarding. Missing receivers and sanitizer errors block forwarding.")
with st.expander("Measured evaluation and limitations"):
    evidence = Path(__file__).parent / "outputs/evaluation.json"
    if evidence.exists():
        saved = json.loads(evidence.read_text(encoding="utf-8"))
        metrics = saved["metrics"]
        a,b,c = st.columns(3)
        a.metric("Exact-span precision", f'{metrics["exact_span_precision"]:.0%}')
        b.metric("Exact-span recall", f'{metrics["exact_span_recall"]:.0%}')
        c.metric("Challenge values fully visible", metrics["challenge_remaining_values"])
        st.write("Scores use 24 synthetic standard/negative cases; four challenge cases are reported separately. They are not a production guarantee.")
        st.warning("The 2 means two difficult examples were NOT masked: the full-width email and the private alias. These are observed detector misses. Another disguised email was only partially masked, so this count is not a complete privacy-risk measure.")
        st.dataframe([{"Synthetic challenge":r["text"],"Sanitized output":r["sanitized_text"],
                       "Complete value still visible":bool(r["remaining_count"])}
                      for r in saved["cases"] if r["group"]=="challenge"],hide_index=True,width="stretch")
    st.write("English only. No OCR, files, secrets detection, reversible mapping, live provider adapter, authentication or production rate limiting. The server sees the original text; do not enter private information into this public demonstration.")
