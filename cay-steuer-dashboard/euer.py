"""Explicit, cent-exact EÜR working papers. No inferred tax elections or filing."""
import csv
import hashlib
import io
import json
import re
from decimal import Decimal, ROUND_HALF_UP
import taxprofile

A = None
SOURCE = 'https://www.elster.de/elsterweb/helpGlobal?themaGlobal=help_euer_ufa_77_2025'
# Selected ordinary positions only. Subtotals and informational subfields are never added twice.
INCOME = {'12':'Kleinunternehmer: Betriebseinnahmen brutto', '15':'Umsatzsteuerpflichtige Betriebseinnahmen netto',
 '16':'Umsatzsteuerfreie / nicht steuerbare Betriebseinnahmen', '17':'Vereinnahmte Umsatzsteuer',
 '18':'Umsatzsteuererstattungen vom Finanzamt', '19':'Veräußerung / Entnahme von Anlagevermögen',
 '20':'Private Kfz-Nutzung', '21':'Sonstige Sach-, Nutzungs- und Leistungsentnahmen'}
EXPENSE = {'27':'Waren, Rohstoffe und Hilfsstoffe', '29':'Bezogene Fremdleistungen', '30':'Personalaufwendungen',
 '31':'AfA auf unbewegliche Wirtschaftsgüter', '32':'AfA auf immaterielle Wirtschaftsgüter', '33':'AfA auf bewegliche Wirtschaftsgüter',
 '36':'Geringwertige Wirtschaftsgüter (GWG)', '38':'Restbuchwert ausgeschiedener Wirtschaftsgüter',
 '39':'Miete / Pacht für Geschäftsräume', '40':'Doppelte Haushaltsführung', '41':'Sonstige Grundstücksaufwendungen',
 '43':'Telekommunikation', '44':'Übernachtung und Reisenebenkosten', '45':'Fortbildung', '46':'Rechts-, Steuerberatung und Buchführung',
 '47':'Miete / Leasing beweglicher Wirtschaftsgüter', '48':'Erhaltungsaufwand beweglicher Wirtschaftsgüter',
 '49':'Beiträge, Gebühren und Versicherungen', '50':'EDV', '51':'Arbeitsmittel / Bürobedarf', '52':'Abfallbeseitigung',
 '53':'Verpackung und Transport', '54':'Werbung', '55':'Schuldzinsen für Anlagevermögen', '56':'Übrige Schuldzinsen',
 '57':'Gezahlte abziehbare Vorsteuer', '58':'Gezahlte Umsatzsteuer an das Finanzamt', '60':'Sonstige unbeschränkt abziehbare Betriebsausgaben',
 '62':'Geschenke: abziehbarer Teil', '63':'Bewirtung: abziehbarer Teil', '64':'Verpflegungsmehraufwendungen',
 '65':'Häusliches Arbeitszimmer / Jahrespauschale', '66':'Tagespauschale für häusliche Tätigkeit',
 '67':'Sonstige beschränkt abziehbare Betriebsausgaben'}
POSITIONS = {k:{'code':k,'label':v,'kind':'income' if k in INCOME else 'expense'} for k,v in {**INCOME,**EXPENSE}.items()}
BANK_POSITIONS = set(POSITIONS)-{'17','20','21','31','32','33','38','57','64','65','66'}
CHECKS = {'records':'Alle betrieblichen Konten, Barzahlungen und privat bezahlten Betriebsausgaben abgeglichen',
 'assets':'Anlageverzeichnis und AfA für dieses Jahr anhand der Anlagen geprüft',
 'noncash':'PR-Samples, Sachentnahmen und Nutzungseinlagen geprüft',
 'timing':'Jahreswechsel, regelmäßig wiederkehrende Zahlungen und Korrekturen geprüft',
 'extras':'Entnahmen / Einlagen, Schuldzinsen und weitere Gewinnkorrekturen gesondert geprüft'}

def bind(core):
    global A
    A = core

