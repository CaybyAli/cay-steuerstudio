// Template/unit checks, not a substitute for real browser QA.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const element={addEventListener(){},content:'test',innerHTML:'',open:false};
const document={querySelector(){return element;},addEventListener(){}};
const context=vm.createContext({document,window:{addEventListener(){}},location:{hash:''},console,Intl,Date,Set,Array,String,Number,Math,Promise,JSON,Error,
  setTimeout,clearTimeout,fetch:async()=>({ok:false,json:async()=>({error:'No server in template test'})})});
vm.runInContext(fs.readFileSync('dist/app.js','utf8'),context);
vm.runInContext(`app.data={documents:[],transactions:[],tasks:[],settings:{active_year:2025,vat_status:'unknown',taxation:'unknown',filing_2025:'unknown',personal_notes:'',worker_model:'',reviewer_model:''}};`,context);
for(const name of ['overviewView','documentsView','transactionsView','tasksView','calendarView','settingsView']){
  const html=vm.runInContext(`${name}()`,context);
  assert(html.includes('<h1>'),name+' heading');
  assert(!/\bundefined\b|\bNaN\b/.test(html),name+' invalid value');
  assert(!/\sonclick=|\sonchange=|<script/.test(html),name+' inline execution');
}
assert.equal(vm.runInContext(`esc('<img src=x onerror="test">')`,context),'&lt;img src=x onerror=&quot;test&quot;&gt;');
assert.equal(vm.runInContext(`money(123456)`,context).replace(/\s/g,''),'1.234,56€');
vm.runInContext(`app.data.transactions=[{id:'a',direction:'expense',amount_cents:10,paid_on:'2025-04-01',partner:'<script>alert(1)</script>',title:'Test',document_ids:[],category:'Unsortiert'},{id:'b',direction:'expense',amount_cents:20,paid_on:'2025-04-02',partner:'Test',title:'Test',document_ids:[],category:'Unsortiert'}]`,context);
assert.equal(vm.runInContext('totals(txForYear()).expense',context),30);
assert(!vm.runInContext('transactionsView()',context).includes('<script>'));
assert(vm.runInContext('transactionsView()',context).includes('&lt;script&gt;'));
vm.runInContext(`app.data.transactions.push({id:'private',direction:'expense',amount_cents:30,paid_on:'2025-04-03',partner:'Privat',title:'Private Einzahlung',scope:'private',document_ids:[],category:'Privat'});`,context);
assert(vm.runInContext('transactionTable(app.data.transactions)',context).includes('Privat · kein Betriebsbeleg'));
vm.runInContext(`app.calendarYear=2026;app.calendarMonth=9;app.data.tasks=[{id:'t',year:2025,title:'Folgejahresfrist',kind:'Antwort',due_on:'2026-10-15',prepare_on:'',due_confirmed:1,status:'open'}]`,context);
assert(vm.runInContext('calendarView()',context).includes('Folgejahresfrist'));
assert(vm.runInContext('calendarView()',context).includes('Oktober 2026'));
assert.equal(vm.runInContext('app.year',context),2025);
for(const expr of ['documentForm()','transactionForm()','taskForm()']){
  element.open=true;
  vm.runInContext(expr,context);
  assert(element.innerHTML.includes('<form'),expr);
  assert(element.innerHTML.includes('type="submit"'),expr+' save');
  assert(!/\bundefined\b|\bNaN\b/.test(element.innerHTML),expr+' invalid value');
}
console.log('Frontend template checks passed: six views, three forms, escaping, exact cent totals.');
