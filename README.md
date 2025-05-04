# Telegram Bot Manager

Este es un bot de Telegram diseñado para administrar el acceso de otros usuarios, basado en su ID de Telegram y con una fecha de vencimiento. Utiliza un archivo JSON (`/etc/zivpn/config.json`) para almacenar los datos de los usuarios y permite una gestión multi-administrador donde cada "manager" solo puede gestionar los usuarios que ha creado, con un administrador principal que tiene control total.

## Características

*   **Gestión de Usuarios:** Añadir, eliminar y renovar usuarios.
*   **Control de Acceso:** Vencimiento automático de 30 días.
*   **Multi-Manager:** Los usuarios pueden gestionar a los usuarios que ellos mismos añaden.
*   **Admin Override:** Un administrador principal (definido en `.env`) puede gestionar a todos los usuarios.
*   **Almacenamiento JSON:** Los datos se guardan en `/etc/zivpn/config.json`.
*   **Auditoría:** Las acciones administrativas se registran en `/etc/zivpn/admin_log.json`.
*   **Backup:** El administrador principal puede crear backups del archivo de configuración.
*   **Instalación Automatizada:** Script `install.sh` para configurar un VPS Ubuntu/Debian.

## Instalación en VPS (Ubuntu/Debian)

El script `install.sh` automatiza la configuración del entorno necesario en un VPS. **Este script está diseñado para ser ejecutado como usuario `root`.**

### Instalación Rápida (One-Liner)

Puedes descargar y ejecutar el script directamente como `root` con el siguiente comando:

```bash
wget --no-cache https://raw.githubusercontent.com/sysdevfiles/telegrambot/main/install.sh -O install.sh && chmod +x install.sh && bash install.sh && rm install.sh
```
*Nota: Este comando asume que estás ejecutándolo como `root`. Si lo ejecutas como un usuario con `sudo`, usa `sudo bash install.sh` en lugar de `bash install.sh`.*

Después de ejecutar este comando, procede directamente a la sección de **Configuración**.

### Instalación Manual

Si prefieres descargar el script manualmente:

1.  **Copiar el script al VPS:**
    ```bash
    # Desde tu máquina local, reemplaza <IP_DEL_VPS>
    scp install.sh root@<IP_DEL_VPS>:/root/
    ```

2.  **Conectar al VPS como root:**
    ```bash
    ssh root@<IP_DEL_VPS>
    ```

3.  **Navegar al directorio donde copiaste el script:**
    ```bash
    cd /root/
    ```

4.  **Dar Permisos de Ejecución:**
    ```bash
    chmod +x install.sh
    ```

5.  **Ejecutar el Script:**
    ```bash
    ./install.sh
    ```
    Este script (ejecutado como `root`):
    *   Realizará una limpieza de la instalación anterior en `/opt/telegram_bot_manager`.
    *   Actualizará el sistema.
    *   Instalará `git`, `python3`, `pip`, `venv`, `sqlite3`.
    *   Clonará el repositorio desde `https://github.com/sysdevfiles/telegrambot.git` a `/opt/telegram_bot_manager/telegrambot`.
    *   Creará un entorno virtual (`venv`) e instalará las dependencias Python.
    *   Creará el directorio `/etc/zivpn` y los archivos `config.json`, `admin_log.json`.
    *   Establecerá los permisos correctos en `/etc/zivpn` para `root:root`.
    *   Creará el directorio `backups` dentro del proyecto.
    *   Guardará un log detallado en `/root/telegram_bot_manager_install.log`.

## Configuración

Después de ejecutar `install.sh`, necesitas configurar tus credenciales:

1.  **Navega al directorio del proyecto:**
    ```bash
    cd /opt/telegram_bot_manager/telegrambot
    ```
    *(Opcional si usas la ruta completa en el siguiente paso)*

2.  **Crea el archivo `.env` si no existe:**
    ```bash
    touch /opt/telegram_bot_manager/telegrambot/.env
    ```

