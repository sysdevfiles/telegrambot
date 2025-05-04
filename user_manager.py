import json
import datetime
import os
import shutil
from dotenv import load_dotenv
import subprocess # Import subprocess module
import logging # Use logging for better output control

CONFIG_FILE = '/etc/zivpn/config.json'
BACKUP_DIR = 'backups' # Directorio local para backups

# Get a logger instance (optional, but good practice)
logger_usermanager = logging.getLogger(__name__)

# --- Funciones de bajo nivel para leer/escribir JSON ---

def _load_data() -> list:
    """Carga los datos desde el archivo JSON. Devuelve una lista vacía en caso de error."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Advertencia: El archivo de configuración {CONFIG_FILE} no existe. Se creará uno vacío.")
        _save_data([]) # Intenta crear el archivo
        return []
    if os.path.getsize(CONFIG_FILE) == 0:
         print(f"Advertencia: El archivo de configuración {CONFIG_FILE} está vacío. Se tratará como lista vacía.")
         return []
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                print(f"Error: El contenido de {CONFIG_FILE} no es una lista JSON. Se devolverá una lista vacía.")
                return []
            return data
    except json.JSONDecodeError:
        print(f"Error: No se pudo decodificar el JSON en {CONFIG_FILE}. ¿Está corrupto?")
        return [] # Devuelve lista vacía para evitar fallos mayores
    except IOError as e:
        print(f"Error de E/S al leer {CONFIG_FILE}: {e}")
        return [] # Devuelve lista vacía

def _save_data(data: list):
    """Guarda los datos en el archivo JSON."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        print(f"Error de E/S al escribir en {CONFIG_FILE}: {e}")
        print("Verifica los permisos de escritura.")
        return False
    except TypeError as e:
        print(f"Error: Los datos a guardar no son serializables a JSON: {e}")
        return False

# --- Funciones de gestión de usuarios ---

