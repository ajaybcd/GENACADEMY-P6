"""Local PII boundary: only sanitized text may reach configured receivers."""
from collections import Counter
from functools import lru_cache
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import EmailRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN",
            "IP_ADDRESS", "LOCATION", "IBAN_CODE", "US_PASSPORT", "US_DRIVER_LICENSE"]
THRESHOLD = 0.35


class OfflineEmailRecognizer(EmailRecognizer):
    """Use tldextract's bundled suffix list, with no runtime network fetch."""
    def __init__(self):
        super().__init__()
        import tldextract
        self.extract = tldextract.TLDExtract(cache_dir=None, suffix_list_urls=())

    def validate_result(self, pattern_text):
        return bool(self.extract(pattern_text).fqdn)


class Sanitizer:
    def __init__(self):
        # Explicit local model: do not download a model at request time.
        import spacy
        model = os.environ.get("PRESIDIO_MODEL", "en_core_web_sm")
        if not spacy.util.is_package(model):
            raise RuntimeError("Install the configured spaCy model before starting.")
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": model}],
        })
        self.analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
        self.analyzer.registry.remove_recognizer("EmailRecognizer", language="en")
        self.analyzer.registry.add_recognizer(OfflineEmailRecognizer())
        self.anonymizer = AnonymizerEngine()

    def sanitize(self, text):
        results = self.analyzer.analyze(text=text, language="en", entities=ENTITIES,
                                        score_threshold=THRESHOLD)
        operators = {entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
                     for entity in ENTITIES}
        clean = self.anonymizer.anonymize(text=text, analyzer_results=results,
                                         operators=operators)
        # Never return matched raw strings or original character offsets.
        return {"sanitized_text": clean.text,
                "detections": dict(Counter(r.entity_type for r in results)),
                "language": "en", "threshold": THRESHOLD}


@lru_cache(maxsize=1)
def get_sanitizer():
    return Sanitizer()


class TextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=20000)


app = FastAPI(title="Week 6 — PII Sanitization Gateway", version="1.0.0",
              description="English text prototype. Swagger examples must use synthetic data.")


@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    # FastAPI's default validation output can echo rejected raw input.
    return JSONResponse(status_code=422, content={"detail": "Provide only text: 1–20000 characters."})


def sanitize_or_block(text):
    try:
        return get_sanitizer().sanitize(text)
    except Exception:
        raise HTTPException(503, "Sanitization unavailable; nothing forwarded.") from None


@app.get("/health")
def health():
    sanitize_or_block("Readiness probe.")
    return {"status": "ready", "language": "en"}


@app.post("/sanitize")
def sanitize(body: TextInput):
    return sanitize_or_block(body.text)


def forward(body, setting, destination):
    result = sanitize_or_block(body.text)
    # Receiver URLs are operator configuration, never request-controlled.
    url = os.environ.get(setting)
    if not url:
        raise HTTPException(503, f"{destination} receiver not configured; nothing forwarded.")
    try:
        with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
            response = client.post(url, json={"text": result["sanitized_text"]})
            response.raise_for_status()
    except Exception:
        raise HTTPException(502, "Receiver failed; sanitized content only was attempted.") from None
    # Never echo receiver bodies: they may contain sensitive data or stack traces.
    return {**result, "forwarded_to": destination, "receiver_status": response.status_code}


@app.post("/chat")
def chat(body: TextInput):
    return forward(body, "LLM_RECEIVER_URL", "LLM")


@app.post("/documents")
def documents(body: TextInput):
    return forward(body, "VECTOR_RECEIVER_URL", "vector ingestion")
