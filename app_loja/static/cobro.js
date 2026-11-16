// Importes en centavos enteros: sin redondeo ni envío de Vuelto.
(() => {
  const form = document.getElementById('cobro');
  if (!form) return;
  const input = document.getElementById('entregado');
  const error = document.getElementById('entregado-error');
  const status = document.getElementById('cobro-estado');
  const review = document.getElementById('cobro-revisar');
  const efectivo = document.getElementById('cobro-efectivo');
  const otro = document.getElementById('cobro-otro');
  const vuelto = document.getElementById('cobro-vuelto');
  const vueltoHelp = document.getElementById('vuelto-ayuda');
  const checkbox = form.elements.integral;
  const confirm = document.getElementById('confirmar-cobro');
  const base = form.elements.envio.value;
  const cents = value => {
    const [whole, fraction = ''] = value.split('.');
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  };
  const total = cents(form.dataset.total);
  const money = value => `${(value / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${(value % 100n).toString().padStart(2, '0')}`;
  const parse = value => {
    let text = value.trim();
    if (!text) throw new Error('Informá Efectivo entregado o elegí uno de los botones.');
    const message = 'Ingresá un importe válido, sin negativos y con hasta 2 decimales.';
    if (/^[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]{1,2})?$/.test(text)) text = text.replaceAll('.', '');
    else if (!/^[0-9]+(?:[.,][0-9]{1,2})?$/.test(text)) throw new Error(message);
    const amount = cents(text.replace(',', '.'));
    if (amount >= 100000000000000n) throw new Error(message);
    return amount;
  };
  let generation = 0, timer, ready = false, mustReview = false;
  const reset = () => {
    generation++;
    clearTimeout(timer);
    ready = false;
    form.elements.envio.value = '';
    checkbox.checked = false;
    confirm.disabled = true;
    efectivo.textContent = otro.textContent = vuelto.textContent = '—';
    vueltoHelp.hidden = true;
    error.hidden = true;
    input.removeAttribute('aria-invalid');
    if (!mustReview) status.textContent = '';
  };
  const showError = message => {
    error.textContent = message;
    error.hidden = false;
    input.setAttribute('aria-invalid', 'true');
  };
  const prepare = modo => {
    reset();
    if (mustReview) return;
    let delivered;
    try {
      delivered = modo === 'entregado' ? parse(input.value) : modo === 'efectivo' ? total : 0n;
    } catch (failure) {
      showError(failure.message);
      return;
    }
    const applied = delivered > total ? total : delivered;
    efectivo.textContent = money(applied);
    otro.textContent = money(total - applied);
    vuelto.textContent = money(delivered > total ? delivered - total : 0n);
    vueltoHelp.hidden = false;
    status.textContent = 'Revisando…';
    const current = generation;
    const data = new FormData();
    data.set('csrf', form.elements.csrf.value);
    data.set('envio', base);
    data.set('modo', modo);
    if (modo === 'entregado') data.set('entregado', input.value);
    timer = setTimeout(async () => {
      try {
        const response = await fetch(form.dataset.preparar, {method: 'POST', body: data, credentials: 'same-origin'});
        const composition = await response.json();
        if (current !== generation) return;
        if (!response.ok) {
          reset();
          if (composition.revisar) {
            mustReview = true;
            review.hidden = false;
            status.textContent = composition.error;
          } else showError(composition.error || 'No se pudo revisar la composición. Reintentá la revisión.');
          return;
        }
        if (cents(composition.total) !== total || cents(composition.efectivo) !== applied || cents(composition.otro) !== total - applied) {
          reset();
          mustReview = true;
          review.hidden = false;
          status.textContent = 'Volvé a revisar el ticket.';
          return;
        }
        form.elements.envio.value = composition.envio;
        ready = true;
        confirm.disabled = false;
        status.textContent = '';
      } catch (_) {
        if (current !== generation) return;
        reset();
        showError('No se pudo revisar la composición. Reintentá la revisión.');
      }
    }, 180);
  };
  input.addEventListener('input', () => prepare('entregado'));
  document.getElementById('todo-efectivo').addEventListener('click', () => {
    input.value = money(total);
    prepare('efectivo');
  });
  document.getElementById('todo-otro').addEventListener('click', () => {
    input.value = '0,00';
    prepare('otro');
  });
  form.addEventListener('submit', event => {
    if (!ready || mustReview) event.preventDefault();
  });
})();
