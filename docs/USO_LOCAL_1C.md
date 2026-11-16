# Caja / Venta — ejecución local

> **Actualización 15/11/2026 — roles en lugar de PIN.** El PIN general ya no existe. Se entra eligiendo el rol (Administrador, Empleado o Cajero) y su contraseña; cada rol ve solo sus secciones. Precios es del Administrador; Cierre y Fondo inicial, del Cajero y del Administrador. Lo que esta guía diga sobre PIN, sesión compartida o `setup_pin` quedó sin efecto. Ver [INSTALACAO_WINDOWS](INSTALACAO_WINDOWS.md).

Usa el entorno Python, PostgreSQL UTF-8, login y conexión restringida descritos
en `USO_LOCAL_1A.md`. La operación no requiere internet ni servicios externos.
La decisión vigente permite sesión compartida sin login/logout individual por atención.
El usuario mostrado no prueba autoria individual; esta no es requisito de la operación normal.

`schema.sql` inicializa una base nueva; no migra una base existente. No borrar
ni reinicializar datos reales para aplicar esta entrega.

## Configuración inicial del PIN general

Desde la raíz del repositorio, con el mismo usuario del sistema que ejecutará
la aplicación:

```bash
.venv/bin/python -m app_loja.setup_pin
```

El comando pide el PIN dos veces sin mostrarlo. Guarda únicamente un hash scrypt
con sal aleatoria, en `$XDG_CONFIG_HOME/urdimbre/cierre-pin.hash` o,
si esa variable no está definida, en `$HOME/.config/urdimbre/cierre-pin.hash`.
El archivo queda con permisos 0600. No escribir el PIN en comandos, variables de
entorno, guías o archivos del proyecto. No existe un PIN predeterminado.

Para usar otro destino externo al repositorio, configurar `CIERRE_PIN_FILE` con
la ruta del archivo antes de ejecutar el comando y antes de iniciar la aplicación:

```bash
export CIERRE_PIN_FILE="$HOME/.config/urdimbre/cierre-pin.hash"
.venv/bin/python -m app_loja.setup_pin
.venv/bin/python -m app_loja.run
```

El comando es solo de configuración inicial: rechaza destinos dentro del
repositorio y no reemplaza archivos existentes. Si falta el archivo, es inválido
o tiene permisos inseguros, el acceso protegido no se libera; la operación normal
continúa. No hay gestión, recuperación o cambio de PIN por interfaz.

## Acceso al flujo protegido

La sesión operativa compartida sigue abierta para Productos / Stock, Corte /
Ticket, Caja / Venta y Consulta de Caja. No se pide PIN por atención.
Al entrar en Cierre, incluyendo sus registros, o al corregir Fondo inicial,
ingresar el PIN general. Un acceso directo por URL o POST requiere la misma
autorización; un POST bloqueado no se ejecuta ni se reenvía automáticamente
después de ingresar el PIN. Volver a preparar y confirmar la acción.

El servidor mantiene la autorización solo para ese flujo, sin timeout:
actualizar la página, guardar el fondo, revisar, confirmar y consultar el Cierre
en ese flujo no vuelve a pedir PIN. Ir a la operación normal, incluida Consulta
de Caja, termina la autorización. Al regresar se pide PIN nuevamente; los
formularios del flujo anterior ya no autorizan operaciones.

La aplicación local usa un solo proceso servidor. Las autorizaciones se mantienen
en memoria del servidor y se pierden al reiniciarlo; volver a ingresar el PIN.
No ejecutar múltiples procesos independientes con este registro en memoria.
El PIN controla acceso, no identifica a una persona. Los responsables y horarios
existentes se conservan sin constituir prueba fuerte de autoría individual.

## Operación

1. Entrar a **Caja / Venta** y buscar el código de Corte / Ticket. También se
   puede acceder desde **Ir a Caja / Venta** en el ticket.
2. Revisar todos los items, cantidades vendidas, precios congelados, subtotales
   y total. La cantidad cortada y su diferencia se muestran como trazabilidad
   física, sin cambiar la cantidad cobrada ni clasificar esa diferencia.
