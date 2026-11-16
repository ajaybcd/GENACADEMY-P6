"""Reproducible synthetic corpus, exact-span scoring and HTTP receiver evidence."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version
import json
import os
from pathlib import Path
import statistics
import threading
import time

from fastapi.testclient import TestClient
from gateway import app, get_sanitizer, THRESHOLD, ENTITIES

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"


def corpus():
    # All identities and contact values are fictional test fixtures.
    positives = [
        ("email", "Email alex@example.com for help.", "EMAIL_ADDRESS", "alex@example.com"),
        ("email", "Write to support@example.org today.", "EMAIL_ADDRESS", "support@example.org"),
        ("email", "Contact jane.doe@example.net.", "EMAIL_ADDRESS", "jane.doe@example.net"),
        ("email", "Use billing+test@example.com.", "EMAIL_ADDRESS", "billing+test@example.com"),
        ("phone", "My phone number is 212-555-0187.", "PHONE_NUMBER", "212-555-0187"),
        ("phone", "Call +1 202-555-0143.", "PHONE_NUMBER", "+1 202-555-0143"),
        ("phone", "Telephone: (415) 555-0123.", "PHONE_NUMBER", "(415) 555-0123"),
        ("card", "Test credit card 4111 1111 1111 1111.", "CREDIT_CARD", "4111 1111 1111 1111"),
        ("card", "Credit card number: 5555555555554444.", "CREDIT_CARD", "5555555555554444"),
        ("ssn", "My social security number is 078-05-1120.", "US_SSN", "078-05-1120"),
        ("ip", "Client IP address is 192.168.1.10.", "IP_ADDRESS", "192.168.1.10"),
        ("ip", "Server IP: 10.0.0.25.", "IP_ADDRESS", "10.0.0.25"),
        ("person", "My name is John Smith.", "PERSON", "John Smith"),
        ("person", "Please contact Jane Doe.", "PERSON", "Jane Doe"),
        ("location", "I live in New York.", "LOCATION", "New York"),
        ("location", "The office is in London.", "LOCATION", "London"),
        ("iban", "Test IBAN: GB82 WEST 1234 5698 7654 32.", "IBAN_CODE", "GB82 WEST 1234 5698 7654 32"),
    ]
    cases = []
    for category, text, entity, value in positives:
        start = text.index(value)
        cases.append({"group": "standard", "category": category, "text": text,
                      "gold": [{"entity": entity, "start": start, "end": start + len(value), "value": value}]})
    mixed = "Contact John Smith at alex@example.com or 212-555-0187."
    cases.append({"group": "standard", "category": "mixed", "text": mixed,
                  "gold": [{"entity": entity, "start": mixed.index(value), "end": mixed.index(value)+len(value), "value": value}
                           for entity,value in [("PERSON","John Smith"),("EMAIL_ADDRESS","alex@example.com"),("PHONE_NUMBER","212-555-0187")]]})
    for text in ["Please summarize this document.", "The order contains three blue notebooks.",
                 "What is the refund policy?", "Total items: 42.", "The meeting is tomorrow.",
                 "Explain how a sorting algorithm works."]:
        cases.append({"group": "negative", "category": "no selected PII", "text": text, "gold": []})
    for text, value in [("Email alex [at] example [dot] com.","alex [at] example [dot] com"),
                        ("Email alex＠example.com.","alex＠example.com"),
                        ("My name is Xzqv Blrpt.","Xzqv Blrpt"),
                        ("My private account alias is blue-falcon-77.","blue-falcon-77")]:
        cases.append({"group": "challenge", "category": "out-of-distribution or unsupported", "text": text,
                      "gold": [{"entity": "SENSITIVE_CHALLENGE", "start": text.index(value), "end": text.index(value)+len(value), "value": value}]})
    for i, case in enumerate(cases, 1): case["id"] = f"c{i:02d}"
    return cases


def main():
    OUT.mkdir(exist_ok=True)
    sanitizer = get_sanitizer()
    rows=[]
    for case in corpus():
        started=time.perf_counter()
        result=sanitizer.sanitize(case["text"])
        ms=(time.perf_counter()-started)*1000
        detections=sanitizer.analyzer.analyze(text=case["text"], language="en", entities=ENTITIES, score_threshold=THRESHOLD)
        gold={(x["entity"],x["start"],x["end"]) for x in case["gold"]}
        actual={(x.entity_type,x.start,x.end) for x in detections}
        remaining=[x["value"] for x in case["gold"] if x["value"] in result["sanitized_text"]]
        rows.append({**case,**result,"latency_ms":round(ms,2),"tp":len(gold&actual),"fp":len(actual-gold),"fn":len(gold-actual),
                     "gold_count":len(gold),"remaining_count":len(remaining),"remaining_values":remaining,
                     "predicted": [{"entity":e,"start":s,"end":t} for e,s,t in sorted(actual)],
                     "case_pass": len(remaining)==0 and (bool(gold) or not actual)})
    standard=[r for r in rows if r["group"]!="challenge"]
    tp=sum(r["tp"] for r in standard);fp=sum(r["fp"] for r in standard);fn=sum(r["fn"] for r in standard)
    gold_total=sum(r["gold_count"] for r in standard)
    metrics={"cases":len(rows),"standard_and_negative_cases":len(standard),"challenge_cases":len(rows)-len(standard),
             "tp":tp,"fp":fp,"fn":fn,"exact_span_precision":tp/(tp+fp) if tp+fp else 0,
             "exact_span_recall":tp/(tp+fn) if tp+fn else 0,"standard_gold_values":gold_total,
             "standard_remaining_values":sum(r["remaining_count"] for r in standard),
             "challenge_remaining_values":sum(r["remaining_count"] for r in rows if r["group"]=="challenge"),
             "case_pass_count":sum(r["case_pass"] for r in rows),
             "median_sanitize_ms":round(statistics.median(r["latency_ms"] for r in rows),2)}
    received=[]
    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append({"path": self.path,"payload":payload})
            self.send_response(200);self.end_headers();self.wfile.write(b'{"accepted":true}')
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(("127.0.0.1",0),Receiver)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    old={k:os.environ.get(k) for k in ["LLM_RECEIVER_URL","VECTOR_RECEIVER_URL"]}
    statuses=[]
    try:
        base=f"http://127.0.0.1:{server.server_port}"
        os.environ["LLM_RECEIVER_URL"]=base+"/llm"
        os.environ["VECTOR_RECEIVER_URL"]=base+"/vector-ingestion"
        with TestClient(app) as client:
            for route in ["/chat","/documents"]:
                response=client.post(route,json={"text":"Email alex@example.com for help."})
                statuses.append(response.status_code)
                assert response.status_code==200
        assert len(received)==2
        assert all("alex@example.com" not in json.dumps(r) for r in received)
        assert all("<EMAIL_ADDRESS>" in r["payload"]["text"] for r in received)
    finally:
        server.shutdown();server.server_close();thread.join()
        for k,v in old.items():
            if v is None: os.environ.pop(k,None)
            else: os.environ[k]=v
    evidence={"generated_utc":datetime.now(timezone.utc).isoformat(),"synthetic_only":True,
              "model":os.environ.get("PRESIDIO_MODEL","en_core_web_sm"),"threshold":THRESHOLD,
              "versions":{p:version(p) for p in ["presidio-analyzer","presidio-anonymizer","spacy","en-core-web-sm"]},
              "metrics":metrics,"http_forwarding":{"receiver":"local test double; no live LLM or vector database", "statuses":statuses,"received":received},"cases":rows}
    (OUT/"evaluation.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print(json.dumps(metrics,indent=2))
    print("Local HTTP receivers verified: sanitized text only, both routes.")


if __name__=="__main__":main()
