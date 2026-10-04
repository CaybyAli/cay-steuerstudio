"""Bank CSV intake: immutable imports, cent integers, explicit review and own-account transfers."""
from __future__ import annotations
import base64
from collections import Counter
import csv
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import re
import unicodedata

A = None
BANKS = {'volksbank', 'n26', 'fyrst', 'other'}
SCOPES = {'business','private','mixed','unknown','transfer'}
ALIASES = {
    'date': ['Buchungstag','Buchungsdatum','Buchung','Date','Booking Date','Datum','Booking date (UTC)'],
    'value_date': ['Wertstellung','Valuta','Valutadatum','Wert','Value Date'],
    'amount': ['Betrag','Betrag (EUR)','Betrag in EUR','Amount (EUR)','Amount','Umsatz','Umsatz in EUR'],
    'debit': ['Soll','Belastung','Debit','Ausgaben'], 'credit': ['Haben','Gutschrift','Credit','Einnahmen'],
    'direction': ['Soll/Haben','Soll/Haben-Kennzeichen','S/H','Debit/Credit'],
    'currency': ['Währung','Waehrung','Currency','Währung des Betrags'],
    'partner': ['Name Zahlungsbeteiligter','Begünstigter/Zahlungspflichtiger','Beguenstigter/Zahlungspflichtiger','Begünstigter / Auftraggeber','Begünstigter','Zahlungspartner','Auftraggeber/Empfänger','Empfänger','Empfaenger','Payee','Name','Partnername'],
    'iban': ['IBAN Zahlungsbeteiligter','IBAN / Kontonummer','IBAN','Account number','Kontonummer/IBAN','Konto-Nr./IBAN'],
    'own_iban': ['IBAN Auftragskonto','Auftragskonto','Eigene IBAN'],
    'purpose': ['Verwendungszweck','Payment reference','Reference','Beschreibung','Zahlungsreferenz'],
    'type': ['Buchungstext','Umsatzart','Transaction type','Transaktionstyp'],
    'reference': ['Kundenreferenz (End-to-End)','End-to-End-Referenz','EndToEndId','Kundenreferenz'],
    # Only genuinely transaction-specific columns, never mandate or generic payment references.
    'transaction_id': ['Transaction ID','Transaktions-ID','Umsatz-ID','Bank Transaction ID']
}


def bind(core):
    global A
    A = core