3. Informar **Efectivo entregado**, o elegir **Todo en efectivo** / **Todo en Otro**.
   En la misma pantalla se muestran Total, Efectivo y Otro. Si el dinero entregado
   supera el total, Efectivo queda limitado al total y **Vuelto a entregar** ayuda
   a devolver el excedente. El campo vacío no es una elección; los botones no
   confirman la venta. Un error de importe permanece junto al campo para corregirlo.
4. Después de recibir el importe completo, marcar **Cobro completo recibido** y
   **Confirmar cobro**, sin pasar por otra página de composición. Cambiar la
   entrada o usar otro botón exige volver a marcar la confirmación.
5. Consultar **Venta concluida**, con total, Efectivo, Otro, responsable informado y
   fecha/hora. El mismo código permite recuperar la venta en otra sesión.

Se admite todo Efectivo, todo Otro o combinación de ambos, siempre integral.
Efectivo es la parcela de la venta pagada en dinero. Efectivo entregado y Vuelto
son transitorios: no se guardan con la venta ni cambian Caja o Cierre. No hay pago
parcial, descuentos, detalle de Otro ni cancelación.

## Integridad

La conferencia se lee en una sola instantánea del banco. La confirmación lleva
los items conferidos en un formulario firmado y vinculado a la sesión.
El banco bloquea el ticket, compara todos los items con la conferencia, calcula
el total y registra una única venta junto con el estado pagado. Una modificación
del ticket exige revisar nuevamente, incluso si el total no cambia.

Repetir una confirmación idéntica, con el mismo Efectivo, recupera la misma venta; no vuelve a recibir
ni registra otra venta. Si se pierde la respuesta, consultar la venta o
**Reintentar el mismo registro**, sin volver a recibir el importe.
La primera persona que confirma permanece como responsable registrado.

La recepción no modifica lotes, asignaciones ni movimientos de CORTE. Conserva
los horarios originales del ticket y los cortes, y añade el de la venta.
Efectivo se persiste como parcela de la venta y Otro como columna calculada.
El campo técnico existente de modalidad queda nulo. Las modalidades futuras
dentro de Otro pueden vincularse a la venta. La preparación valida el dinero
entregado y el total del banco; la confirmación firmada lleva solamente la
parcela Efectivo aplicada y la conferencia. Vuelto se calcula solo en la pantalla
y no se envía al servidor.

## Consulta de Caja, Fondo inicial y Cierre del día

Desde **Caja / Venta**, abrir **Consulta de Caja** para ver la fecha operativa
actual de Córdoba y los valores calculados: Total vendido, Efectivo recibido
por ventas, Otro, Fondo inicial y Efectivo según fondo y ventas. La consulta
no crea Cierre, no reserva el día y no bloquea ventas; puede actualizarse incluso
cuando el día ya está cerrado. **Cierres registrados** permite consultar cada
registro conservado por su fecha.

En **Cierre del día**, informar o corregir el Fondo inicial de referencia de esa
fecha. Cada guardado preserva valor, persona informada y horario. No se transporta
el fondo anterior: **Sin informar** es distinto de fondo cero. Vender no requiere
fondo; confirmar el Cierre sí lo requiere. Corregir el fondo después de cerrar
no cambia el valor que quedó registrado en ese Cierre.

Revisar los valores y, opcionalmente, informar **Efectivo contado**, incluyendo
el fondo y todo el dinero físicamente presente en la gaveta. Dejarlo vacío
significa que no se contó; cero es un conteo informado de cero. **Revisar
Cierre** muestra Diferencia = contado − (fondo + efectivo de ventas), solamente
cuando hubo conteo. Se admite cualquier diferencia numérica sin justificación
textual ni clasificación automática.

