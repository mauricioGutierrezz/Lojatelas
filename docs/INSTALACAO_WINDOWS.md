# Primera instalación en Windows — Urdimbre

Este procedimiento crea una base **nueva** en el equipo de destino. No copia los
datos de otro equipo y nunca borra ni reinstala una base existente. No ejecutar
el bootstrap si la tienda ya fue instalada.

## Camino rápido (recomendado)

1. Instalar Python 3.13 (marcando "Add python.exe to PATH") y PostgreSQL 16
   (`instalar_postgresql.bat`). Guardar la contraseña elegida para `postgres`.
2. Doble clic en **`instalar.bat`**. El asistente hace solo lo que falte:
   entorno de Python, base nueva con sus tres roles, respaldo automático,
   acceso directo "Urdimbre" en el Escritorio y, si hay varios equipos,
   el modo servidor. Se puede repetir sin
   riesgo: nunca borra una base ni reemplaza una contraseña existente.
3. Para abrir la tienda cada día: doble clic en el acceso directo del
   Escritorio (o `iniciar.bat`). No pide la contraseña de conexión.
4. En la pantalla de ingreso, elegir el **rol** y escribir su contraseña.

| Archivo | Para qué sirve |
| --- | --- |
| `instalar.bat` | Instalar o completar la instalación en este equipo. |
| `iniciar.bat` | Abrir la tienda. Si ya está abierta, solo abre el navegador. |
| `cambiar_contrasena.bat` | Cambiar la contraseña de un rol. |
| `permitir_red.bat` | Permitir que los otros equipos de la tienda se conecten a este. |
| `quitar_red.bat` | Deshacer `permitir_red.bat`. |
| `respaldar.bat` | Crear ahora una copia de seguridad. |
| `restaurar_respaldo.bat` | Restaurar el respaldo más reciente en una base **nueva**. |
| `ejecutar_pruebas.bat` | Ejecutar todas las pruebas en un PostgreSQL temporal. |

### Roles

| Rol | Ve |
| --- | --- |
| Administrador | Todo: Productos y stock, Corte / Ticket, Caja / Venta, Cierre, Fondo inicial y Precios. |
| Empleado | Productos y stock; Corte / Ticket. |
| Cajero | Corte / Ticket; Caja / Venta; Consulta de Caja; Cierre del día y Fondo inicial. |

Son tres cuentas fijas, una por rol, cada una con su contraseña. Las cuentas son
compartidas por quienes cumplen ese rol: el rol autoriza, no identifica a la
persona. El PIN general ya no existe. Una sección que el rol no puede usar no
aparece en el menú y responde "Tu rol no tiene acceso a esta sección" si se
abre por dirección directa.

`cambiar_contrasena.bat` cambia la contraseña de un rol; pide la contraseña de
`postgres`. Las sesiones ya abiertas siguen activas hasta usar **Salir**.

Después de 5 contraseñas incorrectas seguidas para un mismo rol hay que esperar
30 segundos; la espera se duplica con cada nuevo error, hasta 5 minutos. Los
otros roles no quedan bloqueados.

### Varios equipos

Un solo equipo es el **servidor**: tiene PostgreSQL, la tienda, los respaldos y
debe estar encendido mientras la tienda trabaja. En los otros equipos **no se
instala nada**: usan el navegador.

En el servidor, una sola vez:

1. Ejecutar `instalar.bat` y responder **S** en "Varios equipos".
2. Aceptar abrir el puerto (o ejecutar `permitir_red.bat`). Windows pide permiso
   de administrador. Solo abre el puerto 5000 para la red privada local; no
   abre nada hacia internet ni expone la base de datos.
3. Opcional: aceptar que la tienda se abra sola al iniciar sesión en Windows.

El asistente muestra la dirección para los otros equipos, por ejemplo
`http://NOMBRE-DEL-EQUIPO:5000`, y deja en el Escritorio el archivo
"Urdimbre - otros equipos": copiarlo a los otros equipos y abrirlo con
doble clic. La misma dirección aparece cada vez que se abre la tienda.

Si un equipo no conecta:

- La tienda debe estar abierta en el servidor.
- La red del servidor debe figurar como **Privada** en Configuración → Red e
  Internet; con red "Pública" la regla del firewall no se aplica.
- Probar con la dirección numérica (`http://192.168.x.x:5000`) que muestra la
  ventana de la tienda. Si funciona solo así, reservar esa dirección para el
  servidor en el router.

- Mientras la tienda está abierta en modo servidor, este equipo no se suspende
  por inactividad. Si se cierra la tapa o se apaga, los otros equipos pierden
  la conexión.
- El archivo `%LOCALAPPDATA%\Urdimbre\accesos.log` registra cada conexión
  (dirección, página y resultado, sin contraseñas). Si el otro equipo no
  aparece allí, el pedido no llegó: revisar red y firewall. Si aparece con
  `403-fuera-de-red`, ese equipo no está en la red local de la tienda.

