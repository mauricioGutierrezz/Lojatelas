# Ingreso / Stock — ejecución local

> **Actualización 15/11/2026 — roles en lugar de PIN.** El PIN general ya no existe. Se entra eligiendo el rol (Administrador, Empleado o Cajero) y su contraseña; cada rol ve solo sus secciones. Precios es del Administrador; Cierre y Fondo inicial, del Cajero y del Administrador. Lo que esta guía diga sobre PIN, sesión compartida o `setup_pin` quedó sin efecto. Ver [INSTALACAO_WINDOWS](INSTALACAO_WINDOWS.md).

La decisión vigente permite sesión operativa compartida, sin login/logout individual por atención.
No exige autoria individual confiable como requisito de la operación normal; los responsables
registrados se conservan sin presentarlos como prueba de identidad individual.

## Preparación técnica, una sola vez

Requiere PostgreSQL local con base UTF-8 y `pgcrypto`, Python y las dependencias de
`app_loja/requirements.txt`. Las dependencias se instalan durante la preparación;
la operación de la tienda no utiliza internet ni recursos externos.

Desde la raíz del repositorio:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app_loja/requirements.txt
```

Para una primera instalación nueva en PostgreSQL local 16/main (puerto 5432),
desde la raíz, ejecutar como el usuario normal de la máquina:

```bash
.venv/bin/python -m app_loja.bootstrap_local --socket /var/run/postgresql --port 5432 --database urdimbre --db-user loja_app
```

Python se ejecuta como el usuario normal, incluso si la home/proyecto/venv son privados.
El comando solicita autorización mediante `sudo -v`; solamente el cliente del sistema
`sudo -n -u postgres -- /usr/bin/psql` realiza las operaciones PostgreSQL administrativas.
Ese proceso trabaja desde `/`, recibe el schema y las instrucciones por stdin y nunca
abre archivos de la home o ejecuta el Python del proyecto. No requiere cambiar permisos
de la home ni crear una role superusuario para el usuario normal.

Las contraseñas ingresadas no se pasan como argumentos, variables de entorno del proceso
elevado ni archivos temporales. La salida de errores SQL se mantiene privada para evitar
mostrar líneas que pudieran contener secretos. Antes de enviar credenciales, se desactiva
el logging SQL estándar solamente en la sesión técnica; no cambia la configuración del
cluster. La aplicación sigue usando `loja_app`.

El comando confirma socket local, puerto y permisos técnicos; exige escribir el nombre
de la base nueva. Rechaza bases existentes, roles LOGIN existentes y roles internos
incompatibles. Nunca borra, recrea o convierte una base. Pide nombre/login operativo,
las categorías existentes de la tienda y dos contraseñas nuevas, con confirmación y sin
mostrar caracteres: conexión PostgreSQL y operación. No hay contraseña predeterminada.

Crea la base UTF-8, instala `schema.sql` con el inicializador preservador y crea el
primer usuario activo con perfil `operador` y hash bcrypt. Crea una role LOGIN
`loja_app` sin privilegios elevados, miembro solamente de `loja_operador`, con
verificador SCRAM-SHA-256. No necesita membresía de `loja_owner` ni `loja_admin`.
El usuario operativo pertenece a `usuarios`; no es una role PostgreSQL.

Si la instalación falla después de crear la base, esta permanece para revisión técnica.
No se intenta borrarla ni repetir sobre ella. `app_loja.setup_local` sigue disponible
para la preparación técnica de una base ya inicializada, pero no sustituye este flujo.

`schema.sql` no es una migración. Los tests usan exclusivamente un cluster temporal
propio. No ejecutar el setup contra sockets o bases de QA existentes.

## Iniciar la aplicación

La aplicación **no carga `.env`**: usa solamente variables de entorno del proceso.
`app_loja/.env` no es configuración efectiva y está ignorado por Git. No guardar allí
contraseñas ni copiar placeholders como si fueran credenciales.

Para la instalación local anterior, PostgreSQL debe aceptar conexiones TCP locales con
contraseña en `127.0.0.1:5432` (configuración habitual de PostgreSQL 16/main). La
aplicación no usa la cuenta técnica `postgres`. En Bash, desde la raíz:

```bash
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_NAME=urdimbre
export DB_USER=loja_app
read -r -s -p 'Contraseña de conexión PostgreSQL: ' DB_PASSWORD
printf '\n'
export DB_PASSWORD
.venv/bin/python -m app_loja.run
unset DB_PASSWORD
```

El comando solicita la contraseña de conexión elegida durante el setup sin eco y no
la escribe en el historial ni en archivos. Al iniciar sesión en la aplicación, usar el
login y la contraseña **operativos** creados por el setup, no la contraseña PostgreSQL.

Abrir `http://127.0.0.1:5000` e ingresar con el usuario preparado. El servidor
escucha únicamente en la máquina local y no activa debug. Puede establecerse
`FLASK_SECRET_KEY` con un secreto local; si no se establece, se genera una clave
por ejecución y reiniciar la aplicación requiere iniciar sesión nuevamente.
Los productos y los ingresos confirmados permanecen en PostgreSQL.

