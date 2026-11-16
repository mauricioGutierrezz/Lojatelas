# Corte / Ticket — ejecución local

> **Actualización 15/11/2026 — roles en lugar de PIN.** El PIN general ya no existe. Se entra eligiendo el rol (Administrador, Empleado o Cajero) y su contraseña; cada rol ve solo sus secciones. Precios es del Administrador; Cierre y Fondo inicial, del Cajero y del Administrador. Lo que esta guía diga sobre PIN, sesión compartida o `setup_pin` quedó sin efecto. Ver [INSTALACAO_WINDOWS](INSTALACAO_WINDOWS.md).

Usa el mismo entorno Python, PostgreSQL UTF-8, conexión restringida y login local
descritos en `USO_LOCAL_1A.md`. No requiere internet durante la operación.
La decisión vigente permite sesión compartida sin login/logout individual por atención.
Los responsables informados se conservan; no prueban autoria individual ni se exige
esa garantía para la operación normal.

`schema.sql` inicializa una base nueva. Esta adaptación incorpora claves de
repetición para tickets y cortes, responsable por item y vínculo del movimiento
con ese item. No es una migración de bases existentes. No borrar ni reinicializar
una base con datos reales para probar esta entrega. Los tests utilizan un cluster
propio descartable; las bases operativas no son tocadas.

## Operación

1. Abrir **Corte / Ticket**, crear **Nuevo ticket** o continuar uno pendiente. Elegir **Agregar producto**, buscar y seleccionar el producto.
2. Informar independientemente cantidad vendida y cantidad retirada: **Cantidad cortada** para m, **Peso retirado** para kg, **Cantidad retirada** entera para un. No se copia una cantidad a la otra.
3. **m / kg**: seleccionar rollos / piezas. La sugerencia conserva prioridad de abiertos y menor saldo suficiente. **MAX** coloca toda la cantidad retirada en una única origen capaz y pone las demás en cero; no reparte automáticamente. Se permite distribución manual entre orígenes.
4. **un**: retirada directa del stock disponible, sin selección de origen, distribución ni MAX. Ingresos +30 y +20, retirada −7: saldo 43, sin FIFO/LIFO.
5. Revisar cantidades, precio/subtotal y saldo previsto. Para físicos se muestra cada origen; para unidades, el agregado. La preparación no reserva ni descuenta stock. Volver preserva cantidades, distribución, búsqueda y clave.
6. Después de la confirmación presencial del cliente y retirada física, marcar **Corte realizado** y **Registrar corte** (m), o **Retirada realizada** y **Registrar retirada** (un/kg).
7. Se vuelve a selección para agregar otro producto al mismo ticket. El resumen/ticket/Caja muestran unidad y cantidades por item; nunca suman unidades de mercadería distintas. Cantidades distintas no se clasifican automáticamente como pérdida o ajuste.

## Integridad y reintentos

Cada confirmación lleva una clave UUID, independiente del ticket. Reenviar la
misma confirmación devuelve el mismo item; cambiar datos con la misma clave se
rechaza. La creación de tickets también admite repetición sin crear otro ticket.
El banco bloquea el ticket, productos y saldos físicos/agregados en orden estable, revalida saldos y registra
item, asignaciones, baja y movimientos en una transacción.

Si no se puede confirmar el registro, la pantalla mantiene la identificación para
**Reintentar el mismo registro** y permite consultar el ticket. Si el
material ya fue cortado, no volver a cortarlo ni preparar otro envío para repetir
la misma retirada. No se ofrece corrección automática de saldos o tratamiento
de divergencia cuando el stock no permite registrar la solicitud.

Salir de la pantalla no deshace retiradas registradas. No hay cancelación,
retalho, impresión, pago o área administrativa en esta entrega.

## Verificación

```bash
bash tests/run_phase0_postgres.sh
git diff --check
```

El runner aplica el schema y ejecuta las pruebas anteriores de Fase 0 y 1A junto
con `tests/test_corte_ticket.py`. Incluye repetición HTTP, continuidad entre
atendentes, cortes de varios lotes, precio congelado, precisión decimal,
permisos, entradas inválidas, fallo posterior a escrituras y carreras entre
conexiones PostgreSQL con espera de locks observada. Las pruebas anteriores de
pago/cierre se mantienen como regresión del núcleo, sin implementar Caja / Venta.

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

La protección se valida en el servidor, también en URLs y POSTs directos.
Las instrucciones de login describen el acceso existente, no una obligación de
cambiar de usuario por cada atención. Conservar los campos de responsables y
validar las protecciones aprobadas antes de declarar el uso real habilitado.

La operación se serializa por clave → ticket → productos ordenados → saldo agregado/orígenes ordenados. El pago no vuelve a retirar stock. Las unidades requieren enteros en HTTP y banco; m/kg admiten hasta tres decimales, sin redondear entradas inválidas. El historial conserva documentos y movimientos físicos o del producto agregado; no inventa origen de unidades.
