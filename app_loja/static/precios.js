(() => {
  const rows=[...document.querySelectorAll('[data-price-row]')];
  const cents=value=>{
    let text=value.trim();
    if (/^\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?$/.test(text)) text=text.replaceAll('.','');
    if (!/^\d+(?:[.,]\d{1,2})?$/.test(text)) return null;
    const [whole,fraction='']=text.replace(',','.').split('.');
    return BigInt(whole)*100n+BigInt(fraction.padEnd(2,'0'));
  };
  const update=()=>{
    let count=0;
    for(const row of rows){
      const changed=cents(row.querySelector('input').value)!==cents(row.dataset.original);
      row.classList.toggle('precio-pendiente',changed);
      row.querySelector('[data-pending]').textContent=changed?'Cambio pendiente':'';
      if(changed)count++;
    }
    document.getElementById('precios-pendientes').textContent=count?`${count} cambio(s) pendiente(s)`:'';
  };
  for(const row of rows)row.querySelector('input').addEventListener('input',update);
  const normalize=v=>v.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const searchInput=document.getElementById('precio-buscar');
  const categories=[...document.querySelectorAll('button[data-category]')];
  let category='';
  const filter=()=>{
    const search=normalize(searchInput.value);
    for(const row of rows)row.hidden=!(normalize(row.dataset.name).includes(search)
      && (!category || row.dataset.category===category));
    for(const button of categories){
      const selected=button.dataset.category===category;
      button.setAttribute('aria-pressed',String(selected));
      button.classList.toggle('secondary',!selected);
    }
  };
  searchInput.addEventListener('input',filter);
  for(const button of categories)button.addEventListener('click',()=>{
    category=button.dataset.category;
    filter();
  });
  filter();
  update();
})();