def initialize():
    with A.db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS bank_accounts (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, bank TEXT NOT NULL, role TEXT NOT NULL,
          iban TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'planned',
          default_scope TEXT NOT NULL DEFAULT 'unknown', reserve_percent INTEGER NOT NULL DEFAULT 35,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS unique_own_iban ON bank_accounts(iban) WHERE iban<>'';
        CREATE TABLE IF NOT EXISTS bank_imports (
          id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES bank_accounts(id), year INTEGER NOT NULL,
          filename TEXT NOT NULL, sha256 TEXT NOT NULL, original BLOB NOT NULL,
          encoding TEXT NOT NULL, delimiter TEXT NOT NULL, mapping_json TEXT NOT NULL,
          preview_json TEXT NOT NULL, state TEXT NOT NULL, result_json TEXT,
          created_at TEXT NOT NULL, committed_at TEXT, UNIQUE(account_id,year,sha256));
        CREATE TABLE IF NOT EXISTS bank_rows (
          id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES bank_accounts(id),
          import_id TEXT NOT NULL REFERENCES bank_imports(id), line_no INTEGER NOT NULL,
          booked_on TEXT NOT NULL, value_on TEXT NOT NULL DEFAULT '',
          amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents<>0),
          currency TEXT NOT NULL CHECK(currency='EUR'), partner TEXT NOT NULL, purpose TEXT NOT NULL,
          counterparty_iban TEXT NOT NULL DEFAULT '', bank_ref TEXT NOT NULL DEFAULT '', external_id TEXT NOT NULL DEFAULT '',
          fingerprint TEXT NOT NULL, unique_key TEXT NOT NULL, raw_json TEXT NOT NULL,
          classification TEXT NOT NULL DEFAULT 'unreviewed', created_at TEXT NOT NULL,
          UNIQUE(account_id,unique_key));
        CREATE INDEX IF NOT EXISTS bank_rows_fingerprint ON bank_rows(account_id,fingerprint);
        CREATE TABLE IF NOT EXISTS bank_transfers (
          id TEXT PRIMARY KEY, outgoing_id TEXT NOT NULL UNIQUE REFERENCES bank_rows(id),
          incoming_id TEXT NOT NULL UNIQUE REFERENCES bank_rows(id), amount_cents INTEGER NOT NULL CHECK(typeof(amount_cents)='integer' AND amount_cents>0),
          evidence TEXT NOT NULL, confirmed_by TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        account_cols={r[1] for r in con.execute('PRAGMA table_info(bank_accounts)')}
        for name in ['opened_on','closed_on']:
            if name not in account_cols:
                con.execute(f"ALTER TABLE bank_accounts ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        import_cols={r[1] for r in con.execute('PRAGMA table_info(bank_imports)')}
        for name,kind in [('source_kind',"TEXT NOT NULL DEFAULT 'csv'"),('statement_document_id','TEXT')]:
            if name not in import_cols: con.execute(f'ALTER TABLE bank_imports ADD COLUMN {name} {kind}')
        cols={r[1] for r in con.execute('PRAGMA table_info(transactions)')}
        for name, kind in [('account_id','TEXT REFERENCES bank_accounts(id)'), ('bank_row_id','TEXT REFERENCES bank_rows(id)')]:
            if name not in cols:
                con.execute(f'ALTER TABLE transactions ADD COLUMN {name} {kind}')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS bank_row_transaction ON transactions(bank_row_id) WHERE bank_row_id IS NOT NULL')
        con.executescript('''
        CREATE TRIGGER IF NOT EXISTS tx_cents_insert BEFORE INSERT ON transactions
          WHEN typeof(NEW.amount_cents)<>'integer' BEGIN SELECT RAISE(ABORT,'amount_cents must be INTEGER'); END;
        CREATE TRIGGER IF NOT EXISTS tx_cents_update BEFORE UPDATE OF amount_cents ON transactions
          WHEN typeof(NEW.amount_cents)<>'integer' BEGIN SELECT RAISE(ABORT,'amount_cents must be INTEGER'); END;
        ''')
        for key,name,bank,role,status,scope in [
            ('volksbank','Volksbank · bisheriges Konto','volksbank','historical','active','unknown'),
            ('n26','N26 Business Standard · Hauptkonto','n26','main','planned','business'),
            ('fyrst','FYRST BASE · Steuerkonto','fyrst','tax','planned','unknown')]:
            con.execute('INSERT OR IGNORE INTO bank_accounts (id,name,bank,role,status,default_scope,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                        ('account_'+key,name,bank,role,status,scope,A.now(),A.now()))


def norm(s):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(s).lower().replace('ß','ss')).encode('ascii','ignore').decode())


def iban(value, required=False):
    value = re.sub(r'\s', '', str(value or '')).upper()
    if not value and not required:
        return ''
    if not re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{11,30}', value):
        raise ValueError('Bitte eine vollständige eigene IBAN eingeben.')
    number=''.join(str(ord(c)-55) if c.isalpha() else c for c in value[4:]+value[:4])
    if int(number) % 97 != 1:
        raise ValueError('Die IBAN-Prüfziffer stimmt nicht.')
    return value


def counterpart(value):
    # Card identifiers and national account numbers are preserved in raw_json, not guessed as IBANs.
    value=re.sub(r'\s','',str(value or '')).upper()
    try:
        return iban(value) if value else ''
    except ValueError:
        return ''


def accounts():
    with A.db() as con:
        return A.rows(con,'SELECT * FROM bank_accounts ORDER BY CASE bank WHEN \'volksbank\' THEN 0 WHEN \'n26\' THEN 1 ELSE 2 END')


def save_account(payload):
    aid=A.clean(payload.get('id'),80)
    data={'name':A.clean(payload.get('name'),200),'bank':payload.get('bank'), 'role':payload.get('role'),
          'iban':iban(payload.get('iban')), 'status':payload.get('status'), 'default_scope':payload.get('default_scope','unknown'), 'updated_at':A.now(), 'opened_on':A.valid_date(payload.get('opened_on','')), 'closed_on':A.valid_date(payload.get('closed_on',''))}
    if data['opened_on'] and data['closed_on'] and data['closed_on']<data['opened_on']:
        raise ValueError('Das Ende darf nicht vor der Kontoeröffnung liegen.')
    if data['status']=='closed' and not data['closed_on']:
        raise ValueError('Bitte den letzten gültigen Kontotag angeben. Frühere Buchungen bleiben erhalten.')
    if data['status']!='closed': data['closed_on']=''
    if not data['name'] or data['bank'] not in BANKS or data['role'] not in {'main','tax','historical'} or data['status'] not in {'planned','active','closed'} or data['default_scope'] not in {'business','private','unknown'}:
        raise ValueError('Bitte die Kontoangaben prüfen.')
    percent=payload.get('reserve_percent',35)
    if not str(percent).isdigit() or not 30<=int(percent)<=45:
        raise ValueError('Deine Rücklagenquote muss zwischen 30 und 45 Prozent liegen.')
    data['reserve_percent']=int(percent)
    with A.WRITE_LOCK,A.db() as con:
        old=con.execute('SELECT * FROM bank_accounts WHERE id=?',(aid,)).fetchone()
        if not old:
            raise ValueError('Konto nicht gefunden.')
        if data['iban'] and con.execute('SELECT 1 FROM bank_accounts WHERE iban=? AND id<>?',(data['iban'],aid)).fetchone():
            raise ValueError('Diese IBAN gehört bereits zu einem anderen Konto im Dashboard.')
        if old['iban'] and old['iban'] != data['iban'] and con.execute('SELECT 1 FROM bank_rows WHERE account_id=?',(aid,)).fetchone():
            raise ValueError('Die IBAN eines bereits importierten Kontos kann nicht nachträglich ausgetauscht werden. Kontoidentität und frühere Überträge müssen erhalten bleiben.')
        if data['opened_on'] and con.execute('SELECT 1 FROM transactions WHERE account_id=? AND archived=0 AND paid_on<?',(aid,data['opened_on'])).fetchone():
            raise ValueError('Vor dem ersten Kontotag sind bereits Buchungen gespeichert. Bitte das Datum prüfen.')
        if data['closed_on'] and con.execute('SELECT 1 FROM transactions WHERE account_id=? AND archived=0 AND paid_on>?',(aid,data['closed_on'])).fetchone():
            raise ValueError('Nach dem gewählten letzten Kontotag sind bereits Buchungen gespeichert. Bitte das Datum prüfen.')
        con.execute('UPDATE bank_accounts SET '+','.join(k+'=?' for k in data)+' WHERE id=?',list(data.values())+[aid])
        A.audit(con,'update','bank_account',aid,dict(old),data)
        reconcile(con)
    return {'id':aid}


def signed_cents(value, style='de'):
    if not isinstance(value,str):
        raise ValueError('Betrag fehlt.')
    text=value.strip().replace('\u00a0','').replace(' ','').replace('€','')
    text=re.sub(r'EUR$', '', text, flags=re.I)
    if text.startswith('(') and text.endswith(')'):
        text='-'+text[1:-1]
    if text.endswith('-'):
        text='-'+text[:-1]
    if style=='de':
        if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?',text):
            raise ValueError('Deutsches Zahlenformat erwartet, z. B. -1.234,56.')
        text=text.replace('.','').replace(',','.')
    elif style=='en':
        if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?',text):
            raise ValueError('Zahlenformat mit Dezimalpunkt erwartet, z. B. -1234.56.')
        text=text.replace(',','')
    else:
        raise ValueError('Zahlenformat unbekannt.')
    try:
        value=Decimal(text)*100
        if value!=value.to_integral_value() or abs(value)>1_000_000_000:
            raise ValueError('Betrag außerhalb des unterstützten Bereichs.')
        return int(value)
    except InvalidOperation:
        raise ValueError('Betrag ist keine gültige Zahl.')


def bank_date(value):
    text=str(value).strip()
    for fmt in ['%Y-%m-%d','%d.%m.%Y','%d/%m/%Y','%d.%m.%y']:
        try:
            d=datetime.strptime(text,fmt).date()
            if not 2024<=d.year<=2100:
                raise ValueError('Datumsjahr liegt außerhalb des Arbeitsbereichs ab 2024.')
            return d.isoformat()
        except ValueError:
            continue
    raise ValueError('Buchungsdatum nicht erkannt. Unterstützt: TT.MM.JJJJ oder JJJJ-MM-TT.')


def decode(raw, requested='auto'):
    if requested not in {'auto','utf-8-sig','cp1252','utf-16'}:
        raise ValueError('Unbekannte Zeichencodierung.')
    attempts=[requested] if requested!='auto' else (['utf-16'] if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else ['utf-8-sig','cp1252'])
    for encoding in attempts:
        try:
            text=raw.decode(encoding,errors='strict')
            if '\x00' in text:
                raise ValueError('Ungültige Nullzeichen im CSV-Text.')
            return text,encoding
        except UnicodeDecodeError:
            continue
    raise ValueError('Zeichencodierung nicht erkannt. Bitte UTF-8 oder Windows-1252 auswählen.')


def auto_mapping(headers):
    normal=[norm(h) for h in headers]
    out={}
    for key,aliases in ALIASES.items():
        for alias in aliases:
            if norm(alias) in normal:
                out[key]=normal.index(norm(alias))
                break
    return out


def parse_csv(raw, bank, options=None):
    options=options or {}
    text,encoding=decode(raw,options.get('encoding','auto'))
    delimiters=[options['delimiter']] if options.get('delimiter') else [';',',','\t']
    if any(d not in {';',',','\t'} for d in delimiters):
        raise ValueError('Bitte Semikolon, Komma oder Tabulator als Trennzeichen wählen.')
    best=None
    for delim in delimiters:
        try:
            parsed=list(csv.reader(io.StringIO(text,newline=''),delimiter=delim,strict=True))
        except csv.Error:
            continue
        for index, row in enumerate(parsed[:35]):
            if len(row)<2:
                continue
            mapping=auto_mapping(row)
            score=10*('date' in mapping)+10*('amount' in mapping or ('debit' in mapping and 'credit' in mapping))+len(mapping)
            if options.get('header_row') is not None:
                if index!=int(options['header_row']):
                    continue
                score+=100
            if best is None or score>best[0]:
                best=(score,delim,index,row,parsed,mapping)
    if not best:
        raise ValueError('Keine CSV-Kopfzeile gefunden. Bitte CSV direkt aus dem Onlinebanking exportieren.')
    _,delim,header_index,headers,parsed,found=best
    mapping=options.get('mapping',found)
    if not isinstance(mapping,dict) or any(k not in ALIASES or isinstance(v,bool) or not isinstance(v,int) or not 0<=v<len(headers) for k,v in mapping.items()):
        raise ValueError('Ungültige Spaltenzuordnung.')
    style=options.get('number_style') or ('en' if bank=='n26' else 'de')
    result={'headers':headers,'mapping':mapping,'encoding':encoding,'delimiter':delim,'header_row':header_index,'number_style':style,'rows':[],'errors':[]}
    if 'date' not in mapping or not ('amount' in mapping or ('debit' in mapping and 'credit' in mapping)):
        result['errors'].append({'line':header_index+1,'message':'Buchungsdatum und Betrag (oder Soll/Haben-Spalten) bitte zuordnen.'})
        return result
    data_rows=parsed[header_index+1:]
    if len(data_rows)>10000:
        raise ValueError('Bitte höchstens 10.000 CSV-Zeilen pro Datei importieren.')
    for index,row in enumerate(data_rows,header_index+2):
        if not row or all(not c.strip() for c in row):
            continue
        try:
            if len(row)!=len(headers):
                raise ValueError('Spaltenzahl weicht von der Kopfzeile ab. Kein stilles Überspringen.')
            def get(key):
                return row[mapping[key]].strip() if key in mapping else ''
            booked=bank_date(get('date'))
            value=bank_date(get('value_date')) if get('value_date') else ''
            if 'amount' in mapping:
                amount=signed_cents(get('amount'),style)
                sign=norm(get('direction'))
                if sign:
                    if sign not in {'s','h','soll','haben','debit','credit','d','c','ausgang','eingang'}:
                        raise ValueError('Soll/Haben-Kennzeichen unbekannt.')
                    negative=sign in {'s','soll','debit','d','ausgang'}
                    if amount<0 and not negative:
                        raise ValueError('Vorzeichen und Soll/Haben-Kennzeichen widersprechen sich.')
                    amount=-abs(amount) if negative else abs(amount)
            else:
                debit=signed_cents(get('debit'),style) if get('debit') else 0
                credit=signed_cents(get('credit'),style) if get('credit') else 0
                if debit and credit or credit<0:
                    raise ValueError('Soll und Haben widersprüchlich.')
                amount=credit-abs(debit)
            currency=get('currency').upper() or 'EUR'
            if currency not in {'EUR','€'}:
                raise ValueError('Fremdwährung ohne EUR-Bankbetrag wird nicht automatisch umgerechnet.')
            if amount==0:
                raise ValueError('Nullbetrag: prüfen, ob diese Zeile eine Buchung ist.')
            partner=get('partner') or 'Partner noch zu prüfen'
            purpose=' · '.join(filter(None,[get('type'),get('purpose')])) or 'Bankumsatz'
            cpiban=counterpart(get('iban'))
            own=counterpart(get('own_iban'))
            ref=get('reference')
            if norm(ref) in {'notprovided','nichtangegeben','nonref','keine'}:
                ref=''
            external=get('transaction_id')
            fingerprint=hashlib.sha256(A.enc([booked,value,amount,'EUR',norm(partner),cpiban,norm(purpose),ref]).encode()).hexdigest()
            result['rows'].append({'line':index,'booked_on':booked,'value_on':value,'amount_cents':amount,'currency':'EUR',
                 'partner':partner[:200],'purpose':purpose[:10000],'counterparty_iban':cpiban,'own_iban':own,'bank_ref':ref[:500],
                 'external_id':external[:500],'fingerprint':fingerprint,'raw':dict(zip(headers,row))})
        except ValueError as exc:
            result['errors'].append({'line':index,'message':str(exc),'raw':row})
    return result


def row_classification(row, account, all_accounts):
    other=next((a for a in all_accounts if a['id']!=account['id'] and a['iban'] and a['iban']==row['counterparty_iban']),None)
    if other:
        return 'transfer','transfer',f"Eigene Gegen-IBAN: {other['name']}. EÜR-neutral; zweite Kontoseite kann noch fehlen."
    text=norm(row['partner']+' '+row['purpose'])
    if account['role']=='tax' or 'finanzamt' in text or 'finanzkasse' in text:
        return 'tax_review','unknown','Steuerkonto / Finanzamt: Steuerart anhand Bescheid oder Voranmeldung zuordnen. Keine pauschale Betriebsausgabe.'
    # A cash withdrawal is a movement into a wallet/cashbox, not the later
    # purchase. Keep it visible for reconciliation and prevent double counting.
    if any(term in text for term in ('geldautomat','bargeldabhebung','barabhebung','cashwithdrawal','atm','auszahlunggeldautomat')):
        return 'cash_withdrawal','unknown','Bargeldabhebung: noch keine Ausgabe. Spätere Barbelege separat erfassen und diese Kontoseite nicht doppelt buchen.'
    if any(term in text for term in ('bareinzahlung','bargeldeinzahlung','cashdeposit')):
        return 'cash_deposit','unknown','Bareinzahlung: Herkunft klären. Private Einlage oder betriebliche Einnahmen sind möglich.'
    return 'unreviewed','unknown','Noch nicht eingeordnet. Geschäftskonto und Händlername allein beweisen keinen betrieblichen Zweck.'


def require_active(batch):
    if batch and batch['archived']:raise ValueError('Dieser Auszug liegt im Papierkorb. Bitte dort wiederherstellen.')

def preview(payload):
    year=A.valid_year(payload.get('year'))
    aid=A.clean(payload.get('account_id'),80)
    filename=A.clean(payload.get('filename'),240).replace('\\','/').split('/')[-1]
    if not filename.lower().endswith('.csv'):
        raise ValueError('Bitte eine CSV-Datei auswählen.')
    if payload.get('import_id'):
        with A.db() as con:
            previous=con.execute('SELECT original,filename,archived FROM bank_imports WHERE id=?',(payload['import_id'],)).fetchone()
        if not previous:
            raise ValueError('Gespeicherte CSV nicht gefunden.')
        require_active(previous)
        raw=previous['original']
        filename=previous['filename']
    else:
        raw=base64.b64decode(payload.get('file_base64',''),validate=True)
    if not raw or len(raw)>10*1024**2:
        raise ValueError('CSV-Dateien bis 10 MB sind möglich.')
    all_accounts=accounts()
    account=next((a for a in all_accounts if a['id']==aid),None)
    if not account:
        raise ValueError('Bitte ein Konto auswählen.')
    if not payload.get('import_id') and not payload.get('options'):
        with A.db() as con:
            previous=con.execute('SELECT id FROM bank_imports WHERE account_id=? AND year=? AND sha256=?',(aid,year,hashlib.sha256(raw).hexdigest())).fetchone()
        if previous:return saved_preview(previous['id'])
    parsed=parse_csv(raw,account['bank'],payload.get('options'))
    return prepare_rows(year, aid, filename, raw, parsed)


def prepare_rows(year, aid, filename, raw, parsed, source_kind='csv', statement_document_id=None):
    all_accounts=accounts()
    account=next((a for a in all_accounts if a['id']==aid),None)
    if not account: raise ValueError('Konto nicht gefunden.')
    sha=hashlib.sha256(raw).hexdigest()
    counts=Counter()
    with A.WRITE_LOCK,A.db() as con:
        existing=con.execute('SELECT * FROM bank_imports WHERE account_id=? AND year=? AND sha256=?',(aid,year,sha)).fetchone()
        require_active(existing)
        if existing and existing['state']=='committed':
            return {'already_imported':True,'id':existing['id'],'result':json.loads(existing['result_json'])}
        db_counts=Counter(r['fingerprint'] for r in con.execute('SELECT fingerprint FROM bank_rows WHERE account_id=?',(aid,)))
        known_external={r['external_id']:dict(r) for r in con.execute("SELECT * FROM bank_rows WHERE account_id=? AND external_id<>''",(aid,))}
        seen_external=set()
        for row in parsed['rows']:
            counts[row['fingerprint']]+=1
            row['occurrence']=counts[row['fingerprint']]
            row['classification'],row['scope'],row['note']=row_classification(row,account,all_accounts)
            row['category']='Unsortiert'
            row['review_note']=''
            row['manual_matches']=[]
            row['status']='ready'
            if int(row['booked_on'][:4])!=year:
                row['status']='outside_year'
            elif not usable_on(account,row['booked_on']):
                row['status']='error'
                row['note']='Buchung liegt außerhalb des erfassten Kontozeitraums. Kontodaten oder Auszug prüfen.'
            elif row['own_iban'] and account['iban'] and row['own_iban']!=account['iban']:
                row['status']='error'
                row['note']='Auftragskonto der CSV stimmt nicht mit der eigenen Konto-IBAN überein.'
            elif row['external_id'] and row['external_id'] in seen_external:
                row['status']='error'
                row['note']='Transaktions-ID steht mehrfach in dieser CSV. Bitte prüfen.'
            elif row['external_id'] and row['external_id'] in known_external:
                old=known_external[row['external_id']]
                row['status']='duplicate' if old['fingerprint']==row['fingerprint'] else 'error'
                row['note']='Bank-ID bereits importiert.' if row['status']=='duplicate' else 'Bekannte Bank-ID mit veränderten Daten. Import gesperrt; Korrektur prüfen.'
            elif not row['external_id'] and counts[row['fingerprint']]<=db_counts[row['fingerprint']]:
                row['status']='duplicate'
                row['note']='Gleiche Buchungsdaten vorhanden. Ohne eindeutige Bank-ID bitte mögliche echte Wiederholungsbuchung prüfen.'
            if row['external_id']:
                seen_external.add(row['external_id'])
            if row['status']=='ready':
                direction='income' if row['amount_cents']>0 else 'expense'
                candidates=A.rows(con,"SELECT id,partner,title,scope,account_id,payment_method FROM transactions WHERE archived=0 AND bank_row_id IS NULL AND paid_on=? AND direction=? AND amount_cents=?",(row['booked_on'],direction,abs(row['amount_cents'])))
                # Cash entries have no bank evidence and must never be silently
                # linked to a same-day/same-amount CSV line.
                row['manual_matches']=[t for t in candidates if t.get('payment_method','unknown')!='cash' and (not t['account_id'] or t['account_id']==aid)]
                if row['manual_matches']:
                    row['status']='manual_review'
                    row['note']='Bereits manuell erfasste Zahlung mit gleichem Datum/Betrag gefunden. Verknüpfen oder ausdrücklich neu importieren.'
                elif con.execute('SELECT 1 FROM bank_rows WHERE account_id=? AND booked_on=? AND amount_cents=? AND fingerprint<>?',(aid,row['booked_on'],row['amount_cents'],row['fingerprint'])).fetchone():
                    row['status']='manual_review'
                    row['note']='Ähnlicher Bankumsatz bereits vorhanden (Datum/Betrag gleich, Text abweichend). Bewusst auslassen oder als tatsächlich weitere Zahlung übernehmen.'
        iid=existing['id'] if existing else A.new_id()
        data={'account_id':aid,'year':year,'filename':filename,'sha256':sha,'original':raw,'encoding':parsed['encoding'],'delimiter':parsed['delimiter'],
              'mapping_json':A.enc({k:parsed[k] for k in ['mapping','number_style','header_row']}),'preview_json':A.enc({**parsed,'source_kind':source_kind,'statement_document_id':statement_document_id}),'state':'partial' if existing and existing['state']=='partial' else 'preview','source_kind':source_kind,'statement_document_id':statement_document_id}
        if existing:
            con.execute('UPDATE bank_imports SET '+','.join(k+'=?' for k in data)+' WHERE id=?',list(data.values())+[iid])
        else:
            A.insert(con,'bank_imports',{**data,'id':iid,'created_at':A.now()})
        A.audit(con,'preview','bank_import',iid,after={'year':year,'account':aid,'sha256':sha,'rows':len(parsed['rows'])})
    return {'id':iid,'year':year,'account':account,'filename':filename,'source_kind':source_kind,'statement_document_id':statement_document_id,**parsed}


def saved_preview(iid):
    with A.db() as con:
        batch=con.execute('SELECT * FROM bank_imports WHERE id=?',(iid,)).fetchone()
        require_active(batch)
        if not batch:
            raise ValueError('Import nicht gefunden.')
        account=dict(con.execute('SELECT * FROM bank_accounts WHERE id=?',(batch['account_id'],)).fetchone())
    if batch['state']=='committed':
        return {'already_imported':True,'id':batch['id'],'result':json.loads(batch['result_json'])}
    parsed=json.loads(batch['preview_json'])
    return {'id':iid,'filename':batch['filename'],'year':batch['year'],'account':account,'resume_job':bool(parsed.get('pdf_month_review') and not parsed.get('pdf_pending_selection')),**parsed}


def commit(payload):
    iid=A.clean(payload.get('id'),80)
    choices=payload.get('choices',{})
    if not isinstance(choices,dict):
        raise ValueError('Ungültige Importauswahl.')
    with A.WRITE_LOCK,A.db() as con:
        batch=con.execute('SELECT * FROM bank_imports WHERE id=?',(iid,)).fetchone()
        require_active(batch)
        if not batch:
            raise ValueError('Importvorschau nicht gefunden.')
        if batch['state']=='committed':
            return json.loads(batch['result_json'])
        parsed=json.loads(batch['preview_json'])
        if parsed.get('pdf_month_review'):
            import pdf_review
            if not parsed.get('pdf_pending_selection'):
                return {**json.loads(batch['result_json'] or '{}'),'partial':batch['state']=='partial','job_id':parsed['pdf_job_id'],'already_approved':True}
            if payload.get('pdf_selection_token')!=parsed.get('pdf_selection_token'):raise ValueError('Diese Monatsauswahl ist nicht mehr aktuell. Bitte die offene Prüfung neu öffnen.')
            pdf_review.before_commit(con,batch,parsed)
        if payload.get('checked') is not True:
            raise ValueError('Bitte Konto, Jahr, Vorzeichen, Summen und Zuordnungen bestätigen.')
        if parsed.get('source_kind')=='pdf' and not parsed.get('pdf_checked'):
            raise ValueError('Bitte den PDF-Auszug zuerst vollständig am Original prüfen.')
        if parsed['errors'] or any(r['status']=='error' for r in parsed['rows']):
            raise ValueError('Der Auszug enthält Fehler. Bitte Spalten/Format korrigieren oder die Quelldatei berichtigen. Es wurde nichts gebucht.')
        account=dict(con.execute('SELECT * FROM bank_accounts WHERE id=?',(batch['account_id'],)).fetchone())
        all_accounts=A.rows(con,'SELECT * FROM bank_accounts')
        result={'imported':0,'linked':0,'skipped':0,'transfers':0,'import_id':iid}
        if parsed.get('pdf_month_review'):result['month_results']={}
        for row in parsed['rows']:
            counts=result['month_results'].setdefault(row['booked_on'][:7],{'imported':0,'linked':0,'skipped':0,'transfers':0}) if parsed.get('pdf_month_review') else None
            default=row.get('choice') or ('create' if row['status']=='ready' else 'skip' if row['status'] in {'duplicate','outside_year'} else 'review')
            action=choices.get(str(row['line']),default)
            if action not in {'create','force_new','skip','review'} and not (isinstance(action,str) and re.fullmatch(r'link:[a-f0-9]{32}',action)):
                raise ValueError('Unbekannte Aktion in Zeile '+str(row['line']))
            if row['status']=='outside_year':
                action='skip'
            if action=='review':
                raise ValueError('Bitte die mögliche manuelle Doppelbuchung in Zeile '+str(row['line'])+' zuordnen.')
            if row['status']=='duplicate' and action not in {'skip','force_new'}:
                raise ValueError('Für vorhandene Buchungen bitte Überspringen oder Echte zweite Buchung wählen.')
            if parsed.get('pdf_month_review'):row['choice']=action
            if action=='skip':
                result['skipped']+=1
                if counts is not None:counts['skipped']+=1
                continue
            if row['external_id']:
                key='bank:'+row['external_id']
                if action=='force_new':
                    raise ValueError('Eine eindeutige Bank-ID darf nicht doppelt importiert werden.')
            else:
                key='fp:'+row['fingerprint']+':'+str(row['occurrence'])
                if action=='force_new':
                    key+=':manual:'+A.new_id()
            if con.execute('SELECT 1 FROM bank_rows WHERE account_id=? AND unique_key=?',(account['id'],key)).fetchone():
                raise ValueError('Zwischen Vorschau und Übernahme wurden dieselben Daten importiert. Bitte Vorschau neu erstellen.')
            if not usable_on(account,row['booked_on']): raise ValueError('Der Kontozeitraum wurde geändert. Vorschau erneut prüfen.')
            bid=A.new_id()
            classification,scope,note=row_classification(row,account,all_accounts)
            if classification!='transfer': scope=row.get('scope','unknown')
            category=row.get('category','Unsortiert')
            if scope not in SCOPES or category not in A.CATEGORIES: raise ValueError('Ungültige Einordnung.')
            if scope=='transfer' and classification!='transfer' and not row.get('review_note','').strip():
                raise ValueError('Manuellen Eigenübertrag bitte kurz begründen.')
            A.insert(con,'bank_rows',{'id':bid,'account_id':account['id'],'import_id':iid,'line_no':row['line'],
                **{k:row[k] for k in ['booked_on','value_on','amount_cents','currency','partner','purpose','counterparty_iban','bank_ref','external_id','fingerprint']},
                'unique_key':key,'raw_json':A.enc(row['raw']),'classification':classification,'created_at':A.now()})
            if action.startswith('link:'):
                tid=action[5:]
                tx=con.execute('SELECT * FROM transactions WHERE id=? AND archived=0 AND bank_row_id IS NULL',(tid,)).fetchone()
                if not tx or tx['payment_method']=='cash' or tx['paid_on']!=row['booked_on'] or tx['amount_cents']!=abs(row['amount_cents']) or tx['direction']!=('income' if row['amount_cents']>0 else 'expense') or tx['account_id'] not in {None,account['id']}:
                    raise ValueError('Die manuelle Zuordnung passt nicht mehr. Bitte Vorschau erneut prüfen.')
                con.execute("UPDATE transactions SET account_id=?,bank_row_id=?,payment_method='bank',updated_at=? WHERE id=?",(account['id'],bid,A.now(),tid))
                A.audit(con,'link','transaction',tid,dict(tx),{'bank_row_id':bid,'account_id':account['id']})
                if parsed.get('pdf_month_review'):
                    check=next((m for m in parsed['pdf_reconciliation']['months'] if m['month']==row['booked_on'][:7]),None)
                    if check and check['status']=='difference':
                        warning='Mit Abweichung übernommen (Saldo/Umsatzsummen). '+parsed['pdf_override_notes'].get(check['month'],'')
                        con.execute('UPDATE transactions SET notes=? WHERE id=?',(tx['notes']+'\n'+warning,tid))
                        A.audit(con,'pdf_review_note','transaction',tid,after={'note':warning})
                result['linked']+=1
                if counts is not None:counts['linked']+=1
            else:
                tx_payload={'direction':'income' if row['amount_cents']>0 else 'expense',
                     'amount':f"{abs(row['amount_cents'])//100},{abs(row['amount_cents'])%100:02d}", 'paid_on':row['booked_on'],
                     'partner':row['partner'],'title':row['purpose'][:200],'notes':f"Auszug: {batch['filename']}, Zeile {row['line']}. {note}\n{row.get('review_note','')}",
                     'scope':scope,'category':category,'data_checked':False,'account_id':account['id'],
                     'payment_method':'bank','expense_kind':'standard'}
                tid=A.save_transaction(tx_payload)['id']
                con.execute('UPDATE transactions SET bank_row_id=? WHERE id=?',(bid,tid))
                result['imported']+=1
                if counts is not None:counts['imported']+=1
            con.execute('UPDATE transactions SET statement_document_id=? WHERE id=?',(batch['statement_document_id'],tid))
            if classification=='transfer':
                neutralize(con,bid,'Eigene Gegen-IBAN erkannt.')
                result['transfers']+=1
                if counts is not None:counts['transfers']+=1
        reconcile(con)
        state,stored_result=pdf_review.finish_commit(con,batch,parsed,result) if parsed.get('pdf_month_review') else ('committed',result)
        con.execute("UPDATE bank_imports SET state=?,result_json=?,committed_at=? WHERE id=?",(state,A.enc(stored_result),A.now(),iid))
        A.audit(con,'commit','bank_import',iid,after={**result,'choices':choices})
    return result


def neutralize(con,bid,evidence):
    con.execute("UPDATE bank_rows SET classification='transfer' WHERE id=?",(bid,))
    tx=con.execute('SELECT * FROM transactions WHERE bank_row_id=?',(bid,)).fetchone()
    if tx and tx['scope']!='transfer':
        con.execute("UPDATE transactions SET scope='transfer',data_checked=0,tax_note=?,updated_at=? WHERE id=?",(evidence,A.now(),tx['id']))
        A.audit(con,'classify_transfer','transaction',tx['id'],dict(tx),{'scope':'transfer','evidence':evidence})


def pair(con,outgoing,incoming,evidence,by):
    for row in [outgoing,incoming]:
        if con.execute('SELECT 1 FROM bank_transfers WHERE outgoing_id=? OR incoming_id=?',(row['id'],row['id'])).fetchone():
            raise ValueError('Eine Kontoseite ist bereits mit einem anderen Übertrag verbunden.')
    tid=A.new_id()
    A.insert(con,'bank_transfers',{'id':tid,'outgoing_id':outgoing['id'],'incoming_id':incoming['id'],'amount_cents':incoming['amount_cents'],
                                'evidence':evidence,'confirmed_by':by,'created_at':A.now()})
    neutralize(con,outgoing['id'],evidence)
    neutralize(con,incoming['id'],evidence)
    A.audit(con,'match','bank_transfer',tid,after={'outgoing_id':outgoing['id'],'incoming_id':incoming['id'],'by':by,'evidence':evidence})


def pair_candidates(con):
    rows=A.rows(con,"SELECT b.*,a.iban AS own_iban,a.name AS account_name,a.role FROM bank_rows b JOIN bank_accounts a ON a.id=b.account_id WHERE NOT EXISTS (SELECT 1 FROM bank_transfers t WHERE t.outgoing_id=b.id OR t.incoming_id=b.id)")
    candidates=[]
    for out in rows:
        if out['amount_cents']>=0:
            continue
        for inc in rows:
            if inc['amount_cents']!=-out['amount_cents'] or inc['account_id']==out['account_id']:
                continue
            days=abs((date.fromisoformat(out['booked_on'])-date.fromisoformat(inc['booked_on'])).days)
            if days>5:
                continue
            # A specified different counterparty is positive evidence against an internal match.
            if out['counterparty_iban'] and inc['own_iban'] and out['counterparty_iban']!=inc['own_iban']:
                continue
            if inc['counterparty_iban'] and out['own_iban'] and inc['counterparty_iban']!=out['own_iban']:
                continue
            strong=bool(out['own_iban'] and inc['own_iban'] and out['counterparty_iban']==inc['own_iban'] and inc['counterparty_iban']==out['own_iban'])
            candidates.append({'outgoing':out,'incoming':inc,'days':days,'strong':strong})
    return candidates


def reconcile(con):
    acc=A.rows(con,'SELECT * FROM bank_accounts')
    byid={a['id']:a for a in acc}
    for row in A.rows(con,'SELECT * FROM bank_rows'):
        if row_classification(row,byid[row['account_id']],acc)[0]=='transfer':
            neutralize(con,row['id'],'Gegen-IBAN gehört zu einem eigenen registrierten Konto.')
    candidates=pair_candidates(con)
    counts=Counter(v for p in candidates for v in [p['outgoing']['id'],p['incoming']['id']])
    for p in candidates:
        if p['strong'] and counts[p['outgoing']['id']]==1 and counts[p['incoming']['id']]==1:
            pair(con,p['outgoing'],p['incoming'],'Beide Gegen-IBANs, EUR-Betrag und Buchungen innerhalb von fünf Tagen stimmen überein.','iban_rule')
        else:
            for row in [p['outgoing'],p['incoming']]:
                if row['classification']=='transfer':
                    continue
                tx=con.execute('SELECT * FROM transactions WHERE bank_row_id=?',(row['id'],)).fetchone()
                if tx and tx['scope']!='unknown' and not tx['data_checked']:
                    con.execute("UPDATE transactions SET scope='unknown',tax_note=?,updated_at=? WHERE id=?",('Möglicher Eigenübertrag. Unter Bankimport prüfen.',A.now(),tx['id']))
                    A.audit(con,'transfer_candidate','transaction',tx['id'],dict(tx),{'scope':'unknown'})


def confirm_pair(payload):
    outgoing=A.clean(payload.get('outgoing_id'),80)
    incoming=A.clean(payload.get('incoming_id'),80)
    with A.WRITE_LOCK,A.db() as con:
        out=con.execute('SELECT * FROM bank_rows WHERE id=?',(outgoing,)).fetchone()
        inc=con.execute('SELECT * FROM bank_rows WHERE id=?',(incoming,)).fetchone()
        if not out or not inc or out['amount_cents']>=0 or inc['amount_cents']!=-out['amount_cents'] or out['account_id']==inc['account_id']:
            raise ValueError('Die Kontoseiten passen nicht zu einem neutralen Eigenübertrag.')
        pair(con,dict(out),dict(inc),'Vom Nutzer anhand beider Kontoseiten bestätigt.','user')
    return {'ok':True}


def status(year):
    with A.db() as con:
        imports=A.rows(con,'SELECT id,account_id,year,filename,encoding,state,result_json,created_at,committed_at,source_kind,statement_document_id FROM bank_imports WHERE year=? AND archived=0 ORDER BY created_at DESC',(year,))
        transfers=A.rows(con,'SELECT t.*,o.booked_on AS outgoing_date,i.booked_on AS incoming_date,oa.name AS outgoing_account,ia.name AS incoming_account FROM bank_transfers t JOIN bank_rows o ON o.id=t.outgoing_id JOIN bank_rows i ON i.id=t.incoming_id JOIN bank_accounts oa ON oa.id=o.account_id JOIN bank_accounts ia ON ia.id=i.account_id WHERE o.booked_on LIKE ? OR i.booked_on LIKE ? ORDER BY t.created_at DESC',(str(year)+'%',str(year)+'%'))
        candidates=[p for p in pair_candidates(con) if p['outgoing']['booked_on'].startswith(str(year)) or p['incoming']['booked_on'].startswith(str(year))]
        unpaired=A.rows(con,"SELECT b.id,b.booked_on,b.amount_cents,b.partner,a.name FROM bank_rows b JOIN bank_accounts a ON a.id=b.account_id WHERE b.classification='transfer' AND b.booked_on LIKE ? AND NOT EXISTS(SELECT 1 FROM bank_transfers t WHERE t.outgoing_id=b.id OR t.incoming_id=b.id)",(str(year)+'%',))
    for item in imports:
        item['result']=json.loads(item.pop('result_json')) if item['result_json'] else None
    return {'accounts':accounts(),'imports':imports,'transfers':transfers,'candidates':candidates,'unpaired':unpaired}


def transaction_values(payload, method=None):
    aid=payload.get('account_id') or None
    if aid and not any(a['id']==aid for a in accounts()):
        raise ValueError('Konto nicht gefunden.')
    if method == 'cash' and aid:
        raise ValueError('Barausgaben dürfen keinem Bankkonto zugeordnet werden.')
    return {'account_id':aid}


def protect_bank_transaction(before,after):
    if not before.get('bank_row_id'):
        return
    for key in ['amount_cents','paid_on','direction','account_id']:
        if before.get(key)!=after.get(key):
            raise ValueError('Datum, Betrag, Richtung und Konto einer importierten Bankbuchung bleiben unverändert. Eine Korrektur bitte separat dokumentieren.')
    if before['scope']=='transfer' and after['scope']!='transfer':
        raise ValueError('Ein erkannter Eigenübertrag darf nicht als Einnahme/Ausgabe umklassifiziert werden.')


def usable_on(account, day):
    return (not account.get('opened_on') or day>=account['opened_on']) and (account['status']!='closed' or bool(account.get('closed_on')) and day<=account['closed_on'])


def save_preview(payload):
    iid=A.clean(payload.get('id'),80)
    edits=payload.get('edits',{})
    if not isinstance(edits,dict): raise ValueError('Ungültige Vorschauänderung.')
    with A.WRITE_LOCK,A.db() as con:
        batch=con.execute('SELECT * FROM bank_imports WHERE id=?',(iid,)).fetchone()
        require_active(batch)
        if not batch or batch['state'] not in {'preview','partial'}: raise ValueError('Diese Vorschau kann nicht mehr geändert werden.')
        if batch['state']=='partial' and not json.loads(batch['preview_json']).get('pdf_pending_selection'):raise ValueError('Bitte zuerst einen offenen Monat auswählen.')
        data=json.loads(batch['preview_json'])
        for row in data['rows']:
            edit=edits.get(str(row['line']))
            if edit is None: continue
            if not isinstance(edit,dict): raise ValueError('Ungültige Zeilenänderung.')
            scope=edit.get('scope',row['scope']); category=edit.get('category',row.get('category','Unsortiert'))
            if scope not in SCOPES or category not in A.CATEGORIES: raise ValueError('Ungültige Einordnung.')
            if row['classification']=='transfer' and scope!='transfer': raise ValueError('Erkannte Eigenüberträge bleiben neutral.')
            row.update(scope=scope,category=category,review_note=A.clean(edit.get('review_note',row.get('review_note','')),2000),user_reviewed=True)
            if 'choice' in edit:
                choice=edit['choice']
                if not isinstance(choice,str) or choice not in {'create','skip','review','force_new'} and not re.fullmatch(r'link:[a-f0-9]{32}',choice): raise ValueError('Ungültige Übernahmeauswahl.')
                row['choice']=choice
        con.execute('UPDATE bank_imports SET preview_json=? WHERE id=?',(A.enc(data),iid))
        A.audit(con,'review','bank_import',iid,after={'changed_lines':list(edits)})
    return saved_preview(iid)


def check_account_date(values, before=None):
    aid=values.get('account_id')
    if not aid:return
    if before and aid==before.get('account_id') and values['paid_on']==before.get('paid_on'):return
    account=next(a for a in accounts() if a['id']==aid)
    if not usable_on(account, values['paid_on']):
        raise ValueError('Zahlungsdatum liegt außerhalb des Kontozeitraums. Das archivierte Konto ist nur für frühere Buchungen verfügbar.')
