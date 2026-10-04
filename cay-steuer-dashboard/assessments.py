"""Explicit, repeat-safe import of a prepared personal notice package.

Originals and excerpts are inserted into the existing durable data directory.
Notice amounts never create transactions or overwrite year-independent settings.
"""
import base64
import hashlib
import json
from pathlib import Path

A = None
BUNDLE = Path(__file__).parent / 'bescheide-2024'

def bind(core):
    global A
    A = core

def initialize():
    with A.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS assessment_imports (id TEXT PRIMARY KEY, data_json TEXT NOT NULL, imported_at TEXT NOT NULL)')

def manifest():
    path=BUNDLE/'manifest.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None

def status():
    with A.db() as con:
        rows=A.rows(con,'SELECT * FROM assessment_imports ORDER BY imported_at DESC')
        cases=[]
        for row in rows:
            case=json.loads(row['data_json']); case['imported_at']=row['imported_at']
            case['source_changed']=False
            for d in case['documents']:
                current=con.execute('SELECT * FROM documents WHERE id=? AND archived=0',(d['id'],)).fetchone()
                if not current or A.source_hash(dict(current))!=d['source_hash']: case['source_changed']=True
            case['facts']=[dict(f) for fid in case['fact_ids'] if (f:=con.execute('SELECT * FROM memory_facts WHERE id=?',(fid,)).fetchone())]
            case['tasks']=[dict(t) for tid in case['task_ids'] if (t:=con.execute('SELECT * FROM tasks WHERE id=? AND archived=0',(tid,)).fetchone())]
            cases.append(case)
    package=manifest()
    return {'cases':cases,'available':{'id':package['id'],'title':package['title'],'document_count':len(package['documents'])} if package and not any(c['id']==package['id'] for c in cases) else None}

def import_bundle():
    import intelligence
    package=manifest()
    if not package: raise ValueError('Kein vorbereitetes Bescheidpaket vorhanden.')
    # Validate all files before any mutation. Only flat filenames from this bundle.
    prepared=[]
    for item in package['documents']:
        name=item['file']
        if Path(name).name!=name: raise ValueError('Ungültiger Dateiname im Bescheidpaket.')
        raw=(BUNDLE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']: raise ValueError('Bescheidpaket ist beschädigt. Bitte neu entpacken.')
        prepared.append((item,raw))
    created=[]
    try:
        with A.WRITE_LOCK,A.db() as con:
            if con.execute('SELECT 1 FROM assessment_imports WHERE id=?',(package['id'],)).fetchone(): return {'already_imported':True}
            case={'id':package['id'],'title':package['title'],'year':package['year'],'document_date':package['document_date'],'summary':package['summary'],'documents':[],'fact_ids':[],'task_ids':[]}
            ids={}
            for item,raw in prepared:
                r=A.create_document({'title':item['title'],'kind':'Finanzamt' if item['key']!='email' else 'Sonstiges','year':package['year'],
                    'document_date':package['document_date'] if item['key']!='email' else '',
                    'partner':'Finanzamt Stuttgart III' if item['key']!='email' else 'Bisherige Steuerberatung',
                    'filename':item['file'],'file_base64':base64.b64encode(raw).decode(),'body':item['body'],'notes':item['notes']})
                d=dict(con.execute('SELECT * FROM documents WHERE id=?',(r['id'],)).fetchone())
                if not r['duplicate']: created.append(A.DATA/'originale'/d['stored_name'])
                elif not d['body'].strip():
                    A.update_document(d['id'],{**d,'body':item['body'],'notes':d['notes']+'\n'+item['notes']})
                    d=dict(con.execute('SELECT * FROM documents WHERE id=?',(r['id'],)).fetchone())
                if not r['duplicate']:
                    con.execute('UPDATE documents SET extraction_note=? WHERE id=?',('Vorbereiteter Auszug; Original vollständig erhalten. Keine vollständige OCR oder fachliche Freigabe.',d['id']))
                ids[item['key']]=d['id']
                case['documents'].append({'id':d['id'],'title':d['title'],'source_hash':A.source_hash(d)})
            for f in package['facts']:
                result=intelligence.save_fact({'year':f.get('year',package['year']),'title':f['title'],'value':f['value'],'source_id':ids[f['document']],
                    'source_note':f['source_note'],'status':'open'})
                case['fact_ids'].append(result['id'])
            for t in package['tasks']:
                result=A.save_task({'year':t.get('year',package['year']),'title':t['title'],'kind':'Unterlagen','source_id':ids[t['document']],
                    'notes':t['notes'],'source_quote':t.get('quote',''),'prepare_on':A.date.today().isoformat() if t.get('urgent') else '',
                    'due_on':'','due_confirmed':False})
                case['task_ids'].append(result['id'])
            A.insert(con,'assessment_imports',{'id':package['id'],'data_json':A.enc(case),'imported_at':A.now()})
            A.audit(con,'import','assessment',package['id'],after={'documents':len(ids),'facts':len(case['fact_ids']),'tasks':len(case['task_ids'])})
        return {'documents':len(ids),'facts':len(case['fact_ids']),'tasks':len(case['task_ids'])}
    except Exception:
        for path in created: path.unlink(missing_ok=True)
        raise