Seguridad: la tienda rechaza cualquier conexión que no venga de este equipo o
de una red privada. Dentro de la red local la conexión **no va cifrada**: usar
el modo servidor solo en una red cableada o un Wi-Fi exclusivo de la tienda,
con contraseña. No usarlo en un Wi-Fi compartido con clientes.

`iniciar.bat --local` abre la tienda solo para este equipo aunque esté
configurado como servidor. `quitar_red.bat` cierra el puerto.

### Qué pide `instalar.bat` en una instalación nueva

1. **Contraseña de postgres:** la elegida al instalar PostgreSQL.
2. **Nombre de base para confirmar:** escribir `urdimbre` exactamente.
3. **Nueva contraseña de conexión de la aplicación:** elegir y repetir. Es
   técnica (role PostgreSQL `loja_app`); queda protegida por Windows y no se
   vuelve a pedir.
4. **Contraseña de cada rol:** Administrador, Empleado y Cajero; elegir y
   repetir cada una.

Las categorías se crean solas: Accesorios, Telas por peso, Telas de punto y
Telas sintéticas. Las contraseñas se escriben sin eco y no se guardan en el
proyecto.

### Equipo con la versión anterior (sin roles)

Si la base existente es de la versión anterior, `instalar.bat` lo detecta y
pide escribir `archivar`. La base anterior **no se borra**: se renombra a
`urdimbre_anterior_FECHA` y se crea una base nueva y vacía con los tres
roles. La tienda debe estar cerrada. La contraseña de conexión no cambia.

### Contraseña de conexión

La contraseña de conexión de la aplicación se pide una sola vez y queda cifrada
por Windows para la cuenta que usa la tienda, en `%LOCALAPPDATA%\Urdimbre`,
fuera del proyecto. Quien use esa misma cuenta Windows abre la tienda sin
escribirla; la contraseña del rol se sigue pidiendo.

- `iniciar.bat --no-recordar`: pedirla siempre y no guardarla.
- `iniciar.bat --olvidar`: borrar la contraseña guardada.

### Respaldos

Cada día, al abrir la tienda, se guarda un respaldo en
`Documentos\Urdimbre - Respaldos` (se conservan los últimos 30). Si falla,
la tienda abre igual y muestra un aviso. `respaldar.bat` crea uno en el momento.
Copiar esa carpeta también a un pendrive o a la nube: un respaldo que vive solo
en el mismo equipo no protege contra la pérdida del equipo. El archivo contiene
los datos de la tienda; tratarlo como confidencial.

`restaurar_respaldo.bat` crea una base nueva con el respaldo más reciente y
muestra cómo abrir la tienda con ella (`iniciar.bat --database NOMBRE`). Nunca
modifica ni borra la base actual.

### Dónde guardar la carpeta del proyecto

Usar una carpeta local, por ejemplo `C:\Urdimbre`. No instalar la tienda
dentro de OneDrive, Google Drive o Dropbox: la sincronización puede dañar el
entorno de Python y el repositorio.

### Pasos manuales equivalentes

Solo para diagnóstico. Cada comando se ejecuta en PowerShell desde la raíz del
proyecto, donde están `schema.sql` y la carpeta `app_loja`.

```powershell
python -m venv .venv-windows
.\.venv-windows\Scripts\python.exe -m pip install -r .\app_loja\requirements.txt
.\.venv-windows\Scripts\python.exe -m app_loja.bootstrap_windows
.\.venv-windows\Scripts\python.exe -m app_loja.start_windows
```

El destino siempre es `127.0.0.1`. El instalador verifica puerto, privilegios,
ausencia de la base y de la role de conexión, y compatibilidad de las roles
internas. Si aparece una falla después de crear la base, la conserva: no
repetir ni eliminar nada en ese caso, pedir revisión técnica. Con otro puerto de
PostgreSQL, usar `--port NUMERO` al instalar y `--db-port NUMERO` al iniciar.

La aplicación no se ejecuta como `postgres` ni necesita privilegios Windows de
administrador. Mantener abierta la ventana de la tienda; cerrarla o `Ctrl+C`
detiene solo la aplicación. El PostgreSQL instalado como servicio sigue
funcionando.

### Comprobación inicial

- Entrar con cada rol y verificar que el menú muestra solo sus secciones.
- Como Empleado, abrir `http://127.0.0.1:5000/caixa`: debe responder que el rol
  no tiene acceso.
- Como Cajero, abrir Cierre del día: no debe pedir PIN.
- Ejecutar `instalar.bat` otra vez: debe informar que la base ya existe y
  conservarla.

No confirmar un Cierre ni registrar operaciones reales solo para comprobar la
instalación.

## Registro de validación Windows (16/11/2026, varios equipos)

`ejecutar_pruebas.bat`, mismo entorno y cluster temporal:

- Suite completa: 171 pruebas, 0 fallas, 11 omitidas; fase TCP con SCRAM: 10 y
  15 aprobadas.
- Modo servidor: el servidor de producción respondió la página de ingreso en
  una prueba real por HTTP; direcciones públicas rechazadas antes de consultar
  el banco; el modo guardado, `--red`, `--local` y `--sin-navegador`
  verificados; el script del firewall abre solo el perfil privado y la subred
  local.