3.  **Edita el archivo `.env`:**
    Usa un editor como `nano` con la ruta completa:
    ```bash
    nano /opt/telegram_bot_manager/telegrambot/.env
    ```

4.  **Añade tus credenciales:**
    Reemplaza `TU_TOKEN_AQUI` con el token de tu bot de Telegram y `TU_ID_DE_ADMIN_AQUI` con tu ID numérico de Telegram (este será el administrador principal con override).
    ```dotenv
    TELEGRAM_BOT_TOKEN=TU_TOKEN_AQUI
    ADMIN_TELEGRAM_ID=TU_ID_DE_ADMIN_AQUI
    ```

5.  **Guarda y Cierra:** En `nano`, presiona `Ctrl+X`, luego `Y`, y finalmente `Enter`.

6.  **Reinicia el servicio (si ya estaba corriendo):** Si modificaste `.env` después de la instalación inicial, reinicia el servicio para que tome los nuevos valores:
    ```bash
    systemctl restart telegrambot
    ```

## Ejecución y Gestión del Servicio

El script `install.sh` configura el bot para que se ejecute automáticamente como un servicio `systemd` llamado `telegrambot`. Se inicia automáticamente después de la instalación y en cada arranque del sistema.

Puedes gestionar el servicio usando los siguientes comandos (ejecutados como `root`):

*   **Verificar Estado:**
    ```bash
    systemctl status telegrambot
    ```

*   **Ver Logs en Tiempo Real:**
    ```bash
    journalctl -u telegrambot -f --no-pager
    ```
    (Presiona `Ctrl+C` para salir)

*   **Ver Logs Anteriores:**
    ```bash
    journalctl -u telegrambot --no-pager
    ```

*   **Detener el Servicio:**
    ```bash
    systemctl stop telegrambot
    ```

*   **Iniciar el Servicio:**
    ```bash
    systemctl start telegrambot
    ```

*   **Reiniciar el Servicio:**
    (Útil después de cambiar la configuración en `.env` o actualizar el código manualmente)
    ```bash
    systemctl restart telegrambot
    ```

*   **Deshabilitar Inicio Automático:**
    ```bash
    systemctl disable telegrambot
    ```

*   **Habilitar Inicio Automático:**
    ```bash
    systemctl enable telegrambot
    ```

## Uso

Interactúa con el bot en Telegram. Los comandos disponibles son:

*   `/start`: Inicia la interacción y verifica el estado del acceso.
*   `/help`: Muestra el menú de comandos de gestión.
*   `/add <user_id>`: Añade un nuevo usuario (creado por ti) con 30 días de acceso.
*   `/delete <user_id>`: Elimina un usuario que hayas creado (o cualquier usuario si eres el admin principal).
*   `/update <user_id>`: Renueva por 30 días el acceso de un usuario que hayas creado (o cualquier usuario si eres el admin principal).
*   `/list`: Lista los usuarios que has creado (o todos si eres el admin principal).
*   `/backup`: (Solo Admin Principal) Crea una copia de seguridad de `config.json` y la envía por Telegram.

## Actualización

Para actualizar el bot a la última versión del repositorio:

1.  **Conéctate al VPS como `root`.**
2.  **Ejecuta el script de instalación nuevamente:**
    ```bash
    cd /root/ # O donde hayas guardado install.sh
    ./install.sh
    ```
    El script se encargará de limpiar la instalación anterior, obtener la última versión del código de GitHub, reinstalar dependencias y reiniciar automáticamente el servicio `systemd`. **Nota:** Esto reiniciará los archivos en `/etc/zivpn`. Si necesitas persistencia de datos, modifica el script `install.sh` para no sobrescribir `config.json` y `admin_log.json`.
3.  **Verifica el archivo `.env`** en `/opt/telegram_bot_manager/telegrambot` por si necesitas ajustarlo (normalmente no será necesario si solo actualizas el código).
4.  **Verifica el estado del servicio** después de que el script termine:
    ```bash
    systemctl status telegrambot
    ```
