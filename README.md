# API de donaciones

API REST con Flask y PostgreSQL para gestionar el registro e inicio de sesión de usuarios y administradores. La base de datos está pensada para conectarse a Neon.

## Requisitos

- Python 3.10 o superior
- Una base de datos PostgreSQL en Neon

## Configuración

Desde la carpeta `Api-algoritmos-Trabajo`, crea y activa un entorno virtual:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y reemplaza sus valores:

- `DATABASE_URL`: cadena de conexión PostgreSQL de Neon. Usa la cadena que proporciona Neon y conserva `sslmode=require`.
- `JWT_SECRET_KEY`: valor aleatorio largo y privado para firmar los tokens.
- `ADMIN_USERNAME` y `ADMIN_PASSWORD`: credenciales únicas del administrador. No hay registro público de administradores.
- `FRONTEND_ORIGINS`: orígenes permitidos para la interfaz, separados por comas. En Render, agrega el dominio HTTPS exacto de la página; conserva localhost si también probarás localmente.

Inicializa las tablas y ejecuta la API:

```powershell
flask --app app:create_app init-db
flask --app app:create_app run --debug
```

La API queda disponible por defecto en `http://127.0.0.1:5000`.

## Despliegue en Render

Configura el servicio web con estos comandos:

- **Root Directory:** `Api-algoritmos-Trabajo`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `gunicorn "app:create_app()"`

En la configuración del servicio agrega las variables `DATABASE_URL`, `JWT_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` y `FRONTEND_ORIGINS`. Antes de usar la API, crea las tablas una sola vez ejecutando `flask --app app:create_app init-db` desde la consola del servicio o desde un entorno local conectado a la misma base de Neon.

## Rutas

| Método | Ruta | Acceso | Descripción |
| --- | --- | --- | --- |
| `GET` | `/` | Público | Comprueba que la API está activa y muestra rutas principales |
| `POST` | `/api/auth/register` | Público | Registra nombre, correo, edad y contraseña |
| `POST` | `/api/auth/login` | Público | Inicia sesión de usuario con correo y contraseña |
| `POST` | `/api/admin/login` | Público | Inicia sesión de administrador con las credenciales del entorno |
| `GET` | `/api/users/me` | Token de usuario | Consulta los datos del usuario autenticado |
| `GET` | `/api/admin/me` | Token de administrador | Confirma la identidad del administrador autenticado |
| `POST` | `/api/donations` | Token de usuario | Registra tipo de objeto, albergue y mensaje |
| `GET` | `/api/admin/donations` | Token de administrador | Lista donaciones y datos de contacto del usuario |

Las rutas de inicio de sesión devuelven un token JWT de acceso válido por una hora. En las rutas protegidas envía el encabezado `Authorization: Bearer <token>`.

### Ejemplos de solicitudes

Registro (devuelve también `access_token` para iniciar la sesión):

```json
{
  "name": "Ana Pérez",
  "email": "ana@example.com",
  "age": 28,
  "password": "una-clave-segura"
}
```

Inicio de sesión de usuario:

```json
{
  "email": "ana@example.com",
  "password": "una-clave-segura"
}
```

Inicio de sesión de administrador:

```json
{
  "username": "admin@ejemplo.com",
  "password": "la-clave-configurada-en-el-entorno"
}
```

Si la pantalla de administrador pide correo, configura `ADMIN_USERNAME` con ese correo exacto. Las contraseñas de usuario se almacenan como hashes y nunca se incluyen en las respuestas.

La tabla `donation` se crea al ejecutar `init-db`; incluye `id`, `user_id`, `object_type`, `priority`, `shelter_name`, `message` y `created_at`. Si ya existe la tabla en Neon, aplica una vez `migrations/add_donation_priority.sql` en el SQL Editor de Neon antes de desplegar esta versión. El backend calcula la prioridad en el servidor: juguetes, útiles escolares y otro = 1; higiene personal = 2; ropa y calzado = 3; alimentos = 4. El formulario no envía ni muestra esa prioridad. El panel de administración sí la muestra y ordena primero los registros con número menor.

Ejemplo de solicitud para registrar una donación:

```json
{
  "object_type": "Ropa y calzado",
  "shelter_name": "Albergue Esperanza",
  "message": "Donaré ropa en buen estado."
}
```

## Pruebas

```powershell
python -m unittest discover -s tests
```
