'use strict';
// Annual review reads persisted records. Accounting values are never model prose.
function annualSummary(c){
 const r=c.annual;if(!r)return '';
 const b=r.summary.scopes.find(s=>s.scope==='business');
 return `<section class="annual-card" aria-label="Berechnete Zahlungsübersicht"><div class="annual-heading"><strong>Zahlungen ${r.year}</strong><span class="tag">${r.summary.count} gespeichert</span></div><div class="annual-values"><div><small>Betriebliche Einnahmen</small><strong>${money(b.income_cents)}</strong></div><div><small>Betriebliche Ausgaben</small><strong>${money(b.expense_cents)}</strong></div><div><small>Zahlungssaldo</small><strong>${money(b.balance_cents)}</strong></div></div><p class="small muted">Vom Programm berechnet, nach deiner Einordnung. Zahlungssummen, keine fertigen EÜR-Werte.</p>${annualReaderProgress(r)}<p class="small muted">${r.coverage.unlinked_business_receipts} betriebliche/gemischte Zahlungen ohne gesonderte Belegverknüpfung.</p><div class="actions section-gap">${button('Zahlungen und Prüfpunkte','annual-report','file','small',`data-id="${c.id}"`)}</div></section>`;
}

function annualRoleState(r,role){
 const state=r.role_states?.[role]||'pending';
 return {complete:'Abgeschlossen',running:'Läuft gerade',error:'Unterbrochen',pending:'Wartet'}[state]||'Wartet';
}
function annualReaderProgress(r){return `<div class="annual-readers" aria-label="Fortschritt der Jahresprüfung">${[['worker','Arbeiter'],['reviewer','Prüfer'],['coordinator','Zusammenfassung']].map(([role,label])=>`<div class="annual-reader ${esc(r.role_states?.[role]||'pending')}"><span>${label}</span><strong>${role==='coordinator'?annualRoleState(r,role):`${r.reader_counts[role]} von ${r.summary.count}`}</strong>${role==='coordinator'?'':`<small>${annualRoleState(r,role)}</small>`}</div>`).join('')}</div>`;}
function annualRoleResult(c,role){
 if(!c.annual)return answerMarkup(c[role+'_json']);
 const r=c.annual;
 return `<p class="small">${r.reader_counts[role]} von ${r.summary.count} gespeicherten Buchungen beantwortet · ${annualRoleState(r,role)}.</p><p class="small muted">${r.reader_counts[role]?'Die gespeicherten Einzelhinweise findest du unter „Zahlungen und Prüfpunkte“.':'Von diesem Leser liegt noch keine vollständige Rückmeldung vor.'}</p>`;
}
function annualError(c){
 if(!c.annual)return `<div class="form-error">${esc(c.error)}</div>`;
 const r=c.annual, role=Object.entries(r.role_states||{}).find(([,s])=>s==='error')?.[0];
 const label={worker:'Der Arbeiter',reviewer:'Der Prüfer',coordinator:'Die Zusammenfassung'}[role]||'Die Prüfung';
 return `<div class="form-error"><strong>${label} konnte den nächsten Abschnitt noch nicht abschließen.</strong><p class="small">Deine Eingaben und fertigen Prüfschritte sind gespeichert. Mit „Prüfung fortsetzen“ wird nur der offene Teil erneut geprüft.</p><details class="source-details"><summary>Genaue Fehlermeldung</summary><p>${esc(c.error)}</p></details></div>`;
}

const annualBaseChatView=chatView;
chatView=function(){return annualBaseChatView().replace('<span class="tag">3 lokale Modelle</span>',button(`Jahr ${app.year} prüfen`,'start-annual','spark','small'));};