def _restart_zivpn_service():
    """Intenta reiniciar el servicio zivpn.service."""
    command = ["systemctl", "restart", "zivpn.service"]
    try:
        # Execute the command
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger_usermanager.info(f"Comando '{' '.join(command)}' ejecutado exitosamente.")
        # Optional: Log stdout/stderr if needed
        # logger_usermanager.debug(f"stdout: {result.stdout}")
        # logger_usermanager.debug(f"stderr: {result.stderr}")
        return True
    except FileNotFoundError:
        logger_usermanager.error(f"Error: El comando 'systemctl' no se encontró. ¿Está systemd instalado y en el PATH?")
        return False
    except subprocess.CalledProcessError as e:
        logger_usermanager.error(f"Error al ejecutar '{' '.join(command)}'. Código de retorno: {e.returncode}")
        logger_usermanager.error(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        logger_usermanager.error(f"Error inesperado al ejecutar '{' '.join(command)}': {e}")
        return False

def init_storage():
    """Inicializa el archivo de configuración si no existe y el directorio de backups."""
    # Asegurar que el archivo JSON existe (lo hace _load_data si no existe)
    _load_data()
    # Crear directorio de backups si no existe
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
            print(f"Directorio de backups creado en: {BACKUP_DIR}")
        except OSError as e:
            print(f"Error al crear el directorio de backups {BACKUP_DIR}: {e}")

# Modificado para aceptar y guardar creator_id
def add_user(telegram_id: int, creator_id: int) -> bool:
    """Agrega un nuevo usuario o lo reactiva si ya existe, asociándolo a un creador."""
    users = _load_data()
    now = datetime.datetime.now()
    creation_date = now.strftime("%Y-%m-%d %H:%M:%S")
    expiration_date = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    action_performed = "agregado" # Default action text

    user_found = False
    for user in users:
        if user.get('telegram_id') == telegram_id:
            # Reactivar: Actualiza fechas y también el creador (opcional, podría mantenerse el original)
            user['creation_date'] = creation_date
            user['expiration_date'] = expiration_date
            user['creator_id'] = creator_id # Actualiza el creador en reactivación
            user_found = True
            action_performed = "reactivado" # Update action text
            logger_usermanager.info(f"Usuario {telegram_id} {action_performed} por {creator_id}.")
            break

    if not user_found:
        users.append({
            'telegram_id': telegram_id,
            'creation_date': creation_date,
            'expiration_date': expiration_date,
            'creator_id': creator_id # Añade el creador
        })
        logger_usermanager.info(f"Usuario {telegram_id} {action_performed} por {creator_id}.")

    if _save_data(users):
        logger_usermanager.info(f"Datos guardados. Intentando reiniciar zivpn.service tras {action_performed} de usuario {telegram_id}...")
        if not _restart_zivpn_service():
             # Log or handle the error if the restart fails, but don't necessarily fail the add_user operation
             logger_usermanager.warning(f"No se pudo reiniciar zivpn.service después de {action_performed} de usuario {telegram_id}.")
        return True # Return True because user data was saved
    else:
        return False # Return False if saving data failed

# Modificado para verificar creator_id
def delete_user(telegram_id: int, admin_id: int) -> tuple[bool, str]:
    """Elimina un usuario si el admin_id coincide con el creator_id."""
    users = _load_data()
    initial_length = len(users)
    user_to_delete = None
    user_index = -1

    for i, user in enumerate(users):
        if user.get('telegram_id') == telegram_id:
            user_to_delete = user
            user_index = i
            break

    if user_to_delete is None:
        return False, "Usuario no encontrado."

    if user_to_delete.get('creator_id') != admin_id:
        # Comprobar si el que intenta borrar es el ADMIN_TELEGRAM_ID original (override)
        # Cargar ADMIN_TELEGRAM_ID de .env para la comparación
        load_dotenv() # Asegurarse de que las variables de entorno estén cargadas
        original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
        original_admin_id = None
        if original_admin_id_str:
            try:
                original_admin_id = int(original_admin_id_str)
            except ValueError:
                pass # Ignorar si no es un entero válido

        if admin_id != original_admin_id: # Solo permitir override al admin original
             print(f"Intento de eliminación fallido: Usuario {admin_id} no creó al usuario {telegram_id} (creado por {user_to_delete.get('creator_id')}).")
             return False, "No tienes permiso para eliminar este usuario (no lo creaste)."
        else:
             print(f"INFO: Admin original {admin_id} eliminando usuario {telegram_id} creado por {user_to_delete.get('creator_id')}.")


    # Eliminar el usuario de la lista
    del users[user_index]

    if _save_data(users):
        return True, "Usuario eliminado exitosamente."
    else:
        return False, "Error al guardar los cambios tras eliminar el usuario."

# Modificado para verificar creator_id
def renew_user(telegram_id: int, admin_id: int) -> tuple[bool, str]:
    """Extiende el acceso de un usuario por 30 días si admin_id coincide con creator_id."""
    users = _load_data()
    user_found = False
    original_creator_id = None
    now = datetime.datetime.now()
    new_expiration_date = (now + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

    user_index = -1
    for i, user in enumerate(users):
        if user.get('telegram_id') == telegram_id:
            user_index = i
            original_creator_id = user.get('creator_id')
            break

    if user_index == -1:
        return False, "Usuario no encontrado."

    # Verificar permiso
    if original_creator_id != admin_id:
        # Comprobar si el que intenta renovar es el ADMIN_TELEGRAM_ID original (override)
        load_dotenv()
        original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
        original_admin_id = None
        if original_admin_id_str:
            try:
                original_admin_id = int(original_admin_id_str)
            except ValueError:
                pass

        if admin_id != original_admin_id: # Solo permitir override al admin original
            print(f"Intento de renovación fallido: Usuario {admin_id} no creó al usuario {telegram_id} (creado por {original_creator_id}).")
            return False, "No tienes permiso para renovar este usuario (no lo creaste)."
        else:
            print(f"INFO: Admin original {admin_id} renovando usuario {telegram_id} creado por {original_creator_id}.")


    # Realizar la renovación
    users[user_index]['expiration_date'] = new_expiration_date
    # Opcional: Actualizar creation_date o incluso creator_id si la política lo requiere
    # users[user_index]['creator_id'] = admin_id # Si la renovación transfiere propiedad
    user_found = True


    if user_found:
        if _save_data(users):
            logger_usermanager.info(f"Datos guardados. Intentando reiniciar zivpn.service tras renovación de usuario {telegram_id}...")
            if not _restart_zivpn_service():
                logger_usermanager.warning(f"No se pudo reiniciar zivpn.service después de renovar usuario {telegram_id}.")
            return True, "Acceso de usuario renovado por 30 días."
        else:
            return False, "Error al guardar los cambios tras renovar el usuario."
    else:
        # Este caso ya está cubierto por la verificación de user_index == -1
        return False, "Usuario no encontrado para renovar."

def get_user(telegram_id: int) -> dict | None:
    """Obtiene los datos de un usuario por su ID de Telegram."""
    users = _load_data()
    for user in users:
        if user.get('telegram_id') == telegram_id:
            return user
    return None

# Modificado para filtrar por admin_id
def get_all_users(admin_id: int) -> list:
    """Obtiene todos los usuarios registrados creados por un admin_id específico."""
    users = _load_data()
    # Cargar ADMIN_TELEGRAM_ID de .env para la comparación
    load_dotenv()
    original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
    original_admin_id = None
    is_original_admin = False
    if original_admin_id_str:
        try:
            original_admin_id = int(original_admin_id_str)
            if admin_id == original_admin_id:
                is_original_admin = True
        except ValueError:
            pass # Ignorar si no es un entero válido

    # El admin original ve todos los usuarios, los demás solo los suyos
    if is_original_admin:
        print(f"Admin original {admin_id} listando todos los usuarios.")
        filtered_users = users
    else:
        print(f"Usuario {admin_id} listando sus usuarios creados.")
        filtered_users = [user for user in users if user.get('creator_id') == admin_id]

    # Ordenar por fecha de creación (opcional)
    try:
        # Añadir manejo para usuarios sin fecha (aunque no debería pasar con la lógica actual)
        filtered_users.sort(key=lambda x: datetime.datetime.strptime(x.get('creation_date', '1970-01-01 00:00:00'), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError) as e:
        print(f"Advertencia: No se pudo ordenar usuarios por fecha: {e}")
    return filtered_users

# --- Función de Backup ---

def create_backup() -> str | None:
    """Crea una copia de seguridad del archivo config.json."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: El archivo de configuración {CONFIG_FILE} no existe. No se puede crear backup.")
        return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Usar os.path.basename para obtener solo 'config.json'
    base_filename = os.path.basename(CONFIG_FILE)
    backup_filename = f"{base_filename}_{timestamp}.bak"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        shutil.copy2(CONFIG_FILE, backup_path)
        print(f"Backup creado exitosamente en: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Error al crear el backup de {CONFIG_FILE}: {e}")
        return None

