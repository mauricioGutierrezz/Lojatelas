// Regresiones de interacción de los scripts reales, sin dependencias de navegador.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const script=name=>fs.readFileSync(path.join(__dirname,'../app_loja/static',name),'utf8');
class Element {
  constructor(value=''){this.value=value;this.hidden=false;this.disabled=false;this.dataset={};this.events={};this.attrs={};this.classes=new Set();
    this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)};}
  addEventListener(name,callback){this.events[name]=callback;}
  setAttribute(name,value){this.attrs[name]=value;}
  fire(name,event={}){return this.events[name]?.(event);}
}
function priceFilters(){
  const input=new Element(),status=new Element();
  const buttons=['','1','2'].map(category=>Object.assign(new Element(),{dataset:{category}}));
  const rows=['Petróleo','Petroleo algodón','Otro'].map((name,index)=>{
    const row=new Element(),price=new Element('100,00'),pending=new Element();
    row.dataset={name,category:index===0?'1':'2',original:'100.00'};
    row.querySelector=selector=>selector==='input'?price:pending;
    row.price=price;
    return row;
  });
  const document={querySelectorAll:selector=>selector==='[data-price-row]'?rows:buttons,
    getElementById:id=>id==='precio-buscar'?input:status};
  vm.runInNewContext(script('precios.js'),{document});
  rows[0].price.value='12.500';rows[0].price.fire('input');
  rows[1].price.value='120';rows[1].price.fire('input');
  input.value='petroleo';input.fire('input');buttons[2].fire('click');
  assert.deepEqual(rows.map(r=>r.hidden),[true,false,true]);
  assert.equal(status.textContent,'2 cambio(s) pendiente(s)');
  assert.equal(rows[0].price.value,'12.500');
  assert.equal(rows[0].price.disabled,false);
  assert.equal(buttons[2].attrs['aria-pressed'],'true');
  buttons[0].fire('click');
  assert.equal(input.value,'petroleo');
  assert.deepEqual(rows.map(r=>r.hidden),[false,false,true]);
  assert.equal(rows[1].price.value,'120');
}
async function cutSuggestions(){
  const sold=new Element('2,5'),cut=new Element('7,125'),button=new Element(),notice=new Element();
  const form=new Element();form.dataset={suggestionUrl:'/tickets/1/corte/1'};
  form.elements={quantidade_vendida:sold,quantidade_cortada:cut,q:new Element('lino'),categoria:new Element('1')};
  const area=new Element();
  let amounts=[Object.assign(new Element('3'),{id:'lote-1'}),Object.assign(new Element('4,125'),{id:'lote-2'})];
  let markers=[{remove:()=>{markers=[];}}];
  let review=new Element();
  area.querySelectorAll=selector=>selector==='[data-suggested]'?markers:selector==='[data-max-for]'?[]:amounts;
  area.querySelector=()=>review;
  Object.defineProperty(area,'innerHTML',{set:html=>{
    amounts=[Object.assign(new Element('99'),{id:'lote-1'}),Object.assign(new Element(''),{id:'lote-2'})];
    review=new Element();markers=[{remove:()=>{markers=[];}}];
  }});
  const elements={'corte-seleccion':form,'corte-sugerir':button,'corte-lotes':area,'corte-aviso':notice};
  const requests=[];
  const fetch=(url,options)=>new Promise(resolve=>requests.push({url,options,resolve}));
  vm.runInNewContext(script('corte.js'),{document:{getElementById:id=>elements[id]},fetch,URL,AbortController,location:{origin:'http://localhost'}});
  sold.value='9';sold.fire('input');
  assert.equal(cut.value,'7,125');assert.equal(review.disabled,true);assert.equal(markers.length,0);
  let prevented=false;
  const first=button.fire('click',{preventDefault:()=>{prevented=true;}});
  assert.equal(prevented,true);assert.equal(requests[0].url.searchParams.get('parcial'),'si');
  assert.equal(requests[0].url.searchParams.get('q'),'lino');
  // Una respuesta antigua, incluso si llega después del abort, no puede reactivar revisión.
  cut.value='8';cut.fire('input');
  assert.equal(requests[0].options.signal.aborted,true);
  requests[0].resolve({ok:true,status:200,text:async()=>'<fragmento antiguo>'});await first;
  assert.equal(review.disabled,true);assert.equal(amounts[1].value,'4,125');
  const second=button.fire('click',{preventDefault(){}});
  amounts[0].value='3,875'; // También conserva una edición hecha mientras llega la respuesta.
  requests[1].resolve({ok:true,status:200,text:async()=>'<fragmento actual>'});await second;
  assert.equal(review.disabled,false);assert.equal(amounts[0].value,'3,875');assert.equal(amounts[1].value,'4,125');
  assert.equal(sold.value,'9');assert.equal(cut.value,'8');
}
priceFilters();
function cutMax(){
  const sold=new Element('99'),cut=new Element('40'),area=new Element();
  const inputs=['5','10','25'].map((value,i)=>Object.assign(new Element(value),{id:'lote-'+i,name:'retirar'}));
  const buttons=['29','45','30'].map((balance,i)=>Object.assign(new Element(),{dataset:{balance,maxFor:inputs[i].id}}));
  area.querySelectorAll=selector=>selector==='[data-max-for]'?buttons:selector==='input[name="retirar"]'?inputs:[];
  area.querySelector=()=>null;
  const form=new Element();form.elements={quantidade_vendida:sold,quantidade_cortada:cut};
  const elements={'corte-seleccion':form,'corte-sugerir':new Element(),'corte-lotes':area,'corte-aviso':new Element()};
  vm.runInNewContext(script('corte.js'),{document:{getElementById:id=>elements[id]}});
  const click=i=>area.fire('click',{target:{closest:()=>buttons[i]}});
  const edit=(i,value)=>{inputs[i].value=value;area.fire('input',{target:inputs[i]});};
  const active=()=>buttons.map(b=>b.attrs['aria-pressed']==='true');
  assert.deepEqual(buttons.map(b=>b.disabled),[true,false,true]);
  click(0);assert.deepEqual(inputs.map(i=>i.value),['5','10','25']);
  click(1);assert.deepEqual(inputs.map(i=>i.value),['0','40','0']);
  assert.deepEqual(active(),[false,true,false]);
  assert.equal(buttons[1].classes.has('secondary'),false);
  edit(0,'0');assert.deepEqual(active(),[false,false,false]);
  assert.equal(buttons[1].classes.has('secondary'),true);
  edit(0,'10');edit(1,'20');edit(2,'10');
  assert.deepEqual(inputs.map(i=>i.value),['10','20','10']);
  click(1);assert.deepEqual(inputs.map(i=>i.value),['0','40','0']);
  cut.value='30';cut.fire('input');assert.deepEqual(active(),[false,false,false]);
  assert.deepEqual(buttons.map(b=>b.disabled),[true,false,false]);
  click(2);assert.deepEqual(inputs.map(i=>i.value),['0','0','30']);
  assert.deepEqual(active(),[false,false,true]);
  click(1);assert.deepEqual(inputs.map(i=>i.value),['0','30','0']);
  assert.deepEqual(active(),[false,true,false]);
  sold.value='100';sold.fire('input');assert.deepEqual(active(),[false,true,false]);
  cut.value='46';cut.fire('input');assert.deepEqual(active(),[false,false,false]);
  assert.deepEqual(buttons.map(b=>b.disabled),[true,true,true]);
  click(1);assert.deepEqual(inputs.map(i=>i.value),['0','30','0']);
  cut.value='30';cut.fire('input');assert.deepEqual(active(),[false,false,false]);
  cut.value='0,3';cut.fire('input');click(0);
  assert.deepEqual(inputs.map(i=>i.value),['0,3','0','0']);
  assert.deepEqual(active(),[true,false,false]);
  edit(0,'0,3');assert.deepEqual(active(),[false,false,false]);
  for(const value of ['','0','-1','inválido','1,0001']){
    cut.value=value;cut.fire('input');assert.ok(buttons.every(b=>b.disabled));
  }
  assert.equal(sold.value,'100');
}