chatHistory=function(){
 const items=app.chatYear===app.year?app.chatItems:[];
 if(!items.length)return `<div class="chat-empty"><span class="chat-orb">✦</span><h3>Ein klarer nächster Schritt.</h3><p>Stelle eine einzelne Frage oder wähle „Jahr ${app.year} prüfen“.<br>Die Jahresprüfung geht alle gespeicherten Buchungen durch.</p></div>`;
 return items.map(c=>`<article class="chat-turn"><div class="user-bubble">${esc(c.question)}</div><div class="chat-meta">${stamp(c.created_at)} · Arbeitsjahr ${c.year}</div><div class="assistant-bubble">${annualSummary(c)}${['queued','running'].includes(c.state)?`<p class="progress-label"><span class="spinner"></span>${esc(c.progress||'Prüfung startet …')}</p><p class="small muted">Fertige Prüfschritte werden einzeln gespeichert. Du kannst in der Anwendung weiterarbeiten.</p>`:c.state==='error'?`${annualError(c)}<div class="actions section-gap">${c.can_resume&&!c.context_stale?button('Prüfung fortsetzen','resume-chat','spark','primary small',`data-id="${c.id}"`):''}${button('Mit aktuellem Stand neu prüfen','restart-chat','','small',`data-id="${c.id}"`)}</div>`:c.legacy_annual?`<p class="answer-warning">Diese alte Jahresantwort beruht auf einer begrenzten Buchungsauswahl und kann falsche Euro-Summen enthalten. Bitte oben „Jahr ${c.year} prüfen“ starten.</p><details class="source-details"><summary>Alte Antwort ansehen · nicht als Arbeitsgrundlage verwenden</summary>${answerMarkup(c.coordinator_json)}</details>`:answerMarkup(c.coordinator_json)}${c.context_stale?'<p class="answer-warning">Daten oder Quellen wurden seit dieser Prüfung geändert. Dieser gespeicherte Bericht zeigt den damaligen Stand. Bitte neu prüfen.</p>':''}${!c.legacy_annual&&c.coordinator_json?.tasks?.length?`<div class="actions section-gap">${c.coordinator_json.tasks.map((t,i)=>button(esc(t.title),'chat-task','plus','small',`data-id="${c.id}" data-index="${i}"`)).join('')}</div>`:''}<details class="source-details"><summary>Einzelauswertungen & Kontext</summary><h3>Arbeiter</h3>${annualRoleResult(c,'worker')}<h3>Unabhängiger Prüfer</h3>${annualRoleResult(c,'reviewer')}<h3>Datenumfang und Quellen</h3><p class="small muted">${esc(c.coverage)}</p><p class="small muted">${c.sources.map(s=>esc(s.title)+(s.excerpt?' (Auszug)':'')).join(' · ')||'Keine Dokumentquelle ausgewählt.'}</p></details></div></article>`).join('');
};

function annualTotalsTable(rows,monthly=false){return `<div class="annual-table-scroll"><table class="annual-table"><thead><tr><th>${monthly?'Monat':'Einordnung'}</th><th>Anzahl</th><th>Eingänge</th><th>Ausgänge</th></tr></thead><tbody>${rows.map(s=>`<tr><th>${monthly?esc(s.month):esc(s.label)}</th><td>${s.count}</td><td>${money(s.income_cents)}</td><td>${money(s.expense_cents)}</td></tr>`).join('')}</tbody></table></div>`;}

