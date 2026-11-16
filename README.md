# Week 6 PII Masking and Data Sanitization Gateway

Microsoft Presidio detects selected PII in English text and replaces it with entity labels before forwarding to an LLM receiver or vector-ingestion receiver. The Streamlit interface demonstrates detection locally within the app server. No API key is needed.

## Interactive demo

[Open the hosted Streamlit app](https://genacademy-p6-pii-gateway.streamlit.app/).

Use **Run one example per PII type** to execute ten category examples. All ten complete values were removed in the saved run, but the SSN fixture was classified as a phone number. The passport example also redacted the country abbreviation. Clean text stayed unchanged; a disguised email was only partially masked. Exact inputs and outputs are in `outputs/entity_examples.json` and the summary appendix.

**Note on disguised values:** these are deliberate challenge examples. The full-width email and private alias were not masked; the bracketed email was only partially masked. These results show current detection gaps, not successful redactions. “Challenge values fully visible: 2” counts completely exposed values and does not include the additional partially exposed email.

## Submission files

- [Project summary and tested examples PDF](outputs/project_summary.pdf)
- [Editable project summary Word document](outputs/project_summary.docx)
- [Summary voiceover](outputs/voiceover/presentation_voiceover.wav)
- [Demo voiceover](outputs/voiceover/demo_voiceover.wav)
- [Voiceover transcript](outputs/voiceover_script.txt)
- [Twenty-line summary](outputs/project_summary_20_lines.txt)
- [Presentation](outputs/presidio_gateway_presentation.pptx)
- [Evaluation workbook](outputs/presidio_evaluation.xlsx)
- [Executed evidence notebook](presidio_gateway_evaluation.ipynb)
- [Main evaluation evidence](outputs/evaluation.json)
- [Ten category examples](outputs/entity_examples.json)

Audio is computer-generated Windows speech, not the author's recorded voice. No video is included. The PDF pages and slide renders were visually reviewed. Native Word pagination could not be verified because the packaged LibreOffice renderer is unavailable. The PDF is the visually checked reading copy. Presentation structure, font policy, geometry and first-party import checks passed; native desktop PowerPoint playback was not tested.

Streamlit entrypoint: `app.py`. Choose an example, edit the text, and click **Detect and redact**. Use fictional data only. On Community Cloud, the original text is processed on the hosting server; redaction does not happen inside your browser. The app does not write user text to files, send it to external models, or retain a reversible mapping. Hosting infrastructure may have its own logging and retention policies.

## Windows quick start

Use Python 3.12. In PowerShell, open this project's folder:

```powershell
.\setup.ps1
.\run.ps1
```

To see the first code example:

```powershell
.\.venv\Scripts\python.exe demo.py
```

Example input:

```text
Please contact Alex Johnson at alex.johnson@example.com or 212-555-0187.
```

Output with the tested model:

```text
Please contact <PERSON> at <EMAIL_ADDRESS> or <PHONE_NUMBER>.
```

## How to use Presidio

1. **AnalyzerEngine** identifies entities, character positions and confidence scores. Rules detect structured values; the spaCy model helps identify names and locations.
2. **AnonymizerEngine** takes those detections and applies replacement operators. This project uses `<ENTITY_TYPE>` placeholders. Presidio also offers other operators, including removing text and masking characters.
3. The gateway passes only the sanitized text field to a server-configured receiver. Sanitizer errors and missing receiver configuration stop forwarding.

`gateway.py` keeps the policy on the server: English, threshold 0.35, ten selected entity types, and a maximum text length of 20,000 characters. The model is `en_core_web_sm` 3.8.0, chosen for a small demonstration deployment. The email recognizer uses the bundled public suffix snapshot to avoid network downloads during inference.

## API

```powershell
.\.venv\Scripts\python.exe -m uvicorn gateway:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for interactive API examples.

| Route | Purpose |
| --- | --- |
| `GET /health` | Loads the sanitizer and checks readiness |
| `POST /sanitize` | Returns sanitized text and detection counts |
| `POST /chat` | Sends sanitized text to `LLM_RECEIVER_URL` |
| `POST /documents` | Sends sanitized text to `VECTOR_RECEIVER_URL` |

Each POST accepts only `{"text":"your synthetic example"}`. Extra fields are rejected so metadata, chat history and alternate prompt fields cannot bypass this interface. Receiver URLs are environment variables controlled by the operator. Redirects are disabled. Errors omit request text, receiver bodies and stack traces.

**Receiver contract:** each receiver accepts a POST with `{"text":"sanitized content"}` and returns a successful HTTP status. The LLM receiver is an adapter that makes the actual model call. The vector receiver must embed and store this sanitized text. This prototype does not implement provider-specific adapters, embeddings, a vector database, authentication or provider responses. Its Streamlit UI calls the sanitizer directly and does not expose forwarding controls.

## Measured results

The evaluation contains 28 synthetic cases: 18 standard PII cases, six negative cases and four challenge cases. The 24 standard/negative cases have 20 labeled PII values. Exact entity-and-span precision and recall are both 95% (19 true positives, one false positive and one false negative). All 20 standard values disappeared as complete strings after replacement. Four challenge cases retained two complete sensitive strings.

Span accuracy and string-removal checks answer different questions: a broad replacement can remove the complete value while still having an incorrect entity boundary. Neither metric establishes production privacy, semantic anonymity or performance on unseen data. Challenges are excluded from the standard precision/recall denominator and are reported separately, not hidden.

`outputs/evaluation.json` contains the synthetic corpus, gold annotations, predictions, timestamps, versions, raw counts, local timings and HTTP receiver evidence. Both forwarding routes were exercised against real local HTTP test receivers with Presidio active. No live LLM or vector database was contacted. Six contract/failure tests use a stub sanitizer to isolate gateway behavior.

```powershell
.\.venv\Scripts\python.exe -m pytest test_gateway.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe evaluate.py
```

`requirements-lock.txt` records the tested Windows environment. `requirements.txt` is the portable installation input, including the English model wheel. Cloud Linux transitive versions can differ.

## Deployment

In Streamlit Community Cloud, choose `ajaybcd/GENACADEMY-P6`, branch `main`, entrypoint `app.py`, and Python **3.12**. No secrets are required. The demonstration is for synthetic text only. Keep repository and app access settings under the account owner's control.

## Limits and production work

Names, addresses, disguised values and unfamiliar identifiers can be missed. Date/time, generic URLs, API keys and many country-specific IDs are outside the selected policy. PDF/OCR, image, binary, nested metadata and multi-message chat sanitization are not implemented. Do not treat this as prompt-injection protection, access control, compliance certification or guaranteed anonymization.

Before production, add authenticated access, TLS and request-size enforcement at the edge, rate limits, timeouts, operational monitoring without raw text, receiver authentication, egress restrictions, stronger/domain-specific recognizers and a representative reviewed corpus. Prevent direct unsanitized writes to the model or embedding pipeline. Evaluate utility loss and false positives, and sanitize retrieved/output text separately if required by the system design.

## References

- [Presidio installation](https://microsoft.github.io/presidio/installation/)
- [Presidio Analyzer](https://microsoft.github.io/presidio/analyzer/)
- [Presidio Anonymizer](https://microsoft.github.io/presidio/anonymizer/)
- [Supported entities](https://microsoft.github.io/presidio/supported_entities/)

Project artifacts use synthetic fixtures only. Voiceover is computer-generated narration, with no video.
