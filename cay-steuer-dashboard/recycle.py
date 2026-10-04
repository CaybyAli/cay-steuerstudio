"""Recoverable removal of uploads. Financial rows are never deleted here."""
import hashlib
import json
A=None

def bind(core):
    global A
    A=core

def initialize():
    with A.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS upload_trash (id TEXT PRIMARY KEY,year INTEGER NOT NULL,label TEXT NOT NULL,contents_json TEXT NOT NULL,created_at TEXT NOT NULL,restored_at TEXT)')
        for table in ['documents','bank_imports']:
            cols={r[1] for r in con.execute(f'PRAGMA table_info({table})')}
            for name,typ in [('archived','INTEGER NOT NULL DEFAULT 0'),('trash_id','TEXT')]:
                if name not in cols:con.execute(f'ALTER TABLE {table} ADD COLUMN {name} {typ}')

def items(year):
    with A.db() as con:
        return A.rows(con,'SELECT id,year,label,created_at FROM upload_trash WHERE year=? AND restored_at IS NULL ORDER BY created_at DESC',(year,))

def resolve(con,payload):
    did=payload.get('document_id');iid=payload.get('import_id');jid=payload.get('job_id')
    if sum(bool(v) for v in [did,iid,jid])!=1:raise ValueError('Bitte genau einen Upload auswählen.')
    if jid:
        j=con.execute('SELECT * FROM intake_jobs WHERE id=? AND archived=0',(jid,)).fetchone()
        if not j:raise ValueError('Auswertung nicht gefunden oder bereits entfernt.')
        did=j['document_id'];iid=j['import_id']
    if iid:
        i=con.execute('SELECT * FROM bank_imports WHERE id=? AND archived=0',(iid,)).fetchone()
        if not i:raise ValueError('Import nicht gefunden oder bereits entfernt.')
        did=did or i['statement_document_id']
    docs=[];imports=[];jobs=[]
    if did:
        d=con.execute('SELECT * FROM documents WHERE id=? AND archived=0',(did,)).fetchone()
        if not d:raise ValueError('Dokument nicht gefunden oder bereits entfernt.')
        if con.execute('SELECT 1 FROM transaction_documents td JOIN transactions t ON t.id=td.transaction_id WHERE td.document_id=? AND t.archived=0',(did,)).fetchone() or con.execute('SELECT 1 FROM tasks WHERE source_id=? AND archived=0',(did,)).fetchone():
            raise ValueError('Dieses Dokument ist noch als Beleg oder Aufgabenquelle verknüpft. Bitte zuerst diese Zuordnung bearbeiten.')
        docs=[did];label=d['title'];year=d['year']
        imports=[r['id'] for r in con.execute('SELECT id FROM bank_imports WHERE statement_document_id=? AND archived=0',(did,))]
        jobs=[dict(r) for r in con.execute('SELECT id,state FROM intake_jobs WHERE document_id=? AND archived=0',(did,))]
    elif iid:label=i['filename'];year=i['year']
    else:raise ValueError('Zum Upload wurde kein Original gefunden.')
    if iid and iid not in imports:imports.append(iid)
    for i in imports:
        for r in con.execute('SELECT id,state FROM intake_jobs WHERE import_id=? AND archived=0',(i,)):
            if not any(x['id']==r['id'] for x in jobs):jobs.append(dict(r))
    payments=0
    for i in imports:
        payments+=con.execute('SELECT COUNT(*) FROM transactions t JOIN bank_rows b ON b.id=t.bank_row_id WHERE b.import_id=? AND t.archived=0',(i,)).fetchone()[0]
    content={'documents':sorted(docs),'imports':sorted(imports),'jobs':sorted(jobs,key=lambda x:x['id']),'payments':payments}
    return {'label':label,'year':year,**content,'token':hashlib.sha256(A.enc(content).encode()).hexdigest()}

def preview(payload):
    with A.WRITE_LOCK,A.db() as con:return resolve(con,payload)

