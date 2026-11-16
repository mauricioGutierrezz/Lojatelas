(() => {
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-foto]');
    if(!button)return;
    const dialog=document.getElementById('foto-dialog');
    dialog.querySelector('img').src=button.dataset.foto;
    dialog.querySelector('img').alt=button.getAttribute('aria-label');
    dialog.showModal();
  });
  document.querySelector('#foto-dialog button')?.addEventListener('click',()=>document.getElementById('foto-dialog').close());
  const container=document.querySelector('.foto-input');
  if(!container)return;
  const input=container.querySelector('input[type=file]');
  const preview=container.querySelector('.foto-preview');
  const status=container.querySelector('[role=status]');
  let url;
  const show=()=>{
    if(url)URL.revokeObjectURL(url);
    preview.hidden=!input.files.length;
    if(input.files.length){url=URL.createObjectURL(input.files[0]);preview.src=url;status.textContent='Foto seleccionada. Se guarda al confirmar el formulario.';}
  };
  input.addEventListener('change',show);
  container.querySelector('[contenteditable]').addEventListener('paste',event=>{
    event.preventDefault();
    const item=[...(event.clipboardData?.items||[])].find(item=>item.kind==='file'&&item.type.startsWith('image/'));
    const file=item?.getAsFile();
    if(!file){status.textContent='No hay una imagen para pegar. Podés seleccionar un archivo.';return;}
    const transfer=new DataTransfer();
    transfer.items.add(file);
    input.files=transfer.files;
    show();
  });
})();
