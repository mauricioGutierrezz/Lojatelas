(() => {
 const unit=document.getElementById('unidade');
 const standard=document.getElementById('padrao'),width=document.getElementById('largura');
 const update=()=>{
  const aggregated=unit.value==='un';
  document.getElementById('precio-unidad').textContent=unit.value;
  document.getElementById('padrao-campo').hidden=aggregated;
  standard.disabled=aggregated;
  document.querySelector('label[for="padrao"]').textContent=unit.value==='kg'?'Peso sugerido por pieza (kg, opcional)':'Metros sugeridos por rollo (opcional)';
  document.getElementById('largura-campo').hidden=unit.value!=='m';
  width.disabled=unit.value!=='m';
 };
 unit.addEventListener('change',update);update();
})();
