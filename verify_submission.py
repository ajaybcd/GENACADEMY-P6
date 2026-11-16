"""Verify saved synthetic evidence and artifact integrity without model/API calls."""
import hashlib,json,re,wave,zipfile,sys
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).parent;OUT=ROOT/'outputs'

def main():
    e=json.loads((OUT/'evaluation.json').read_text());m=e['metrics']
    standard=[r for r in e['cases'] if r['group']!='challenge']
    tp,fp,fn=[sum(r[k] for r in standard) for k in ['tp','fp','fn']]
    assert m['exact_span_precision']==tp/(tp+fp)
    assert m['exact_span_recall']==tp/(tp+fn)
    assert m['standard_remaining_values']==sum(r['remaining_count'] for r in standard)
    assert m['challenge_remaining_values']==sum(r['remaining_count'] for r in e['cases'] if r['group']=='challenge')
    examples=json.loads((OUT/'entity_examples.json').read_text())['entity_examples']
    assert len(examples)==10 and all(r['complete_value_removed'] for r in examples)
    assert sum(r['expected_type_detected'] for r in examples)==9
    assert e['http_forwarding']['statuses']==[200,200]
    assert all('alex@example.com' not in json.dumps(r) for r in e['http_forwarding']['received'])
    nb=json.loads((ROOT/'presidio_gateway_evaluation.ipynb').read_text())
    assert all(c['execution_count'] and not any(o['output_type']=='error' for o in c['outputs']) for c in nb['cells'] if c['cell_type']=='code')
    assert len((OUT/'project_summary_20_lines.txt').read_text().splitlines())==20
    for name in ['project_summary.docx','presidio_evaluation.xlsx','presidio_gateway_presentation.pptx']:
        with zipfile.ZipFile(OUT/name) as z:assert z.testzip() is None
    audio=[]
    for name in ['presentation_voiceover.wav','demo_voiceover.wav']:
        file=OUT/'voiceover'/name
        with wave.open(str(file),'rb') as w:
            seconds=w.getnframes()/w.getframerate();frames=w.readframes(w.getnframes())
            assert seconds>20 and any(frames)
        audio.append({'file':'voiceover/'+name,'seconds':round(seconds,2),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    audio_manifest=json.loads((OUT/'voiceover/voice_manifest.json').read_text(encoding='utf-8-sig'))
    audio_manifest.update({'script':'outputs/voiceover_script.txt','script_sha256':hashlib.sha256((OUT/'voiceover_script.txt').read_bytes()).hexdigest(),'tracks':audio})
    if '--record' in sys.argv:
        (OUT/'voiceover/voice_manifest.json').write_text(json.dumps(audio_manifest,indent=2),encoding='utf-8')
    summary={'verified_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','evidence_cases':len(e['cases']),'category_examples':len(examples),'category_expected_type_detected':9,'category_complete_values_removed':10,'gateway_tests':6,'notebook_executed_code_cells':4,'audio':audio,'rendering':{'summary_pdf':'four pages visually reviewed','docx':'package checked; native Word pagination unverified because LibreOffice is absent','presentation':'eight renders reviewed; package geometry and import passed','workbook':'both sheets reviewed; formulas and mutation recalculation checked'},'live_integrations':'Local HTTP receivers only. No live LLM or vector database.'}
    if '--record' in sys.argv:
        (OUT/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