No ejecutado: la conexión desde un segundo equipo real, la creación de la
regla del firewall (requiere permiso de administrador del responsable), el
inicio automático al iniciar sesión y el recorrido interactivo del asistente.

## Registro de validación Windows (15/11/2026, roles)

`ejecutar_pruebas.bat` en Windows 11 con PostgreSQL 16, contra un cluster
temporal propio, detenido y borrado al terminar:

- `schema.sql`, `phase0_functional.sql`, `phase0_concurrency.py` y
  `phase0_closing.sql`: aprobados.
- Suite completa: 161 pruebas, 0 fallas, 11 omitidas (pruebas POSIX y las de la
  fase TCP, que se ejecutan aparte). Incluye la matriz de roles por menú, ruta
  y función del banco.
- Fase TCP con SCRAM y registro detallado: `test_bootstrap_windows.py` (10) y
  `test_windows_practico.py` (15) aprobados: instalación con tres roles y
  categorías, archivo de la base anterior con reutilización de la role de
  conexión, cambio de contraseña de un rol, respaldo y restauración.

No ejecutado: el recorrido interactivo de `instalar.bat` y de
`cambiar_contrasena.bat` (piden contraseñas por teclado), la creación del acceso
directo en el Escritorio real y una revisión visual de las pantallas en el
navegador. Las 6 pruebas POSIX de `test_bootstrap_local.py` siguen requiriendo
el runner Linux; el instalador Linux crea una única cuenta con rol
Administrador.

Los registros siguientes son anteriores a los roles y mencionan el PIN general,
que ya no existe.

## Registro de validación Windows (15/11/2026, antes de los roles)

`tests\run_windows.py` (`ejecutar_pruebas.bat`) en Windows 11 con PostgreSQL
16, contra un cluster temporal propio, detenido y borrado al terminar:

- `schema.sql`, `phase0_functional.sql`, `phase0_concurrency.py` y
  `phase0_closing.sql`: aprobados.
- Suite completa: 167 pruebas, 0 fallas, 12 omitidas (pruebas POSIX y las de la
  fase TCP, que se ejecutan aparte).
- Fase TCP con SCRAM y registro detallado: `test_bootstrap_windows.py` (17) y
  `test_windows_practico.py` (15) aprobados, incluido respaldo real con
  `pg_dump`, restauración en base nueva y rechazo de reemplazo.

No ejecutado: el recorrido interactivo de `instalar.bat` (pide contraseñas por
teclado) y la creación del acceso directo en el Escritorio real; el mismo
comando de acceso directo se probó en una carpeta temporal. Las 6 pruebas POSIX
de `test_bootstrap_local.py` siguen requiriendo el runner Linux.

## Registro de validación Windows (04/11/2026)

### Aprobado

- `test_bootstrap_windows.WindowsPostgresTests`: 3 pruebas, 0 fallas, contra un
  cluster PostgreSQL 16 descartable en TCP con SCRAM, UTF-8 y logging detallado.
  La instalación limpia y el rechazo de repetición pasaron; la falla de
  inicialización conservó la base sin crear el login; el fallo de secreto
  revirtió categorías, usuario y role sin registrar secretos.
- `test_bootstrap_windows.py` sin el runner PostgreSQL: 17 pruebas, 0 fallas y
  3 pruebas PostgreSQL omitidas porque ese cluster no estaba habilitado en esa
  ejecución. Las 3 omitidas se ejecutaron y aprobaron por separado arriba.
- El log del runner Windows se lee explícitamente como UTF-8; la lectura con la
  codificación predeterminada de Windows fallaba en el cluster UTF-8.

El cluster de pruebas fue detenido y eliminado. Las pruebas no modificaron la
base de uso real ni realizaron operaciones financieras.

### Pendiente o no ejecutado

- Las 6 pruebas PostgreSQL de `test_bootstrap_local.py` requieren el runner
  POSIX: socket Unix, rutas `/usr/bin` y `psql`, y permisos `sudo` opcionales.
  No se ejecutaron en su entorno previsto; la invocación directa en Windows no
  es una ejecución válida de esos contratos y WSL no estuvo disponible.
- El intento de ejecutar aisladamente el caso de retorno de Precios no llegó al
  proceso de prueba durante la preparación del cluster; se detuvo y eliminó el
  cluster temporal. El recorrido también forma parte de la integración amplia
  que aprobó 145 pruebas en la ejecución anterior.
- `GET /login` respondió HTTP 200 y el listener está activo en
  `127.0.0.1:5000`; la consulta inicial desde el sandbox no podía acceder al
  loopback. En la comprobación manual, el usuario informó que el PIN se pidió
  en las dos entradas a la zona protegida. El inicio de la aplicación por sí
  solo no pide PIN, como corresponde.
- La automatización visual no pudo identificar con confianza la URL actual del
  navegador y se detuvo sin introducir credenciales. El resultado del flujo
  visual queda registrado como confirmación del usuario, no como observación
  directa de la automatización.