function annualReportMarkup(r,filter){
 const selected=r.rows.filter(x=>filter==='all'||x.needs_review);
 const groups=new Map();for(const row of selected){const key=row.paid_on.slice(0,7);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
 return `<div class="modal-body annual-report"><p class="small muted">Gespeicherter Stand vom ${stamp(r.created_at)} · ${r.summary.count} Buchungen</p>${r.stale?'<p class="answer-warning">Seitdem wurden Angaben geändert. Für den aktuellen Stand eine neue Jahresprüfung starten.</p>':''}<section class="annual-report-intro"><h3>Deine Zahlungsübersicht</h3><p class="small muted">Alle aktiven Zahlungen dieses Jahres, ohne Schätzung. Private Zahlungen und Eigenüberträge bleiben getrennt. Gemischte Beträge sind noch nicht nach Anteil aufgeteilt.</p>${annualTotalsTable(r.summary.scopes)}<details class="source-details"><summary>Alle Monate · Bank und Bar zusammen</summary><p class="small muted">Enthält alle Einordnungen; keine Kontostandsprüfung.</p>${annualTotalsTable(r.summary.months,true)}</details></section><div class="annual-coverage"><strong>Was wurde gelesen?</strong><p>Arbeiter ${r.reader_counts.worker}/${r.summary.count} · Prüfer ${r.reader_counts.reviewer}/${r.summary.count}. Vollständige Rückmeldungen je übergebenem Buchungsdatensatz, einschließlich Einordnung und Belegstatus.</p><p>${r.coverage.linked_receipts} Zahlungen mit gesonderter Belegverknüpfung · ${r.coverage.bank_evidence} mit zugeordnetem Banknachweis. Originalbelege hier nicht vollständig gelesen.</p></div>${r.checks.length?`<div class="answer-warning"><strong>Für das Jahr klären</strong><ul>${r.checks.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}<h3>Zahlungen und Prüfpunkte</h3><p class="small muted">Öffne einen Monat. „Kein weiterer KI-Hinweis“ bestätigt keine Absetzbarkeit. Hinweise ändern deine Daten nicht.</p><div class="scope-tabs section-gap">${button(`Offene Punkte (${r.open_count})`,'annual-filter','',filter==='open'?'selected':'',`data-filter="open"`)}${button(`Alle (${r.summary.count})`,'annual-filter','',filter==='all'?'selected':'',`data-filter="all"`)}</div><div class="annual-months">${[...groups].map(([month,rows],i)=>`<details class="annual-month"${i===0?' open':''}><summary>${new Date(month+'-01T12:00:00').toLocaleDateString('de-DE',{month:'long',year:'numeric'})}<span>${rows.length} Zahlungen</span></summary>${rows.map(row=>`<article class="annual-row"><div class="annual-row-heading"><div><small>${fmtDate(row.paid_on)} · ${row.ref}</small><strong>${esc(row.partner)}</strong><span>${esc(row.title)}</span></div><strong class="annual-amount">${row.direction==='income'?'+':'−'} ${money(row.amount_cents)}</strong></div><div class="detail-meta"><span class="tag">${esc(scopeNames[row.scope])}</span>${!row.both_read?'<span class="tag amber">KI-Prüfung noch offen</span>':row.disagreement?'<span class="tag amber">Leser beurteilen unterschiedlich</span>':''}</div><p class="small muted">${esc(row.receipt_status)}${row.bank_evidence?' · Banknachweis zugeordnet.':''}</p>${row.issues.length?`<ul class="annual-issues">${row.issues.map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:''}<details class="source-details"><summary>KI-Hinweise und gespeicherte Notizen</summary>${[['Arbeiter',row.worker],['Prüfer',row.reviewer]].map(([name,x])=>`<p><strong>${name}</strong> · ${x?esc(x.note):'Noch keine vollständige Rückmeldung.'}</p>`).join('')}${Object.values(row.notes).map(n=>`<p class="small muted">${esc(n)}</p>`).join('')}${row.text_excerpts.length?'<p class="small muted">Lange Notizen hier nur auszugsweise. Vollständige Angaben bei der Zahlung.</p>':''}</details><div class="actions section-gap">${button('Zahlung öffnen','annual-transaction','edit','small',`data-id="${esc(row.id)}"`)}</div></article>`).join('')}</details>`).join('')||'<p class="small muted">Keine Position in diesem Filter. Die fachliche Jahresprüfung bleibt davon unabhängig.</p>'}</div><p class="small muted section-gap">${esc(r.limitation)}</p><div class="actions">${button('Gespeicherten Bericht neu laden','annual-report','','small',`data-id="${r.id}"`)}</div></div>`;
}

const annualBaseAction=action;
action=async function(name,el){
 if(name==='annual-filter'){app.annualFilter=el.dataset.filter;showModal('Jahresprüfung · '+app.annualReport.year,annualReportMarkup(app.annualReport,app.annualFilter));return;}
 if(name==='annual-transaction'){await refresh();if(!app.data.transactions.some(t=>t.id===el.dataset.id))return toast('Diese Zahlung ist inzwischen archiviert. Der Bericht zeigt den früheren Stand.',true);return transactionForm(el.dataset.id);}
 if(['start-annual','resume-chat','restart-chat','annual-report'].includes(name)){
  el.disabled=true;
  try{
   if(name==='annual-report'){const r=await api('/api/chat/report?id='+encodeURIComponent(el.dataset.id));app.annualReport=r;app.annualFilter='open';showModal('Jahresprüfung · '+r.year,annualReportMarkup(r,'open'));return;}
   if(name==='resume-chat')await api('/api/chat/resume',{id:el.dataset.id});
   else if(name==='restart-chat'){const c=app.chatItems.find(x=>x.id===el.dataset.id);await api('/api/chat',{year:c.year,question:c.question,document_ids:[],mode:c.annual||c.legacy_annual?'annual':'question'});}
   else await api('/api/chat',{year:app.year,question:`Jahresprüfung ${app.year}: Prüfe alle gespeicherten Buchungen zur Vorbereitung meiner EÜR. Welche konkreten Angaben muss ich noch klären?`,document_ids:[],mode:'annual'});
   await loadChat();toast(name==='resume-chat'?'Gespeicherte Prüfung wird fortgesetzt.':'Jahresprüfung gestartet. Die Fortschritte bleiben gespeichert.');
  }catch(e){toast(e.message,true);}finally{el.disabled=false;}
  return;
 }
 return annualBaseAction(name,el);
};