**Confirmar Cierre del día** es definitivo: produce un único registro por fecha
y bloquea nuevos recibimientos de esa fecha. Preparar el Cierre no bloquea ventas.
Si cambia el movimiento o se corrige el fondo desde la revisión, actualizar y
revisar nuevamente el conteo; no se reutiliza silenciosamente un conteo anterior.
Un reenvío idéntico recupera el mismo Cierre, conservando responsable y horario.
No existe reapertura ni segundo Cierre para la fecha.

Tickets pendientes pueden atravesar días. Una venta corresponde al día de su
recibimiento en Córdoba, no a la fecha del ticket o corte. Un Cierre no altera
stocks, cortes, tickets ni valores de ventas. No se registran movimientos
extraordinarios ni se interpreta la diferencia como falta, sobra, pérdida o error.

## Verificación

```bash
bash tests/run_phase0_postgres.sh
git diff --check
```

La suite usa un cluster propio descartable e incluye regresiones de Fase 0,
Ingreso / Stock y Corte / Ticket, más `tests/test_caja_venta.py`: cantidades
distintas, precio congelado, dinero entregado y botones sin recepción automática,
composición aplicada sin persistir dinero entregado ni vuelto, reenvío, permisos, timestamps, fallos posteriores a
escrituras, pérdida de respuesta y carreras entre corte y recepción y entre dos
recepciones. `tests/test_cierre.py` verifica consulta sin efectos, fondo con historial,
conteo opcional, diferencias, snapshots desactualizados, unicidad, permisos,
reenvío y carreras entre recibimiento, fondo y Cierre. Usa bases descartables
independientes para no cerrar la fecha de las demás regresiones.
Las pruebas de PIN usan valores ficticios generados para cada prueba y archivos
temporales externos: acceso directo, PIN incorrecto, continuidad, salida,
repetición de cookies/formularios, CSRF y corrección del fondo. `tests/test_pin.py`
verifica hash, permisos, configuración interactiva y rechazo de archivos inseguros.
`tests/test_cobro.py` verifica los formatos monetarios es-AR y la precisión sin
redondeo silencioso. La interacción inmediata y los errores corregibles se
verifican también en el navegador con datos ficticios.

## Acceso aprobado y estado de implementación

Productos / Stock, Corte / Ticket, Caja / Venta y Consulta de Caja permanecen
accesibles en la sesión operativa normal. Acceder a Cierre del día y corregir
Fondo inicial requiere el mismo PIN general compartido. El PIN autoriza acceso,
no identifica a una persona. Precios usa también ese mismo PIN. Ver [Precios y fotos](USO_LOCAL_PRECIOS_FOTOS.md) para instalación y uso de la extensión.
No se crean usuarios individuales, PIN individuales, permisos granulares ni sesión administrativa.
La autorización dura únicamente mientras se permanece en el flujo protegido.
Pasar entre sus etapas no requiere repetir el PIN. Salir termina la autorización;
volver a ingresar requiere el PIN nuevamente.

El PIN real se configura localmente fuera del repositorio. Su valor no se incluye
en documentos versionados ni código fuente. Se verifica en el servidor y no se
almacena como texto plano. La gestión y el cambio amigable del PIN quedan para
Administración futura, que podrá reemplazar este mecanismo.

La protección está implementada y las verificaciones locales usan exclusivamente
PIN ficticio. La instalación debe configurar su PIN mediante el procedimiento
anterior. Las instrucciones de login describen el acceso existente, no una
obligación de cambiar de usuario por cada atención. Se conservan los campos de
responsables sin atribuirles autoría individual comprobada.

La extensión implementada de precios y fotos se describe en [Precios y fotos](USO_LOCAL_PRECIOS_FOTOS.md). Usa el mismo PIN general y conserva los precios congelados de los tickets.

## Ticket con unidades mixtas

Cada item conserva m/un/kg, ambas cantidades y precio congelado por su unidad. En Caja se muestra cantidad cortada (m), retirada de unidades (un) o peso retirado (kg). Total, Efectivo y Otro siguen calculados por el banco; el pago no cambia saldos físicos ni agregados. Consulta, Fondo inicial, PIN y Cierre conservan sus reglas.