def initialize():
    with A.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS euer_allocations (tx_id TEXT PRIMARY KEY, year INTEGER NOT NULL, payload TEXT NOT NULL, source_hash TEXT NOT NULL, updated_at TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS euer_entries (id TEXT PRIMARY KEY, year INTEGER NOT NULL, payload TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS euer_reviews (year INTEGER PRIMARY KEY, payload TEXT NOT NULL, source_hash TEXT NOT NULL, updated_at TEXT NOT NULL)')

def digest(obj):
    return hashlib.sha256(A.enc(obj).encode()).hexdigest()

def amount(value, signed=False):
    raw=A.clean(value,30)
    pattern=r'-?' if signed else ''
    if not re.fullmatch(pattern+r'(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?',raw):
        # Dot decimals allowed only when unambiguously one/two decimal places.
        if not re.fullmatch(pattern+r'\d+\.\d{1,2}',raw):
            raise ValueError('Betrag bitte als 0,00 oder 1.234,56 eingeben; höchstens zwei Nachkommastellen.')
        number=Decimal(raw)
    else:
        number=Decimal(raw.replace('.','').replace(',','.'))
    cents=int(number*100)
    if abs(cents)>99999999999:raise ValueError('Betrag außerhalb des unterstützten Bereichs.')
    return cents

def eur(cents):
    return ('-' if cents<0 else '')+str(abs(cents)//100)+','+str(abs(cents)%100).zfill(2)

def percent(value):
    if isinstance(value,bool) or not re.fullmatch(r'\d{1,3}',str(value)) or not 0<=int(value)<=100:
        raise ValueError('Anteil muss eine ganze Zahl von 0 bis 100 sein.')
    return int(value)

def scaled(cents,share):
    return int((Decimal(cents)*Decimal(share)/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def supported(year):
    if year!=2025:raise ValueError('Die EÜR-Zuordnung ist für das amtliche Formular 2025 eingerichtet. Andere Jahre benötigen eine eigene geprüfte Zuordnung.')

def source_hash(tx,docs,year):
    return digest({'tx':tx,'documents':[(d['id'],A.source_hash(d)) for d in docs if d['id'] in tx['document_ids']],
                   'profile':taxprofile.get(year)})

def allocation_row(tx,docs,stored=None):
    payload=json.loads(stored['payload']) if stored else None
    target=stored['year'] if stored else int(tx['paid_on'][:4])
    current=source_hash(tx,docs,target)
    excluded=tx['scope'] in {'private','transfer'} and not stored
    stale=bool(stored and stored['source_hash']!=current)
    return {**tx,'allocation':payload,'target_year':target,'source_hash':current,
            'revision':digest(dict(stored)) if stored else '', 'stale':stale,
            'status':'stale' if stale else 'confirmed' if stored else 'excluded' if excluded else 'open'}

def rows(year,data=None):
    data=data or A.state()
    with A.db() as con:stored={r['tx_id']:dict(r) for r in con.execute('SELECT * FROM euer_allocations')}
    result=[]
    for tx in sorted(data['transactions'],key=lambda t:(t['paid_on'],t['id'])):
        saved=stored.get(tx['id'])
        if int(tx['paid_on'][:4])==year or saved and saved['year']==year:
            result.append(allocation_row(tx,data['documents'],saved))
    return result

def check_revision(payload,actual):
    if payload.get('revision','')!=actual:raise ValueError('Der Datensatz wurde inzwischen geändert. Ansicht neu laden und erneut prüfen.')

def save_allocation(payload):
    year=A.valid_year(payload.get('year'));supported(year)
    with A.WRITE_LOCK,A.db() as con:
        data=A.state();tx=next((t for t in data['transactions'] if t['id']==payload.get('tx_id')),None)
        if not tx:raise ValueError('Aktive Zahlung nicht gefunden.')
        old=con.execute('SELECT * FROM euer_allocations WHERE tx_id=?',(tx['id'],)).fetchone()
        check_revision(payload,digest(dict(old)) if old else '')
        if payload.get('source_hash')!=source_hash(tx,data['documents'],year):
            raise ValueError('Zahlung, Beleg oder Steuerprofil wurde geändert. Bitte neu öffnen und prüfen.')
        if payload.get('confirmed') is not True:raise ValueError('Zuordnung bitte ausdrücklich bestätigen.')
        pos=A.clean(payload.get('position'),20)
        if pos not in BANK_POSITIONS|{'asset','exclude'}:raise ValueError('Bitte eine unterstützte EÜR-Position auswählen.')
        note=A.clean(payload.get('note'),4000)
        if not note:raise ValueError('Bitte Beleggrundlage / Begründung angeben.')
        if abs(year-int(tx['paid_on'][:4]))>1:raise ValueError('Abweichendes EÜR-Jahr kann nur ein Nachbarjahr sein.')
        share=percent(payload.get('business_percent'))
        rate=percent(payload.get('deductible_percent'))
        vat=amount(payload.get('vat',''))
        gross=scaled(tx['amount_cents'],share)
        if vat>gross:raise ValueError('Abziehbare / vereinnahmte Umsatzsteuer darf den betrieblichen Zahlungsanteil nicht übersteigen.')
        if pos in {'12','16','18','58','exclude'} and vat:raise ValueError('Für diese Position Umsatzsteuer nicht nochmals abspalten (0,00 eintragen).')
        if pos=='exclude' and (share or vat):raise ValueError('Bei Ausschluss den betrieblichen Anteil auf 0 setzen.')
        if pos!='exclude' and not share:raise ValueError('Für einen betrieblichen Ansatz einen Anteil über 0 wählen.')
        if pos=='asset' and tx['direction']!='expense':raise ValueError('Anschaffung ist nur bei einer Ausgabe möglich.')
        if pos in INCOME and rate!=100:raise ValueError('Einnahmen werden nicht mit einem Betriebsausgaben-Abzugsanteil gekürzt.')
        if taxprofile.get(year)['vat_status']=='small' and (vat or pos=='15'):
            raise ValueError('Die Zuordnung passt nicht zum gespeicherten Kleinunternehmerstatus. Jahresprofil und Sachverhalt zuerst prüfen.')
        if pos=='asset' and rate!=100:raise ValueError('Anschaffungen werden über die separat geprüfte AfA berücksichtigt; hier den Abzugsanteil auf 100 setzen.')
        if pos=='63' and rate!=70:raise ValueError('Geschäftlich veranlasste Bewirtung: hier 70 % des betrieblichen Betrags ohne abziehbare Vorsteuer; Sonderfälle gesondert prüfen.')
        value={'position':pos,'business_percent':share,'deductible_percent':rate,'vat_cents':vat,'note':note,'confirmed':True}
        con.execute('INSERT INTO euer_allocations VALUES (?,?,?,?,?) ON CONFLICT(tx_id) DO UPDATE SET year=excluded.year,payload=excluded.payload,source_hash=excluded.source_hash,updated_at=excluded.updated_at',
                    (tx['id'],year,A.enc(value),source_hash(tx,data['documents'],year),A.now()))
        A.audit(con,'update','euer_allocation',tx['id'],dict(old) if old else None,value)
    return {'ok':True}

def entries(year):
    with A.db() as con:items=A.rows(con,'SELECT * FROM euer_entries WHERE year=? AND archived=0 ORDER BY updated_at,id',(year,))
    return [{**json.loads(r['payload']),'id':r['id'],'year':year,'revision':digest(r)} for r in items]

def save_entry(payload):
    year=A.valid_year(payload.get('year'));supported(year)
    with A.WRITE_LOCK,A.db() as con:
        key=A.clean(payload.get('id'),100) or A.new_id()
        old=con.execute('SELECT * FROM euer_entries WHERE id=? AND archived=0',(key,)).fetchone()
        if payload.get('id') and not old:raise ValueError('Ergänzung nicht gefunden.')
        if old and old['year']!=year:raise ValueError('Jahr der Ergänzung darf nicht geändert werden.')
        check_revision(payload,digest(dict(old)) if old else '')
        if payload.get('archive') is True:
            con.execute('UPDATE euer_entries SET archived=1,updated_at=? WHERE id=?',(A.now(),key));A.audit(con,'archive','euer_entry',key);return {'ok':True}
        if payload.get('confirmed') is not True:raise ValueError('Ergänzung bitte bestätigen.')
        kind=payload.get('kind');pos=A.clean(payload.get('position'),20)
        title=A.clean(payload.get('title'),200);note=A.clean(payload.get('note'),4000)
        if not title or not note:raise ValueError('Titel und nachvollziehbare Quelle / Berechnung sind erforderlich.')
        value={'kind':kind,'position':pos,'title':title,'note':note,'confirmed':True,'profile_hash':digest(taxprofile.get(year))}
        value['source_id']=A.clean(payload.get('source_id'),100)
        if value['source_id']:
            doc=next((d for d in A.state()['documents'] if d['id']==value['source_id']),None)
            if not doc:raise ValueError('Aktive Beleggrundlage nicht gefunden.')
            value['document_hash']=A.source_hash(doc)
        if kind=='asset':
            if pos not in {'31','32','33'}:raise ValueError('AfA-Position auswählen.')
            for k in ('opening','additions','depreciation','disposals'):value[k+'_cents']=amount(payload.get(k,''))
            value['closing_cents']=value['opening_cents']+value['additions_cents']-value['depreciation_cents']-value['disposals_cents']
            if value['closing_cents']<0:raise ValueError('AfA und Abgänge übersteigen den verfügbaren Buchwert.')
            value['amount_cents']=value['depreciation_cents']
            value['acquired_on']=A.valid_date(payload.get('acquired_on'),True)
            if int(value['acquired_on'][:4])>year:raise ValueError('Anschaffung liegt nach dem Arbeitsjahr.')
            value['tx_id']=A.clean(payload.get('tx_id'),100)
            if value['tx_id']:
                row=next((r for r in rows(year) if r['id']==value['tx_id'] and r['status']=='confirmed' and r['target_year']==year and r['allocation']['position']=='asset'),None)
                if not row:raise ValueError('Verknüpfte Zahlung zuerst aktuell als Anschaffung zuordnen.')
                if any(x['id']!=key and x.get('tx_id')==value['tx_id'] for x in entries(year)):
                    raise ValueError('Diese Anschaffung ist bereits in einem Anlageneintrag verknüpft.')
                value['tx_hash']=row['source_hash'];value['allocation_revision']=row['revision']
        elif kind=='supplement':
            if pos not in POSITIONS or pos in {'31','32','33'}:raise ValueError('Ergänzungsposition auswählen; AfA im Anlageverzeichnis erfassen.')
            if taxprofile.get(year)['vat_status']=='small' and pos in {'15','17','57'}:raise ValueError('Ergänzung passt nicht zum Kleinunternehmerstatus des Jahres.')
            value['amount_cents']=amount(payload.get('amount',''),signed=True)
            if value['amount_cents']==0:raise ValueError('Ergänzung mit tatsächlichem Betrag erfassen.')
        else:raise ValueError('Ungültige Ergänzung.')
        con.execute('INSERT INTO euer_entries VALUES (?,?,?,0,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at', (key,year,A.enc(value),A.now()))
        A.audit(con,'update','euer_entry',key,dict(old) if old else None,value)
    return {'ok':True,'id':key}

def posting(row):
    a=row['allocation'];pos=a['position']
    if pos=='exclude':return []
    kind=POSITIONS.get(pos,{}).get('kind','expense')
    sign=1 if row['direction']==kind else -1
    gross=scaled(row['amount_cents'],a['business_percent']);vat=a['vat_cents']
    base=gross-vat
    values=[]
    if pos!='asset':values.append((pos,sign*(scaled(base,a['deductible_percent']) if kind=='expense' else base)))
    if vat:values.append(('57' if kind=='expense' else '17',sign*vat))
    return values

def report(year):
    with A.db():
        data=A.state();rr=rows(year,data);ee=entries(year);profile=taxprofile.get(year)
        marks=[];lines={};details=[];nondeductible=[]
        with A.db() as con:
            imports=A.rows(con,'SELECT id,state,statement_document_id FROM bank_imports WHERE year=? AND archived=0',(year,))
            jobs=A.rows(con,'SELECT id,state,document_id,import_id FROM intake_jobs WHERE year=? AND archived=0',(year,))
        pending={('document',i['statement_document_id']) if i['statement_document_id'] else ('import',i['id']) for i in imports if i['state']!='committed'}
        states={i['id']:i['state'] for i in imports}
        for job in jobs:
            if job['state']!='complete' or job['import_id'] in states and states[job['import_id']]!='committed':
                pending.add(('document',job['document_id']) if job['document_id'] else ('import',job['import_id']) if job['import_id'] else ('job',job['id']))
        if pending:marks.append({'kind':'imports','text':f'{len(pending)} Kontoauszug-Importe noch nicht abgeschlossen. Diese Zahlungen sind noch nicht vollständig enthalten.'})
        def add(code,cents,source,label,note):
            lines[code]=lines.get(code,0)+cents;details.append({'position':code,'amount_cents':cents,'source':source,'label':label,'note':note})
        for r in rr:
            if r['status'] in {'open','stale'}:marks.append({'kind':'transaction','id':r['id'],'text':r['partner']+': '+('Zuordnung nach Änderung erneut bestätigen' if r['stale'] else 'EÜR-Zuordnung offen')})
            elif r['status']=='confirmed' and r['target_year']==year:
                for code,cents in posting(r):add(code,cents,'T:'+r['id'],r['partner']+' · '+r['title'],r['allocation']['note'])
                a=r['allocation']
                if a['position'] in EXPENSE and a['deductible_percent']<100:
                    base=scaled(r['amount_cents'],a['business_percent'])-a['vat_cents']
                    nondeductible.append({'position':a['position'],'source':'T:'+r['id'],'label':r['partner']+' · '+r['title'],'amount_cents':(base-scaled(base,a['deductible_percent']))*(1 if r['direction']=='expense' else -1)})
                if r['allocation']['position']=='asset' and not any(e.get('tx_id')==r['id'] for e in ee):
                    marks.append({'kind':'transaction','id':r['id'],'text':r['partner']+': Anlage und Jahres-AfA noch nicht verknüpft'})
        for e in ee:
            linked=next((r for r in rr if r['id']==e.get('tx_id')),None)
            e['stale']=bool(e.get('tx_id') and (not linked or linked['stale'] or linked['source_hash']!=e.get('tx_hash') or linked['revision']!=e.get('allocation_revision')))
            doc=next((d for d in data['documents'] if d['id']==e.get('source_id')),None)
            e['stale']=e['stale'] or bool(e.get('source_id') and (not doc or A.source_hash(doc)!=e.get('document_hash'))) or bool(e.get('profile_hash') and e['profile_hash']!=digest(profile))
            if e['stale']:marks.append({'kind':'entry','id':e['id'],'text':e['title']+': Anschaffung, Beleggrundlage oder Steuerprofil geändert; Ansatz erneut bestätigen'})
            else:add(e['position'],e['amount_cents'],'E:'+e['id'],e['title'],e['note'])
        fingerprint=digest({'rows':rr,'entries':ee,'profile':profile,'imports':imports,'jobs':jobs,'documents':[(d['id'],A.source_hash(d)) for d in data['documents'] if d['year']==year]})
        with A.db() as con:review=con.execute('SELECT * FROM euer_reviews WHERE year=?',(year,)).fetchone()
        checked=json.loads(review['payload']) if review and review['source_hash']==fingerprint else {}
        if year!=2025:marks.append({'kind':'year','text':'Formularzuordnung nur für 2025 unterstützt.'})
        if profile['vat_status']=='unknown':marks.append({'kind':'profile','text':'Umsatzsteuerstatus für dieses Jahr klären.'})
        if profile['vat_status']=='regular' and profile['taxation']=='unknown':marks.append({'kind':'profile','text':'Ist-/Soll-Versteuerung ist im Jahresprofil noch offen.'})
        if '65' in lines and '66' in lines:marks.append({'kind':'year','text':'Arbeitszimmer/Jahrespauschale und Tagespauschale: Voraussetzungen und zeitlichen Ausschluss prüfen.'})
        if not rr and not ee:marks.append({'kind':'year','text':'Noch keine Zahlungen oder Ergänzungen erfasst.'})
        for key,label in CHECKS.items():
            if not checked.get(key):marks.append({'kind':'check','text':label})
        positions=[{**POSITIONS[k],'amount_cents':v} for k,v in sorted(lines.items(),key=lambda kv:int(kv[0]))]
        inc=sum(p['amount_cents'] for p in positions if p['kind']=='income');exp=sum(p['amount_cents'] for p in positions if p['kind']=='expense')
        return {'year':year,'supported':year==2025,'source_url':SOURCE,'positions_catalog':list(POSITIONS.values()),
          'bank_positions':sorted(BANK_POSITIONS,key=int),'rows':rr,'entries':ee,'positions':positions,'details':details,'nondeductible':nondeductible,
          'income_cents':inc,'expense_cents':exp,'balance_cents':inc-exp,'open':marks,'fingerprint':fingerprint,'check_labels':CHECKS,'checks':checked,
          'counts':{s:sum(r['status']==s for r in rr) for s in ['open','stale','confirmed','excluded']},
          'limitation':'Arbeitsentwurf aus bestätigten Positionen. Ergebnis vor weiteren steuerlichen Gewinnkorrekturen; keine vollständige Steuererklärung und keine ELSTER-Übermittlung. Nicht bestätigte Positionen sind nicht eingerechnet.'}

def save_review(payload):
    year=A.valid_year(payload.get('year'));supported(year)
    with A.WRITE_LOCK,A.db() as con:
        r=report(year)
        if payload.get('fingerprint')!=r['fingerprint']:raise ValueError('Der Jahresstand wurde geändert. Bitte neu laden und prüfen.')
        values={k:payload.get(k) is True for k in CHECKS}
        con.execute('INSERT INTO euer_reviews VALUES (?,?,?,?) ON CONFLICT(year) DO UPDATE SET payload=excluded.payload,source_hash=excluded.source_hash,updated_at=excluded.updated_at',(year,A.enc(values),r['fingerprint'],A.now()))
        A.audit(con,'update','euer_review',str(year),after=values)
    return {'ok':True}

def csv_bytes(year):
    r=report(year);stream=io.StringIO(newline='');writer=csv.writer(stream,delimiter=';')
    def safe(x):
        s=str(x);return "'"+s if s.lstrip().startswith(('=','+','-','@','\t','\r')) else s
    writer.writerow(['EÜR-Arbeitsentwurf',year]);writer.writerow([r['limitation']]);writer.writerow(['Offene Punkte',len(r['open'])])
    writer.writerow(['Zeile 2025','Position','Betrag EUR'])
    for p in r['positions']:writer.writerow([p['code'],p['label'],eur(p['amount_cents'])])
    writer.writerow(['','Einnahmen',eur(r['income_cents'])]);writer.writerow(['','Ausgaben',eur(r['expense_cents'])]);writer.writerow(['','Differenz vor weiteren Gewinnkorrekturen',eur(r['balance_cents'])])
    writer.writerow([]);writer.writerow(['Einzelansätze','Zeile','Betrag EUR','Quelle','Beschreibung','Begründung'])
    for p in r['details']:writer.writerow(['',p['position'],eur(p['amount_cents']),safe(p['source']),safe(p['label']),safe(p['note'])])
    writer.writerow([]);writer.writerow(['Nicht abziehbarer Nettoteil (nicht in den Ausgaben enthalten)','Zeile','Betrag EUR','Quelle','Beschreibung'])
    for p in r['nondeductible']:writer.writerow(['',p['position'],eur(p['amount_cents']),p['source'],safe(p['label'])])
    writer.writerow([]);writer.writerow(['Zahlungsabgleich','Datum','Bruttobetrag EUR','Status','EÜR-Jahr','ID','Beschreibung'])
    for t in r['rows']:writer.writerow(['',t['paid_on'],eur(t['amount_cents']),t['status'],t['target_year'],t['id'],safe(t['partner']+' · '+t['title'])])
    writer.writerow([]);writer.writerow(['Offene Punkte'])
    for p in r['open']:writer.writerow([safe(p['text'])])
    return ('\ufeff'+stream.getvalue()).encode('utf-8')
