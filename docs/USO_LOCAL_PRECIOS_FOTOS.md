# Precios y foto principal — uso local

> **Actualización 15/11/2026 — roles en lugar de PIN.** El PIN general ya no existe. Se entra eligiendo el rol (Administrador, Empleado o Cajero) y su contraseña; cada rol ve solo sus secciones. Precios es del Administrador; Cierre y Fondo inicial, del Cajero y del Administrador. Lo que esta guía diga sobre PIN, sesión compartida o `setup_pin` quedó sin efecto. Ver [INSTALACAO_WINDOWS](INSTALACAO_WINDOWS.md).

La sesión operativa sigue compartida. El PIN general controla acceso; no identifica a una persona. Los responsables existentes se conservan como información registrada.

## Instalación de la extensión

Instalar las dependencias de `app_loja/requirements.txt` en el entorno virtual local; incluye Pillow para validar y procesar fotos. La operación cotidiana no necesita internet.

La revisión m/un/kg se instala únicamente en una base nueva y vacía con el procedimiento de `USO_LOCAL_1A.md`. El inicializador incluye precios y fotos atomicamente. `migrations/001_precios_fotos.sql` se conserva como histórico de la extensión anterior: no convierte una base poblada a los contratos actuales. No aplicar el nuevo schema a una base existente ni limpiar datos para reinstalar.

El mismo PIN externo ya configurado protege Precios. El procedimiento inicial sigue siendo `.venv/bin/python -m app_loja.setup_pin`; nunca guardar el valor real en el repositorio. No crear otro PIN para Precios.

## Precios

1. Abrir **Precios** e ingresar el PIN general.
2. Buscar productos y editar sus precios en la lista. El filtro conserva las entradas pendientes; las filas modificadas indican **Cambio pendiente**. Editar no guarda.
3. Elegir **Revisar cambios**. La revisión muestra solamente los productos modificados, precio anterior y precio nuevo por m/un/kg.
4. **Seguir editando** conserva las entradas del lote. **Confirmar cambios** aplica todas juntas y registra su historial.

Los precios aceptan cero y hasta dos decimales, con separadores es-AR o decimales sin agrupación. Si los valores revisados dejan de estar vigentes, no se guarda ninguna parte del lote: volver a Precios para revisar los datos actuales. No hay fusión ni sobrescrita silenciosa.

Una confirmación repetida del mismo lote no duplica el historial. Ante un fallo técnico con resultado incierto, reintentar el mismo lote permite recuperar su resultado sin volver a aplicarlo. El banco conserva producto, precio anterior/nuevo, horario y responsable informado. Los precios congelados de tickets existentes no cambian.

Salir hacia la operación normal termina la autorización. Volver exige PIN. Cambiar al flujo protegido de Cierre también requiere iniciar su propio acceso con el mismo PIN. Las etapas internas y las imágenes no piden nuevamente el PIN. Se mantiene el mecanismo local de un proceso, sin timeout ni sesión administrativa.

## Foto principal

En **Nuevo producto**, seleccionar una foto opcional antes de crear el producto. Para un producto existente, abrir su ficha desde **Productos y stock**, seleccionar o pegar una imagen y elegir **Guardar foto**.

La zona **Pegar imagen** recibe una imagen con Ctrl+V o la acción de pegar del dispositivo. No lee el clipboard automáticamente. Si contiene solamente texto o un enlace, se informa que no hay imagen: usar selección de archivo como alternativa. No descarga imágenes de URLs ni integra WhatsApp.

Cada producto conserva como máximo una foto principal. Seleccionar/pegar prepara la foto; confirmar el formulario la guarda. Una foto inválida o una escritura fallida conserva la foto válida anterior. Crear producto con foto sucede en una única transacción.

Las miniaturas aparecen en stock, selección de productos para corte, ingreso, ticket, Caja y Precios. Tocar/clicar la miniatura abre la imagen mayor; **Cerrar** o Escape vuelve a la pantalla. Un producto sin foto funciona normalmente.

## Almacenamiento y límites técnicos

Las imágenes normalizadas y sus miniaturas se almacenan como bytes en `fotos_produto` dentro del PostgreSQL local; no hay archivos de medios en Git ni rutas tomadas del nombre subido. El respaldo de la base incluye estas fotos. Una sustitución reemplaza la única fila en una transacción; no produce archivos huérfanos ni mantiene un historial de fotos.

- Entrada: JPEG, PNG o WebP estático, hasta 5 MiB.
- Dimensiones: hasta 4096 píxeles por lado y 12 millones de píxeles en total.
- Validación por contenido, lectura y decodificación del servidor; no se confía en extensión ni MIME declarado.
- Re-encode JPEG/PNG, conservando proporción y transparencia cuando existe; sin EXIF, GPS, comentarios o perfiles heredados.
- Imagen normalizada: hasta 8 MiB. Miniatura: dentro de 240 × 240 píxeles, sin distorsión.
- Imágenes accesibles solamente en la sesión operativa; tipo de contenido normalizado y `nosniff`.

No incluye galería, cámara, crop, edición, eliminación de fotos ni gestión de permisos individuales. Una foto ayuda a identificar el producto; no garantiza fidelidad de color.

## Verificación

`bash tests/run_phase0_postgres.sh` ejecuta SQL, concurrencia y la suite Python sobre PostgreSQL descartable, incluyendo regresiones y la migración aditiva. No usa la base operacional. Los tests y la demostración de navegador usan imágenes y PIN ficticios.
