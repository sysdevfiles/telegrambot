import json
import datetime
import os
import shutil
from dotenv import load_dotenv
import subprocess
import logging

CONFIG_FILE = '/etc/zivpn/config.json'
TRACKING_FILE = '/etc/zivpn/manager_tracking.json' # Nuevo archivo de tracking
BACKUP_DIR = 'backups'

logger_usermanager = logging.getLogger(__name__)

# --- Default Structure ---
DEFAULT_CONFIG = {
  "listen": ":5667",
   "cert": "/etc/zivpn/zivpn.crt",
   "key": "/etc/zivpn/zivpn.key",
   "obfs":"zivpn",
   "auth": {
    "mode": "passwords",
    "config": ["root","neri","tomas","yasser","daniel","antonio","mono","doncarlos"]
  }
}
DEFAULT_TRACKING = [] # El archivo de tracking es una lista

# --- Funciones de bajo nivel para leer/escribir JSON ---

def _load_data() -> dict:
    """Carga la estructura completa desde config.json."""
    if not os.path.exists(CONFIG_FILE):
        logger_usermanager.warning(f"El archivo de configuración {CONFIG_FILE} no existe. Se creará con valores por defecto.")
        _save_data(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    if os.path.getsize(CONFIG_FILE) == 0:
         logger_usermanager.warning(f"El archivo de configuración {CONFIG_FILE} está vacío. Se usará la estructura por defecto.")
         return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, 'r') as f: data = json.load(f)
        if not isinstance(data, dict) or "auth" not in data or "config" not in data["auth"] or not isinstance(data["auth"]["config"], list):
             logger_usermanager.error(f"Estructura inválida en {CONFIG_FILE}. Usando defecto.")
             return DEFAULT_CONFIG.copy()
        return data
    except Exception as e:
        logger_usermanager.error(f"Error cargando {CONFIG_FILE}: {e}. Usando defecto.")
        return DEFAULT_CONFIG.copy()


