"""Conservative reading of Volksbank VR-GiroBusiness text tables.

Only dated, signed table rows are payments. All amounts remain integer cents.
Unknown layouts return None so the generic reader can handle them explicitly.
"""
import copy
import re
import hashlib
import unicodedata
from collections import Counter
from datetime import date
import banking

DATE=r'\d{2}\.\d{2}\.(?:\d{4})?'
MONEY=r'(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}'
ROW=re.compile(r'^\s*('+DATE+r')\s+('+DATE+r')\s+(.+?)\s+('+MONEY+r')\s*([SH])\s*$')
START=re.compile(r'^\s*'+DATE+r'\s+'+DATE+r'\s+')
STOP=re.compile(r'^\s*(?:Übertrag (?:auf|von)|neuer Kontostand|Bitte beachten|\d{4}$|K\d{5,})',re.I)
SINGLE_ROW=re.compile(r'^\s*('+DATE+r')\s+(?!'+DATE+r'\s)(.+?\bPN:\s*\d+.*?)\s+('+MONEY+r')\s*([SH])\s*$')

def normalized(value):
    return ' '.join(unicodedata.normalize('NFKC',value).replace('\u00ad','').split()).casefold()

def cents(amount,sign):return banking.signed_cents(amount)*(-1 if sign=='S' else 1)
def money(c):return ('-' if c<0 else '')+str(abs(c)//100)+','+str(abs(c)%100).zfill(2)

def day(value,year,end_month=None):
    bits=value.rstrip('.').split('.');d,m=map(int,bits[:2])
    y=int(bits[2]) if len(bits)==3 else year
    if len(bits)==2 and end_month==1 and m==12:y-=1
    return date(y,m,d).isoformat()

def page_identity(page):
    """Read a statement header independently of its transaction-table layout.

    Never derive the statement/account from amounts, row dates or a merchant's
    IBAN. Ambiguous headers do not become evidence for merging pages.
    """
    text=page['text']
    header=re.split(r'Bu-Tag|Buchungstag|^\s*'+DATE+r'\s+',text,maxsplit=1,flags=re.M|re.I)[0]
    refs=list(re.finditer(r'\bKontoauszug\s*(?:Nr\.?|Nummer)\s*:?\s*(\d{1,3})\s*/\s*(20\d{2})\b',header,re.I))
    keys={m[2]+'-'+str(int(m[1])) for m in refs}
    ibans={re.sub(r'\s','',m).upper() for m in re.findall(r'\bIBAN\s*:\s*([A-Z]{2}\d{2}(?:[ \t]*\d){18})',header,re.I)}
    accounts={re.sub(r'\s','',m) for m in re.findall(r'\bKontonummer\s*:?\s*([\d][\d \t]*\d)\b',header,re.I)}
    currencies={m.upper() for m in re.findall(r'\b([A-Z]{3})\s*-?\s*Konto\b',header,re.I)}
    ambiguous=len(keys)>1 or len(ibans)>1 or len(accounts)>1 or len(currencies)>1
    return {'key':next(iter(keys)) if len(keys)==1 else '',
            'own_iban':next(iter(ibans)) if len(ibans)==1 else '',
            'account_number':next(iter(accounts)) if len(accounts)==1 else '',
            'currency':next(iter(currencies)) if len(currencies)==1 else '',
            'quote':refs[0][0] if len(keys)==1 else '', 'ambiguous':ambiguous}

def attach_statement_pages(checks,pages):
    """Attach unfamiliar continuation layouts by explicit header identity only."""
    checks=copy.deepcopy(checks);by_page={p['page']:p for p in pages}
    assigned={number for c in checks for number in c['pages']}
    for page in pages:
        number=page['page']
        if number in assigned:continue
        identity=page_identity(page)
        if identity['ambiguous'] or not identity['key'] or identity['currency'] not in ('','EUR'):continue
        matches=[]
        for check in checks:
            header_ids=[page_identity(by_page[p]) for p in check['pages'] if p in by_page]
            keys={x['key'] for x in header_ids if x['key']}
            if keys!={identity['key']} or any(x['ambiguous'] for x in header_ids):continue
            if any(identity[field] and x[field] and identity[field]!=x[field]
                   for x in header_ids for field in ('own_iban','account_number','currency')):continue
            # Repeated end balances are evidence too, not values to ignore in
            # order to make an apparent match. A contradictory page stays open.
            controls=page_controls(page)
            if any(check.get(field) is not None and check[field]!=value
                   for field,value in controls.items() if not field.endswith('_quote')):continue
            matches.append(check)
        if len(matches)!=1:continue
        check=matches[0];check['pages']=sorted(set(check['pages'])|{number});assigned.add(number)
        check.setdefault('page_links',[]).append({'page':number,'quote':identity['quote'],
            'message':f"Seite {number} gehört laut Auszugsnummer zum selben Kontoauszug und wird hier mitgerechnet."})
    return checks

def page_controls(page):
    controls={}
    for line in page['text'].splitlines():
        stripped=' '.join(line.split())
        for field,label in [('opening_cents','alter Kontostand'),('closing_cents','neuer Kontostand')]:
            if re.search(label,stripped,re.I):
                match=re.search('('+MONEY+r')\s*([SH])\s*$',stripped)
                if match:controls[field]=cents(match[1],match[2]);controls[field+'_quote']=line.strip()
        if 'Gesamtumsatz:' in stripped:
            for amount,sign in re.findall('('+MONEY+r')\s*([SH])',stripped):
                field='debit_cents' if sign=='S' else 'credit_cents'
                controls[field]=abs(cents(amount,sign));controls[field+'_quote']=line.strip()
    return controls

def partial_page_rows(page):
    """Provable signed PN booking lines on an otherwise unfamiliar bank page.

    This does NOT claim that the entire page or document has been extracted.
    The posting day is the first date, never the fee period's end date.
    """
    identity=page_identity(page)
    if identity['ambiguous'] or not identity['key'] or identity['currency'] not in ('','EUR'):return []
    year=int(identity['key'].split('-')[0]);lines=page['text'].splitlines();found=[]
    dates=re.findall(r'\berstellt am\s+\d{2}\.(\d{2})\.'+str(year)+r'\b',page['text'],re.I)
    end_month=int(dates[0]) if len(set(dates))==1 else None
    for index,line in enumerate(lines):
        two=ROW.match(line);single=SINGLE_ROW.match(line)
        if two and re.search(r'\bPN:\s*\d+',two[3]):
            booked,value,description,amount,sign=two.groups()
        elif single:
            booked,description,amount,sign=single.groups();value=booked
        else:continue
        try:booked=day(booked,year,end_month);value=day(value,year,end_month)
        except ValueError:continue
        quote=line.strip();amount=cents(amount,sign)
        purpose=re.sub(r'\s+PN:.*$','',description).strip()
        source=hashlib.sha256((str(page['page'])+':partial:'+str(index)+':'+quote).encode()).hexdigest()[:24]
        found.append({'page':page['page'],'booked_on':booked,'value_on':value,'amount':money(amount),
            'amount_cents':amount,'currency':'EUR','partner':'Kontoführung und Bankgebühren' if purpose.casefold()=='abschluss' else purpose,
            'purpose':purpose,'quote':quote,'statement_key':identity['key'],'source_id':source,
            'own_iban':identity['own_iban'],'source_method':'volksbank_signed_line'})
    return found

def source_rows(page):
    parsed=parse_page(page)
    return parsed['rows'] if parsed is not None else partial_page_rows(page)

def parse_page(page):
    text=page['text'];lines=text.splitlines()
    if not re.search(r'Bu-Tag\s+Wert\s+Vorgang',text):return None
    if not re.search(r'EUR\s*-?\s*Konto',text,re.I):return None
    nr=re.search(r'\bNr\.\s*(\d{1,3})/(20\d{2})\b',text)
    if not nr:return None
    year=int(nr[2]);key=nr[2]+'-'+nr[1]
    header=text.split('Bu-Tag')[0];header_dates=re.findall(r'\b\d{2}\.(\d{2})\.'+str(year)+r'\b',header)
    end_month=int(header_dates[0]) if header_dates else None
    own=re.search(r'IBAN:\s*([A-Z]{2}\d{2}(?:[ \t]*\d){18})',header)
    own_iban=re.sub(r'\s','',own[1]) if own else ''
    matches=[]
    for i,line in enumerate(lines):
        if START.match(line):
            match=ROW.match(line)
            if not match:return None  # Do not silently skip a malformed payment line.
            matches.append((i,match))
        elif SINGLE_ROW.match(line):return None  # Not the two-date table layout.
    # A continuation page can contain only fee explanations or control totals.
    rows=[]
    for n,(idx,m) in enumerate(matches):
        end=matches[n+1][0] if n+1<len(matches) else len(lines)
        block=[lines[idx].rstrip()]
        for line in lines[idx+1:end]:
            if STOP.match(line):break
            if line.strip():block.append(line.rstrip())
        quote='\n'.join(block).strip()
        if len(quote)>4000:return None
        description=re.sub(r'\s+PN:\S+.*$','',m[3]).strip()
        details=[' '.join(x.split()) for x in block[1:]]
        partner=details[0] if details else description
        if 'kartenzahlung' in description.casefold() and len(details)>1 and 'bank' in partner.casefold():partner=details[1]
        if description.casefold()=='abschluss':partner='Kontoführung und Bankgebühren'
        purpose=description
        if details and 'überw' in description.casefold() and len(details)>1:purpose=details[1]
        purpose=re.split(r'\s+(?:IBAN:|BIC:|TAN1:)',purpose)[0][:160]
        try:booked=day(m[1],year,end_month);value=day(m[2],year,end_month)
        except ValueError:return None
        amount=cents(m[4],m[5]);source_id=hashlib.sha256((str(page['page'])+':'+str(idx)+':'+quote).encode()).hexdigest()[:24]
        rows.append({'page':page['page'],'booked_on':booked,'value_on':value,'amount':money(amount),'amount_cents':amount,'currency':'EUR','partner':partner[:200],'purpose':purpose,'quote':quote,'statement_key':key,'source_id':source_id,'own_iban':own_iban,'source_method':'volksbank_table'})
    balances={}
    for line in lines:
        stripped=' '.join(line.split())
        for field,pattern in [('opening_cents',r'alter Kontostand'),('closing_cents',r'neuer Kontostand')]:
            if re.search(pattern,stripped,re.I):
                found=re.search('('+MONEY+r')\s*([SH])\s*$',stripped)
                if found:balances[field]=cents(found[1],found[2]);balances[field+'_quote']=line.strip()
        if 'Gesamtumsatz:' in stripped:
            for amount,sign in re.findall('('+MONEY+r')\s*([SH])',stripped):
                field='debit_cents' if sign=='S' else 'credit_cents';balances[field]=abs(cents(amount,sign));balances[field+'_quote']=line.strip()
    return {'rows':rows,'key':key,**balances}

def parse_document(pages):
    if not pages:return None
    rows=[];groups={};page_status=[]
    for page in pages:
        parsed=parse_page(page)
        if parsed is None:
            # This exact appendix contains legal explanations, not payments.
            if rows and re.search(r'Sehr geehrte Kundin, sehr geehrter Kunde',page['text']) and 'Rechnungsabschlüsse' in page['text'] and not any(START.match(x) for x in page['text'].splitlines()):
                page_status.append({'page':page['page'],'state':'notes','count':0});continue
            return None
        rows.extend(parsed['rows']);group=groups.setdefault(parsed['key'],{'key':parsed['key'],'pages':[]})
        own=next((r['own_iban'] for r in parsed['rows'] if r['own_iban']),group.get('own_iban',''))
        if group.get('own_iban') and own!=group['own_iban']:return None
        group['own_iban']=own
        for row in parsed['rows']:row['own_iban']=own
        group['pages'].append(page['page'])
        for key,value in parsed.items():
            if key not in {'rows','key'}:
                if key in group and not key.endswith('_quote') and group[key]!=value:return None
                group[key]=value
        page_status.append({'page':page['page'],'state':'read','count':len(parsed['rows'])})
    checks=[];issues=[]
    for key,group in groups.items():
        subset=[r for r in rows if r['statement_key']==key]
        incoming=sum(r['amount_cents'] for r in subset if r['amount_cents']>0)
        outgoing=-sum(r['amount_cents'] for r in subset if r['amount_cents']<0)
        opening=group.get('opening_cents');closing=group.get('closing_cents')
        diff=closing-opening-incoming+outgoing if opening is not None and closing is not None else None
        totals_ok=all(group.get(field) is None or group[field]==value for field,value in [('credit_cents',incoming),('debit_cents',outgoing)])
        checks.append({**group,'incoming_cents':incoming,'outgoing_cents':outgoing,'difference_cents':diff,'totals_ok':totals_ok})
        if diff not in {None,0} or not totals_ok:issues.append(f'Auszug {key}: Erkannte Zahlungen passen noch nicht zu Kontostand oder Umsatzsummen.')
        if diff is None and (group.get('credit_cents') is None or group.get('debit_cents') is None):issues.append(f'Auszug {key}: Vollständigkeit zusätzlich am Original prüfen; Kontrollsummen fehlen.')
    first=checks[0] if len(checks)==1 else {}
    return {'rows':rows,'readings':[],'issues':issues,'balance_checks':checks,'page_status':page_status,'all_pages_read':True,'source_method':'volksbank_table','opening_cents':first.get('opening_cents'),'closing_cents':first.get('closing_cents'),'difference_cents':first.get('difference_cents'),'summary':'Zahlungen direkt aus der Volksbank-Tabelle gelesen. S = Auszahlung, H = Einzahlung. Bitte Einordnung wählen und am Original prüfen.'}

def locate(row,page):
    parsed=parse_page(page)
    if parsed is None:
        candidates=partial_page_rows(page)
        if not candidates:return None
        # Other, unrecognised payment formats may still use literal quote proof.
        tokens=set(re.findall(r'[\w]{4,}',normalized(str(row.get('purpose',''))+' '+str(row.get('quote','')))))
        if not any(tokens & set(re.findall(r'[\w]{4,}',normalized(r['quote']))) for r in candidates):return None
        parsed={'rows':candidates}
    amount=banking.signed_cents(row.get('amount',''))
    numeric=[r for r in parsed['rows'] if r['booked_on']==row.get('booked_on') and r['amount_cents']==amount]
    source=row.get('source_id');quote=normalized(str(row.get('quote','')))
    matches=[r for r in numeric if r['source_id']==source] if source else numeric
    exact=[r for r in matches if quote and quote in normalized(r['quote'])]
    if len(exact)==1:return exact[0]
    if len(matches)==1:
        candidate=matches[0]
        tokens=[t for t in re.findall(r'[\w]{3,}',normalized(str(row.get('partner',''))+' '+str(row.get('purpose','')))) if not t.isdigit()]
        if any(t in normalized(candidate['quote']) for t in tokens):return candidate
    # A stale internal hash must not reject a uniquely identical original row.
    # Repair only the reference; never change date, amount, sign or an ambiguous match.
    if source and not any(r['source_id']==source for r in parsed['rows']):
        exact=[r for r in numeric if quote and quote==normalized(r['quote'])]
        if len(exact)==1:return exact[0]
    raise ValueError(f"Seite {page['page']}: Datum, Betrag oder Soll/Haben passen nicht eindeutig zu einer Originalzeile. Bitte diese Zahlung prüfen.")


def diagnose(row,pages,message,index):
    """Explain source mismatches using actual source rows, never model guesses."""
    try:amount=banking.signed_cents(row.get('amount',''))
    except (ValueError,TypeError):amount=None
    quote=normalized(str(row.get('quote','')));page=row.get('page');source=row.get('source_id')
    original=[]
    for p in pages:
        original.extend(source_rows(p))
    tokens=set(re.findall(r'[\w]{4,}',normalized(str(row.get('partner',''))+' '+str(row.get('purpose','')))))
    scored=[]
    for candidate in original:
        same_source=bool(source and source==candidate['source_id'])
        exact_quote=bool(quote and quote==normalized(candidate['quote']))
        shared=bool(tokens&set(re.findall(r'[\w]{4,}',normalized(candidate['quote']))))
        same_day=candidate['booked_on']==row.get('booked_on')
        same_value=candidate['value_on']==row.get('booked_on')
        same_amount=amount is not None and abs(amount)==abs(candidate['amount_cents'])
        if not(same_source or exact_quote or same_amount and (same_day or same_value or shared) or same_day and shared):continue
        score=1000*same_source+500*exact_quote+60*same_amount+25*same_day+10*same_value+10*shared+5*(candidate['page']==page)
        scored.append((score,candidate))
    scored.sort(key=lambda x:-x[0]);candidates=[]
    # With a still-valid reference, explain that actual source instead of unrelated guesses.
    if scored and scored[0][0]>=1000:
        scored=scored[:1]+[(score,c) for score,c in scored[1:] if quote and quote==normalized(c['quote']) or amount==c['amount_cents'] and row.get('booked_on')==c['booked_on']]
    for _,candidate in scored[:3]:
        differences=[];cause=[]
        if candidate['page']!=page: differences.append('page');cause.append(f"Die passende Originalstelle steht auf Seite {candidate['page']}, nicht auf Seite {page}.")
        if candidate['booked_on']!=row.get('booked_on'):
            differences.append('booked_on')
            cause.append('Das eingetragene Datum ist die Wertstellung. Für die Zahlungsliste wird der Buchungstag verwendet.' if candidate['value_on']==row.get('booked_on') else 'Der Buchungstag in der Originalzeile ist anders. Ein Datum im Abrechnungszeitraum ersetzt diesen Buchungstag nicht.')
        if candidate['amount_cents']!=amount:
            differences.append('amount')
            cause.append('Ein- und Auszahlung sind vertauscht: S bedeutet Auszahlung (Minus), H bedeutet Eingang (Plus).' if amount is not None and abs(amount)==abs(candidate['amount_cents']) else 'Der Betrag stimmt mit dieser Originalstelle nicht überein. Prüfe auch Komma und Tausenderpunkt.')
        if source!=candidate['source_id']:differences.append('source_id')
        if quote!=normalized(candidate['quote']):differences.append('quote')
        if not cause:cause.append('Datum und Betrag passen. Die Fundstelle oder interne Zuordnung ist aber nicht eindeutig. Wähle die tatsächlich gemeinte Originalzeile.')
        match='reference' if source==candidate['source_id'] else 'quote' if quote==normalized(candidate['quote']) else 'possible'
        candidates.append({**candidate,'differences':differences,'explanation':('Mögliche Ursache: ' if match=='possible' else '')+' '.join(cause),'match':match})
    reason='Die Zuordnung zum Original ist nicht eindeutig; das muss kein falsch eingetragener Betrag sein.'
    if candidates and len(candidates)==1:reason=candidates[0]['explanation']
    elif candidates:reason='Mehrere Originalzeilen kommen infrage. Vergleiche Empfänger, Zweck und Originaltext und wähle die richtige Zeile.'
    else:
        p=next((p for p in pages if p['page']==page),None)
        fee=fee_detail_reason(row,p) if p else ''
        if fee:reason=fee+' Über „Auslassen → Keine eigene Zahlung“ entfernen.'
        elif p and parse_page(p) is not None:reason='Keine eindeutig passende gebuchte Zeile gefunden. Prüfe PDF-Seite und Originalstelle; möglicherweise wurde eine Gebührenaufschlüsselung oder ein Kontostand als Zahlung gelesen.'
        else:reason='Für dieses Layout fehlt ein verlässlicher Textnachweis. Vergleiche Buchungstag, Vorzeichen und die wörtliche Originalstelle. Ein Scan oder umformulierter KI-Text kann die Zuordnung verhindern.'
    return {'index':index,'page':page,'entered':{k:row.get(k,'') for k in ['booked_on','amount','partner','purpose','quote']},'message':message,'explanation':reason,'candidates':candidates,'candidate_count':len(scored)}

def known_document(pages):
    """Keep source coverage and control totals when an appendix is unfamiliar."""
    known=[page for page in pages if parse_page(page) is not None]
    if not known:return None
    result=parse_document(known)
    if result is None:raise ValueError('Originaltabellen enthalten widersprüchliche Konto- oder Summenangaben. Bitte Auszug prüfen.')
    result['rows'].extend(r for p in pages if p not in known for r in partial_page_rows(p))
    result['balance_checks']=attach_statement_pages(result['balance_checks'],pages)
    # Refresh source totals after attaching provable rows from continuation pages.
    result['issues']=[]
    for check in result['balance_checks']:
        values=[r['amount_cents'] for r in result['rows'] if r['page'] in check['pages']]
        incoming=sum(v for v in values if v>0);outgoing=-sum(v for v in values if v<0)
        start=check.get('opening_cents');end=check.get('closing_cents')
        diff=end-start-incoming+outgoing if start is not None and end is not None else None
        totals_ok=all(check.get(f) in (None,v) for f,v in [('credit_cents',incoming),('debit_cents',outgoing)])
        check.update(incoming_cents=incoming,outgoing_cents=outgoing,difference_cents=diff,totals_ok=totals_ok)
        if diff not in (None,0) or not totals_ok:result['issues'].append(f"Auszug {check['key']}: Erkannte Zahlungen passen noch nicht zu Kontostand oder Umsatzsummen.")
    if len(result['balance_checks'])==1:result['difference_cents']=result['balance_checks'][0]['difference_cents']
    return result


def validate_coverage(rows,pages):
    parsed=known_document(pages)
    if parsed is None:return
    known_pages={p['page'] for p in parsed['page_status']}
    expected=[r['source_id'] for r in parsed['rows']]
    actual=[r.get('source_id') for r in rows if r.get('page') in known_pages or r.get('source_id') in expected]
    if Counter(expected)!=Counter(actual):
        missing=Counter(expected)-Counter(actual);repeated=Counter(actual)-Counter(expected)
        original={r['source_id']:r for r in parsed['rows']}
        def describe(ids):
            return '; '.join(f"Seite {original[s]['page']}: {original[s]['booked_on']} · {money(original[s]['amount_cents'])} € · {original[s]['partner']}" for s in list(ids)[:3] if s in original)
        detail=(' Fehlt: '+describe(missing)+'.' if missing else '')+(' Doppelt zugeordnet: '+describe(repeated)+'.' if repeated else '')
        raise ValueError('Eine echte Zahlung fehlt oder ist doppelt zugeordnet.'+detail+' Falls schon erfasst, „Schon erfasst / doppelt“ verwenden; zusätzlich gelesene Zeilen als „Keine eigene Zahlung“ auslassen.')
    if any(c['difference_cents'] not in {None,0} or not c['totals_ok'] for c in parsed['balance_checks']):
        raise ValueError('Die Saldenprüfung oder Umsatzsummen gehen noch nicht auf. Original und Vollständigkeit prüfen.')


def page_rows(page):
    """Known table pages are authoritative even inside otherwise unknown PDFs."""
    parsed=parse_page(page)
    return parsed['rows'] if parsed is not None else None


def fee_detail_reason(row,page):
    """Reject a quoted fee component only when it is in a marked breakdown.

    Full independent dated payment lines stay valid, including another bank fee.
    No merchant/category keywords alone decide that a payment is not real.
    """
    quote=str(row.get('quote','')).strip()
    if not quote:return ''
    lines=page['text'].splitlines()
    q=normalized(quote)
    # A dated S/H table row is independently checked by locate().
    if any(ROW.match(line) for line in quote.splitlines()):return ''
    if re.match(r'^\s*\d{2}\.\d{2}\.\d{4}\s+',quote):return ''
    starts=[i for i,line in enumerate(lines) if re.search(r'(?:Entgeltaufstellung|Entgeltabrechnung|Aufschl[üu]sselung|Zusammensetzung|Berechnung (?:des|der) (?:Abschluss|Entgelte|Geb[üu]hren)|Abrechnungsdetails)',line,re.I)]
    for start in starts:
        end=next((i for i in range(start+1,len(lines)) if START.match(lines[i]) or re.search(r'neuer Kontostand|Endsaldo|Kontostand am',lines[i],re.I)),len(lines))
        block='\n'.join(lines[start:end])
        if q not in normalized(block):continue
        if not re.search(r'(?:Kontof[üu]hrung|Grundpreis|Postenpreis|Buchungsposten|beleghaft|beleglos|Entgelt|Preis pro|Einzelpreis|Abschlussposten|Kartengeb[üu]hr)',quote,re.I):continue
        return 'Gebührenaufschlüsselung: Bestandteil des Abschlussbetrags, keine zusätzliche Zahlung.'
    return ''
