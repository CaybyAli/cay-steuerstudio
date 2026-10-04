import json
import sys
import time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import app
import taxprofile
app.DATA=Path(sys.argv[sys.argv.index('--data-dir')+1]);app.initialize()
if not app.state()['transactions']:
    taxprofile.save({'year':2025,'vat_status':'regular','taxation':'cash','filing_status':'open','source_note':'Synthetische Testdaten'})
    for direction,amount,name,title,body in [('expense','119,00','Studio Tools · Test','Jahreslizenz Schnittsoftware','Rechnung 2025: Software netto 100,00 EUR, USt 19,00 EUR, brutto 119,00 EUR.'),('income','238,00','Videoplattform · Test','Auszahlung Februar','Abrechnung 2025: 200,00 EUR netto, 38,00 EUR USt, 238,00 EUR bezahlt.'),('expense','1190,00','Kameratechnik · Test','Kamera für Videoproduktion','Rechnung 2025: Kamera netto 1000,00 EUR; USt 190,00 EUR; brutto 1190,00 EUR.')]:
        d=app.create_document({'year':2025,'title':title+' · Rechnung','body':body,'kind':'Rechnung'})['id']
        app.save_transaction({'direction':direction,'amount':amount,'paid_on':'2025-02-03','partner':name,'title':title,'scope':'business','document_ids':[d],'data_checked':True})
    for i in range(30):app.save_transaction({'direction':'expense','amount':'9,00','paid_on':f'2025-{i%12+1:02d}-10','partner':f'Testanbieter {i+1:02d}','title':'Gebühr · synthetischer Test','scope':'business'})
    for i in range(73):app.save_transaction({'direction':'expense','amount':'7,00','paid_on':f'2025-{i%12+1:02d}-15','partner':f'Privatzahlung Test {i+1:02d}','title':'Privat','scope':'private'})
MODELS=['qwen3.8:27b','gemma4:31b','gpt-oss:20b']
failmarker=app.DATA/'qa-failed-once'
def fake(path,payload=None,timeout=5):
    if path=='/api/tags':return {'models':[{'name':m,'size':100,'digest':'synthetic-'+m} for m in MODELS]}
    raw=json.loads(payload['messages'][1]['content'])
    with (app.DATA/'qa-calls.jsonl').open('a') as f:f.write(json.dumps({'model':payload['model'],'kind':'document' if 'Abschnitt' in raw else 'transaction' if 'Zahlung' in raw else 'chat'})+'\n')
    if 'Auftrag' in raw and payload['model']==MODELS[1] and not failmarker.exists():
        failmarker.write_text('simulated connection interrupted');raise OSError('Synthetic connection interrupted')
    time.sleep(.01)
    if 'Abschnitt' in raw:obj={'note':'Textabschnitt gelesen. Jahresangabe und Originalrechnung vor Übernahme prüfen.','quote':raw['Abschnitt']['text'][:80]}
    elif 'Zahlung' in raw:
        t=raw['Zahlung'];camera='Kamera' in t['title'];software='Jahreslizenz' in t['title'];income=t['direction']=='income'
        obj={'position':'asset' if camera else '15' if income else '50' if software else '49','vat':'190,00' if camera else '38,00' if income else '19,00' if software else None,'note':'Synthetischer KI-Vorschlag. Beleg und betrieblichen Zweck prüfen.','question':'' if camera or software or income else 'Liegt eine Rechnung mit gesonderter Umsatzsteuer vor?'}
    elif 'buchungen' in raw:obj={'checks':[{'ref':t['ref'],'status':'no_issue','note':''} for t in raw['buchungen']]}
    else:obj={'answer':'Deine EÜR-Frage bleibt eine freie Frage. Im EÜR-Arbeitsbereich lassen sich die bestätigten Ansätze berechnen.','missing':[], 'conflicts':[], 'citations':[], 'tasks':[]}
    return {'done':True,'done_reason':'stop','message':{'content':json.dumps(obj)}}
app.ollama=fake
raise SystemExit(app.main())
