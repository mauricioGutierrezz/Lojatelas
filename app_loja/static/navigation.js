// Una página restaurada desde la caché debe volver a consultar la autorización.
window.addEventListener('pageshow',event=>{
  if(event.persisted) window.location.reload();
});
