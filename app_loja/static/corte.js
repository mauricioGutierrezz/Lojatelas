(() => {
  const form=document.getElementById('corte-seleccion');
  const button=document.getElementById('corte-sugerir');
  const area=document.getElementById('corte-lotes');
  const notice=document.getElementById('corte-aviso');
  if(!button)return; // Unidades: revisión directa, sin orígenes físicos ni sugerencia.
  const quantities=[form.elements.quantidade_vendida,form.elements.quantidade_cortada];
  let revision=0;
  let request=null;
  let maxApplied=null;
  // Milésimas enteras: la ayuda conserva la precisión NUMERIC(12,3).
  const units=value=>{
    const text=value.trim();
    if(!/^\d+(?:[.,]\d{1,3})?$/.test(text))return null;
    const [whole,fraction='']=text.replace(',','.').split('.');
    return BigInt(whole)*1000n+BigInt(fraction.padEnd(3,'0'));
  };
  const quantityText=value=>{
    const fraction=(value%1000n).toString().padStart(3,'0').replace(/0+$/,'');
    return (value/1000n).toString()+(fraction?','+fraction:'');
  };
  const maximum=button=>{
    const total=units(form.elements.quantidade_cortada.value);
    const balance=units(button.dataset.balance);
    if(total===null || total<=0n || balance===null || balance<total)return null;
    return total;
  };
  const updateMax=()=>{
    const inputs=[...area.querySelectorAll('input[name="retirar"]')];
    for(const button of area.querySelectorAll('[data-max-for]')){
      const value=maximum(button);
      const input=inputs.find(input=>input.id===button.dataset.maxFor);
      const active=value!==null && maxApplied===input?.id && units(input.value)===value &&
        inputs.every(other=>other===input || units(other.value)===0n);
      if(maxApplied===input?.id && !active)maxApplied=null;
      button.disabled=value===null;
      button.classList.toggle('secondary',!active);
      button.setAttribute('aria-pressed',String(active));
    }
  };
  area.addEventListener('input',event=>{
    if(event.target.name!=='retirar')return;
    maxApplied=null;
    updateMax();
  });
  area.addEventListener('click',event=>{
    const button=event.target.closest('[data-max-for]');
    if(!button)return;
    const inputs=[...area.querySelectorAll('input[name="retirar"]')];
    const value=maximum(button);
    if(value===null)return;
    const input=inputs.find(input=>input.id===button.dataset.maxFor);
    for(const other of inputs)other.value=other===input?quantityText(value):'0';
    maxApplied=input.id;
    updateMax();
  });
  const message=text=>{notice.textContent=text;notice.hidden=!text;};
  const invalidate=()=>{
    revision++;
    request?.abort();
    area.querySelectorAll('[data-suggested]').forEach(marker=>marker.remove());
    const review=area.querySelector('#corte-revisar');
    if(review)review.disabled=true;
    message('Las cantidades cambiaron. Actualizá la sugerencia antes de revisar.');
    updateMax();
  };
  quantities.forEach(input=>input.addEventListener('input',invalidate));
  button.addEventListener('click',async event=>{
    event.preventDefault();
    request?.abort();
    request=new AbortController();
    const controller=request;
    const version=++revision;
    const url=new URL(form.dataset.suggestionUrl,location.origin);
    for(const name of ['quantidade_vendida','quantidade_cortada','q','categoria'])
      url.searchParams.set(name,form.elements[name].value);
    url.searchParams.set('parcial','si');
    for(const input of area.querySelectorAll('input[name="retirar"]')){
      url.searchParams.append('lote_id',input.id.slice('lote-'.length));
      url.searchParams.append('retirar',input.value);
    }
    message('Actualizando sugerencia…');
    try{
      const response=await fetch(url,{signal:controller.signal});
      if(response.redirected || ![200,400].includes(response.status))throw new Error();
      const html=await response.text();
      if(version!==revision)return;
      // Solo reemplaza el fragmento del servidor; no cambia cantidades ni preparación.
      if(response.ok){
        const saved=new Map([...area.querySelectorAll('input[name="retirar"]')]
          .map(input=>[input.id,input.value]));
        area.innerHTML=html;
        for(const input of area.querySelectorAll('input[name="retirar"]'))
          if(saved.has(input.id))input.value=saved.get(input.id);
        message('');
        updateMax();
      }else{
        const fragment=new DOMParser().parseFromString(html,'text/html');
        message(fragment.querySelector('[role="alert"]')?.textContent || 'Revisá las cantidades.');
        const review=area.querySelector('#corte-revisar');
        if(review)review.disabled=true;
        area.querySelectorAll('[data-suggested]').forEach(marker=>marker.remove());
      }
    }catch(error){
      if(error.name!=='AbortError' && version===revision)
        message('No se pudo actualizar la sugerencia. Volvé a intentar.');
    }
  });
  updateMax();
})();