def remove(payload):
    with A.WRITE_LOCK,A.db() as con:
        data=resolve(con,payload)
        # UI rechecks the exact effect if a job completed while the dialog was open.
        if payload.get('token') and payload['token']!=data['token']:
            raise ValueError('Der Upload wurde inzwischen weiterbearbeitet. Bitte den Entfernen-Dialog erneut öffnen.')
        tid=A.new_id()
        for table,key in [('documents','documents'),('bank_imports','imports')]:
            for uid in data[key]:con.execute(f'UPDATE {table} SET archived=1,trash_id=? WHERE id=?',(tid,uid))
        for j in data['jobs']:
            con.execute("UPDATE intake_jobs SET archived=1,trash_id=?,run_token=?,state='cancelled',updated_at=? WHERE id=?",(tid,A.new_id(),A.now(),j['id']))
        A.insert(con,'upload_trash',{'id':tid,'year':data['year'],'label':data['label'],'contents_json':A.enc(data),'created_at':A.now()})
        A.audit(con,'trash','upload',tid,after=data)
        return {'ok':True,'id':tid,'payments_preserved':data['payments']}

def restore(payload):
    with A.WRITE_LOCK,A.db() as con:
        row=con.execute('SELECT * FROM upload_trash WHERE id=?',(payload.get('id'),)).fetchone()
        if not row:raise ValueError('Papierkorbeintrag nicht gefunden.')
        if row['restored_at']:return {'ok':True}
        data=json.loads(row['contents_json'])
        for table in ['documents','bank_imports']:
            con.execute(f'UPDATE {table} SET archived=0,trash_id=NULL WHERE trash_id=?',(row['id'],))
        for j in data['jobs']:
            state=j['state'];interrupted=state in {'queued','running'}
            con.execute('UPDATE intake_jobs SET archived=0,trash_id=NULL,state=?,updated_at=? WHERE id=? AND trash_id=?',('error' if interrupted else state,A.now(),j['id'],row['id']))
            if interrupted:con.execute("UPDATE intake_jobs SET error='Vorherige Auswertung wurde beim Entfernen beendet. Bitte erneut starten.',progress='Erneut lesen lassen' WHERE id=?",(j['id'],))
        con.execute('UPDATE upload_trash SET restored_at=? WHERE id=?',(A.now(),row['id']))
        A.audit(con,'restore','upload',row['id'],after={'restored':True})
    return {'ok':True}


class UploadInTrash(ValueError):
    def __init__(self,item,content):
        super().__init__('Dieser Kontoauszug liegt im Papierkorb. Du kannst ihn hier wiederherstellen und weiterbearbeiten.')
        self.details={'kind':'upload_in_trash','trash_id':item['id'],'label':item['label'],'year':item['year'],'payments_preserved':content.get('payments',0)}


def restore_from_upload(tid,payload):
    """Caller matched exact file hash, year and (CSV) account before calling."""
    with A.WRITE_LOCK,A.db() as con:
        item=con.execute('SELECT * FROM upload_trash WHERE id=? AND restored_at IS NULL',(tid,)).fetchone()
        if not item:raise ValueError('Papierkorbeintrag wurde inzwischen geändert. Bitte den Upload erneut öffnen.')
        if payload.get('restore_trash_id')!=tid:raise UploadInTrash(item,json.loads(item['contents_json']))
        restore({'id':tid})



def verify_restored_upload(tid,sha,year,aid,kind):
    """A retried restore request returns the same import after a lost response."""
    with A.db() as con:
        item=con.execute('SELECT * FROM upload_trash WHERE id=? AND restored_at IS NOT NULL',(tid,)).fetchone()
        if item:
            data=json.loads(item['contents_json'])
            if kind=='pdf':
                for did in data['documents']:
                    if con.execute('SELECT 1 FROM documents WHERE id=? AND sha256=? AND year=? AND archived=0',(did,sha,year)).fetchone():return
            else:
                for iid in data['imports']:
                    if con.execute('SELECT 1 FROM bank_imports WHERE id=? AND sha256=? AND year=? AND account_id=? AND archived=0',(iid,sha,year,aid)).fetchone():return
    raise ValueError('Die gewählte Datei, das Konto oder das Jahr hat sich geändert. Bitte erneut hochladen.')
