"""One synthetic example per selected PII category, plus boundary demonstrations."""
import json
from pathlib import Path
from gateway import get_sanitizer

EXAMPLES = [
    ("PERSON", "My name is John Smith.", "John Smith"),
    ("EMAIL_ADDRESS", "Email alex@example.com for help.", "alex@example.com"),
    ("PHONE_NUMBER", "My phone number is 212-555-0187.", "212-555-0187"),
    ("CREDIT_CARD", "Test credit card: 4111 1111 1111 1111.", "4111 1111 1111 1111"),
    ("US_SSN", "My social security number is 078-05-1120.", "078-05-1120"),
    ("IP_ADDRESS", "Client IP address is 192.168.1.10.", "192.168.1.10"),
    ("LOCATION", "I live in New York.", "New York"),
    ("IBAN_CODE", "Test IBAN: GB82 WEST 1234 5698 7654 32.", "GB82 WEST 1234 5698 7654 32"),
    ("US_PASSPORT", "My US passport number is 123456789.", "123456789"),
    ("US_DRIVER_LICENSE", "My driver license number is D1234567.", "D1234567"),
]


def main():
    s=get_sanitizer();rows=[]
    for entity,text,value in EXAMPLES:
        result=s.sanitize(text)
        rows.append({"expected_entity":entity,"input":text,**result,
                     "expected_type_detected":entity in result["detections"],
                     "complete_value_removed":value not in result["sanitized_text"]})
    clean="Please summarize the refund policy."
    challenge="Email alex [at] example [dot] com."
    evidence={"synthetic_only":True,"entity_examples":rows,"clean_text":s.sanitize(clean),"challenge":s.sanitize(challenge)}
    dest=Path(__file__).parent/'outputs/entity_examples.json'
    dest.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':main()