## Operación de la atendente

1. Buscar en **Productos y stock** por nombre o categoría.
2. Si falta el producto, usar **Nuevo producto** y definir su precio inicial.
3. Elegir **Cargar rollos**, indicar cuántos tienen la misma cantidad y agregar
   otro grupo para un tamaño diferente. Se acepta coma decimal.
4. Revisar la cantidad de rollos y el total. **Corregir datos** vuelve al formulario.
5. Confirmar. Cada rollo obtiene código y stock disponible inmediatamente.
6. Abrir el producto para consultar declaración original, saldo y origen de cada
   rollo. El total y el mayor rollo disponible se muestran por separado.

El ejemplo de cuatro rollos de 30 m y uno de 45 m genera cinco lotes y 165 m en
total. Reintentar la misma confirmación devuelve el mismo ingreso. La confirmación
es una única transacción y no deja lotes parciales si falla.

El registro operativo no modifica precios existentes; esos cambios requieren Precios y PIN. No modifica declaraciones ni saldos existentes.
No están habilitados corte/ticket, caja/venta, aprobación de ingreso, informes,
alertas o tratamiento de divergencias.

## Verificación

```bash
bash tests/run_phase0_postgres.sh
git diff --check
```

El runner requiere los binarios de PostgreSQL (`pg_config`, `initdb`, `pg_ctl`,
`createdb`, `psql`) y ejecuta las pruebas SQL y de concurrencia del núcleo, los
tests de 1A y, al final, las verificaciones existentes de cierre. No utiliza la
base configurada para operación ni presume comportamiento posterior al cierre.

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

## Unidades y stock

- **m**: ingreso por cantidad de rollos × metros por rollo. 4 × 30 + 1 × 45 crea cinco rollos físicos y 165 m. Metros sugeridos y ancho son opcionales.
- **kg**: ingreso por cantidad de piezas × peso por pieza. 30 × 10 crea treinta piezas y 300 kg. Peso sugerido opcional; no requiere ancho.
- **un**: ingresar directamente una cantidad entera. El saldo se acumula por producto, sin rollos, piezas ni estados físicos. No se pide ancho ni tamaño sugerido.

Revisar y confirmar conserva declaración, documento, horario y responsable informado. La ficha muestra los saldos físicos o el agregado según la unidad, junto con movimientos por producto. Una salida de unidades no se atribuye a un ingreso específico.

El inicializador confirma nombre, puerto y socket, rechaza destinos distintos, bases reservadas o cualquier estructura existente. Todo el schema, incluyendo fotos/precios, se instala en una transacción. No migrar ni limpiar una base poblada; requiere revisión específica. Aplicación y schema nuevos deben instalarse juntos en base vacía. Preparaciones antiguas sin confirmar necesitan nueva revisión; tickets registrados no se convierten.