cutMax();
cutSuggestions().then(()=>console.log('ux_controllers: 3 grupos de regresiones OK')).catch(error=>{console.error(error);process.exitCode=1;});
function aggregatedWithdrawal(){
 const sold=new Element(''),cut=new Element(''),review=new Element();
 const form=new Element();form.elements={quantidade_vendida:sold,quantidade_cortada:cut};
 const elements={'corte-seleccion':form,'corte-sugerir':null,'corte-lotes':new Element(),'corte-aviso':new Element()};
 vm.runInNewContext(script('corte.js'),{document:{getElementById:id=>elements[id]}});
 assert.equal(sold.value,'');assert.equal(cut.value,'');assert.equal(review.disabled,false);
 sold.value='5';sold.fire('input');assert.equal(cut.value,'');
}
function productUnits(){
 const unit=new Element('m'),standard=new Element('30'),width=new Element('1,40');
 const fields={'unidade':unit,'padrao':standard,'largura':width,'padrao-campo':new Element(),'largura-campo':new Element(),'precio-unidad':new Element()};
 const label=new Element();
 vm.runInNewContext(script('producto.js'),{document:{getElementById:id=>fields[id],querySelector:()=>label}});
 assert.equal(standard.disabled,false);assert.match(label.textContent,/rollo/);
 unit.value='un';unit.fire('change');assert.equal(standard.disabled,true);assert.equal(width.disabled,true);assert.equal(fields['padrao-campo'].hidden,true);
 assert.equal(fields['precio-unidad'].textContent,'un');
 unit.value='kg';unit.fire('change');assert.equal(standard.disabled,false);assert.equal(width.disabled,true);assert.match(label.textContent,/pieza/);
 assert.equal(standard.value,'30');
}
aggregatedWithdrawal();productUnits();
console.log('unidades: 2 grupos de regresiones JS OK');