def _save_data(data: dict) -> bool:
    """Guarda la estructura completa en config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f: json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger_usermanager.error(f"Error guardando {CONFIG_FILE}: {e}")
        return False

# --- Funciones para Tracking File ---

def _load_tracking_data() -> list:
    """Carga la lista de tracking desde manager_tracking.json."""
    if not os.path.exists(TRACKING_FILE):
        logger_usermanager.warning(f"El archivo de tracking {TRACKING_FILE} no existe. Se creará vacío.")
        _save_tracking_data(DEFAULT_TRACKING)
        return DEFAULT_TRACKING.copy()
    if os.path.getsize(TRACKING_FILE) == 0:
         logger_usermanager.warning(f"El archivo de tracking {TRACKING_FILE} está vacío.")
         return DEFAULT_TRACKING.copy()
    try:
        with open(TRACKING_FILE, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                logger_usermanager.error(f"El contenido de {TRACKING_FILE} no es una lista. Se usará lista vacía.")
                return DEFAULT_TRACKING.copy()
            # Validar entradas (opcional pero recomendado)
            valid_data = []
            for entry in data:
                if isinstance(entry, dict) and "username" in entry and "creator_id" in entry:
                    valid_data.append(entry)
                else:
                    logger_usermanager.warning(f"Entrada inválida encontrada en {TRACKING_FILE}: {entry}")
            return valid_data
    except json.JSONDecodeError:
        logger_usermanager.error(f"No se pudo decodificar JSON en {TRACKING_FILE}. Se usará lista vacía.")
        return DEFAULT_TRACKING.copy()
    except IOError as e:
        logger_usermanager.error(f"Error de E/S al leer {TRACKING_FILE}: {e}. Se usará lista vacía.")
        return DEFAULT_TRACKING.copy()

def _save_tracking_data(data: list) -> bool:
    """Guarda la lista de tracking en manager_tracking.json."""
    try:
        with open(TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        logger_usermanager.error(f"Error de E/S al escribir en {TRACKING_FILE}: {e}")
        return False
    except TypeError as e:
        logger_usermanager.error(f"Error: Los datos de tracking no son serializables a JSON: {e}")
        return False

# --- Funciones de gestión ---

def _restart_zivpn_service():
    """Intenta reiniciar el servicio zivpn.service."""
    command = ["systemctl", "restart", "zivpn.service"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger_usermanager.info(f"Comando '{' '.join(command)}' ejecutado exitosamente.")
        return True
    except Exception as e:
        logger_usermanager.error(f"Error reiniciando zivpn.service: {e}")
        return False


def init_storage():
    """Inicializa ambos archivos de configuración si no existen."""
    _load_data() # Asegura config.json
    _load_tracking_data() # Asegura manager_tracking.json
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
            logger_usermanager.info(f"Directorio de backups creado en: {BACKUP_DIR}")
        except OSError as e:
            logger_usermanager.error(f"Error al crear el directorio de backups {BACKUP_DIR}: {e}")


def add_user(username: str, creator_id: int) -> tuple[bool, str]:
    """Agrega un username a config.json y registra al creador en manager_tracking.json."""
    if not username:
        return False, "El nombre de usuario no puede estar vacío."

    main_data = _load_data()
    tracking_data = _load_tracking_data()
    config_list = main_data.get("auth", {}).get("config", [])

    # Verificar si ya existe en config.json
    if username in config_list:
        return False, f"El usuario '{username}' ya existe en la configuración principal."

    # Verificar si ya existe en tracking (redundante si no está en config, pero seguro)
    if any(entry.get("username") == username for entry in tracking_data):
         logger_usermanager.warning(f"Inconsistencia: Usuario '{username}' encontrado en tracking pero no en config. Se procederá a añadirlo a config.")
         # No retornamos error aquí, simplemente lo añadiremos a config.json

    # Añadir a config.json
    config_list.append(username)
    main_data["auth"]["config"] = config_list

    # Añadir a tracking.json (o actualizar si hubo inconsistencia)
    existing_track_entry = next((entry for entry in tracking_data if entry.get("username") == username), None)
    if existing_track_entry:
        existing_track_entry["creator_id"] = creator_id # Actualizar creador si ya existía en tracking
    else:
        tracking_data.append({"username": username, "creator_id": creator_id})

    # Guardar ambos archivos
    if _save_data(main_data) and _save_tracking_data(tracking_data):
        logger_usermanager.info(f"Usuario '{username}' agregado por {creator_id}. Intentando reiniciar zivpn.service...")
        if not _restart_zivpn_service():
             logger_usermanager.warning(f"No se pudo reiniciar zivpn.service después de agregar a '{username}'.")
        return True, f"Usuario '{username}' agregado exitosamente."
    else:
        # Intentar revertir si es posible (complejo, por ahora solo loguear)
        logger_usermanager.error(f"Error al guardar uno o ambos archivos para agregar a '{username}'. Estado puede ser inconsistente.")
        return False, f"Error crítico al guardar la configuración para '{username}'. Revisa los logs."

def delete_user(username: str, admin_id: int) -> tuple[bool, str]:
    """Elimina un username de ambos archivos, verificando permisos."""
    if not username:
        return False, "El nombre de usuario no puede estar vacío."
    if username.lower() == "root":
         return False, "No se permite eliminar al usuario 'root'."

    main_data = _load_data()
    tracking_data = _load_tracking_data()
    config_list = main_data.get("auth", {}).get("config", [])

    # Encontrar entrada en tracking
    track_entry_index = -1
    original_creator_id = None
    for i, entry in enumerate(tracking_data):
        if entry.get("username") == username:
            track_entry_index = i
            original_creator_id = entry.get("creator_id")
            break

    if track_entry_index == -1:
        # Si no está en tracking, pero sí en config (inconsistencia), permitir borrar solo al admin
        if username in config_list:
             load_dotenv()
             original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
             try:
                 original_admin_id = int(original_admin_id_str) if original_admin_id_str else None
             except ValueError:
                 original_admin_id = None

             if admin_id == original_admin_id:
                 logger_usermanager.warning(f"Usuario '{username}' encontrado en config pero no en tracking. Admin {admin_id} procederá a eliminarlo de config.")
                 config_list.remove(username)
                 main_data["auth"]["config"] = config_list
                 if _save_data(main_data):
                     if not _restart_zivpn_service(): logger_usermanager.warning(f"No se pudo reiniciar zivpn.service tras eliminar inconsistencia '{username}'.")
                     return True, f"Usuario '{username}' (inconsistente) eliminado de config.json por Admin."
                 else:
                     return False, f"Error al guardar config.json tras intentar eliminar inconsistencia '{username}'."
             else:
                 return False, f"Usuario '{username}' no encontrado en los registros de gestión. Contacta al Admin."
        else:
            return False, f"El usuario '{username}' no se encontró."


    # Verificar permisos
    load_dotenv()
    original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
    try:
        original_admin_id = int(original_admin_id_str) if original_admin_id_str else None
    except ValueError:
        original_admin_id = None

    is_creator = (original_creator_id == admin_id)
    is_main_admin = (admin_id == original_admin_id)

    if not is_creator and not is_main_admin:
        return False, f"No tienes permiso para eliminar a '{username}' (Creado por: {original_creator_id})."

    # Proceder con la eliminación
    if username in config_list:
        config_list.remove(username)
        main_data["auth"]["config"] = config_list
    else:
        logger_usermanager.warning(f"Usuario '{username}' encontrado en tracking pero no en config.json al eliminar.")

    del tracking_data[track_entry_index]

    # Guardar ambos archivos
    if _save_data(main_data) and _save_tracking_data(tracking_data):
        logger_usermanager.info(f"Usuario '{username}' eliminado por {admin_id}. Intentando reiniciar zivpn.service...")
        if not _restart_zivpn_service():
             logger_usermanager.warning(f"No se pudo reiniciar zivpn.service después de eliminar a '{username}'.")
        return True, f"Usuario '{username}' eliminado exitosamente."
    else:
        logger_usermanager.error(f"Error al guardar uno o ambos archivos para eliminar a '{username}'. Estado puede ser inconsistente.")
        return False, f"Error crítico al guardar la configuración para '{username}'. Revisa los logs."


def get_all_users(admin_id: int) -> list[str]:
    """Obtiene la lista de usernames creados por admin_id (o todos si es main admin)."""
    tracking_data = _load_tracking_data()

    load_dotenv()
    original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
    try:
        original_admin_id = int(original_admin_id_str) if original_admin_id_str else None
    except ValueError:
        original_admin_id = None

    is_main_admin = (admin_id == original_admin_id)

    if is_main_admin:
        # Devolver todos los usernames registrados en el tracking
        usernames = [entry.get("username") for entry in tracking_data if entry.get("username")]
    else:
        # Devolver solo los usernames creados por este admin_id
        usernames = [entry.get("username") for entry in tracking_data if entry.get("creator_id") == admin_id and entry.get("username")]

    # Opcional: Ordenar alfabéticamente
    usernames.sort(key=str.lower)
    return usernames

# --- Función de Backup ---

def create_backup() -> str | None:
    """Crea una copia de seguridad de config.json y manager_tracking.json."""
    backup_paths = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    files_to_backup = {
        CONFIG_FILE: "config.json",
        TRACKING_FILE: "manager_tracking.json"
    }

    success = True
    for file_path, base_name in files_to_backup.items():
        if not os.path.exists(file_path):
            logger_usermanager.error(f"Error: El archivo {file_path} no existe. No se puede crear backup.")
            success = False
            continue # Saltar al siguiente archivo

        backup_filename = f"{base_name}_{timestamp}.bak"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        try:
            shutil.copy2(file_path, backup_path)
            logger_usermanager.info(f"Backup de {base_name} creado exitosamente en: {backup_path}")
            backup_paths.append(backup_path)
        except Exception as e:
            logger_usermanager.error(f"Error al crear el backup de {file_path}: {e}")
            success = False

    # Devolver la ruta del backup principal (config.json) si tuvo éxito, o None si algo falló
    # Podríamos devolver una lista o un dict si fuera necesario manejar ambos archivos en el bot
    config_backup_path = next((p for p in backup_paths if CONFIG_FILE in p), None)
    return config_backup_path if success and config_backup_path else None

