import json
import datetime
import os
import shutil
from dotenv import load_dotenv
import subprocess
import logging
from typing import List, Dict, Any, Tuple, Optional # Mejorar type hinting

CONFIG_FILE = '/etc/zivpn/config.json'
TRACKING_FILE = '/etc/zivpn/manager_tracking.json'
BOT_MANAGERS_FILE = '/etc/zivpn/bot_managers.json'
BACKUP_DIR = 'backups'

logger_usermanager = logging.getLogger(__name__)

# --- Default Structures ---
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
DEFAULT_TRACKING = [] # Lista de dicts: {"username": str, "creator_id": int, "creation_date": str, "expiration_date": str}
DEFAULT_BOT_MANAGERS = []

# --- Funciones de bajo nivel ---

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

def _load_tracking_data() -> List[Dict[str, Any]]:
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
            # Validar entradas con nueva estructura
            valid_data = []
            for entry in data:
                if (isinstance(entry, dict) and
                    "username" in entry and
                    "creator_id" in entry and
                    "creation_date" in entry and    # Nueva validación
                    "expiration_date" in entry):   # Nueva validación
                    valid_data.append(entry)
                else:
                    logger_usermanager.warning(f"Entrada inválida o incompleta encontrada en {TRACKING_FILE}: {entry}")
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

def _load_bot_managers() -> list[int]:
    """Carga la lista de IDs de gestores autorizados."""
    if not os.path.exists(BOT_MANAGERS_FILE):
        logger_usermanager.warning(f"El archivo de gestores {BOT_MANAGERS_FILE} no existe. Se creará vacío.")
        _save_bot_managers(DEFAULT_BOT_MANAGERS)
        return DEFAULT_BOT_MANAGERS.copy()
    if os.path.getsize(BOT_MANAGERS_FILE) == 0:
         logger_usermanager.warning(f"El archivo de gestores {BOT_MANAGERS_FILE} está vacío.")
         return DEFAULT_BOT_MANAGERS.copy()
    try:
        with open(BOT_MANAGERS_FILE, 'r') as f:
            data = json.load(f)
            if not isinstance(data, list):
                logger_usermanager.error(f"El contenido de {BOT_MANAGERS_FILE} no es una lista. Se usará lista vacía.")
                return DEFAULT_BOT_MANAGERS.copy()
            # Validar que sean enteros
            valid_ids = []
            for item in data:
                if isinstance(item, int):
                    valid_ids.append(item)
                else:
                    logger_usermanager.warning(f"Entrada no entera encontrada en {BOT_MANAGERS_FILE}: {item}")
            return valid_ids
    except json.JSONDecodeError:
        logger_usermanager.error(f"No se pudo decodificar JSON en {BOT_MANAGERS_FILE}. Se usará lista vacía.")
        return DEFAULT_BOT_MANAGERS.copy()
    except IOError as e:
        logger_usermanager.error(f"Error de E/S al leer {BOT_MANAGERS_FILE}: {e}. Se usará lista vacía.")
        return DEFAULT_BOT_MANAGERS.copy()

def _save_bot_managers(data: list[int]) -> bool:
    """Guarda la lista de IDs de gestores autorizados."""
    try:
        with open(BOT_MANAGERS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except IOError as e:
        logger_usermanager.error(f"Error de E/S al escribir en {BOT_MANAGERS_FILE}: {e}")
        return False
    except TypeError as e:
        logger_usermanager.error(f"Error: Los datos de gestores no son serializables a JSON: {e}")
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
    """Inicializa todos los archivos de configuración si no existen."""
    _load_data() # Asegura config.json
    _load_tracking_data() # Asegura manager_tracking.json
    _load_bot_managers() # Asegura bot_managers.json
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
            logger_usermanager.info(f"Directorio de backups creado en: {BACKUP_DIR}")
        except OSError as e:
            logger_usermanager.error(f"Error al crear el directorio de backups {BACKUP_DIR}: {e}")


def add_user(username: str, creator_id: int) -> Tuple[bool, str]:
    """Agrega username a config.json y registra creador y fechas en manager_tracking.json."""
    if not username: return False, "El nombre de usuario no puede estar vacío."

    main_data = _load_data()
    tracking_data = _load_tracking_data()
    config_list = main_data.get("auth", {}).get("config", [])

    if username in config_list: return False, f"El usuario '{username}' ya existe en la configuración principal."
    if any(entry.get("username") == username for entry in tracking_data):
         logger_usermanager.warning(f"Inconsistencia: Usuario '{username}' encontrado en tracking pero no en config. Se procederá a añadirlo a config.")

    # Calcular fechas
    now = datetime.datetime.now()
    creation_date_str = now.strftime("%Y-%m-%d %H:%M:%S")
    expiration_date = now + datetime.timedelta(days=30)
    expiration_date_str = expiration_date.strftime("%Y-%m-%d %H:%M:%S")

    # Añadir a config.json
    config_list.append(username)
    main_data["auth"]["config"] = config_list

    # Añadir/Actualizar tracking.json
    existing_track_entry = next((entry for entry in tracking_data if entry.get("username") == username), None)
    if existing_track_entry:
        existing_track_entry["creator_id"] = creator_id
        existing_track_entry["creation_date"] = creation_date_str # Actualizar fechas si había inconsistencia
        existing_track_entry["expiration_date"] = expiration_date_str
    else:
        tracking_data.append({
            "username": username,
            "creator_id": creator_id,
            "creation_date": creation_date_str,
            "expiration_date": expiration_date_str
        })

    # Guardar ambos archivos
    if _save_data(main_data) and _save_tracking_data(tracking_data):
        logger_usermanager.info(f"Usuario '{username}' agregado por {creator_id} hasta {expiration_date_str}. Reiniciando zivpn...")
        if not _restart_zivpn_service(): logger_usermanager.warning(f"No se pudo reiniciar zivpn.service después de agregar a '{username}'.")
        return True, f"Usuario '{username}' agregado exitosamente. Válido hasta {expiration_date.strftime('%Y-%m-%d')}."
    else:
        logger_usermanager.error(f"Error crítico al guardar la configuración para '{username}'.")
        return False, f"Error crítico al guardar la configuración para '{username}'. Revisa los logs."

def delete_user(username: str, admin_id: int) -> Tuple[bool, str]:
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

def renew_user(username: str, admin_id: int) -> Tuple[bool, str]:
    """Renueva la fecha de expiración de un usuario por 30 días."""
    if not username: return False, "El nombre de usuario no puede estar vacío."

    tracking_data = _load_tracking_data()

    # Encontrar entrada en tracking
    track_entry = None
    for entry in tracking_data:
        if entry.get("username") == username:
            track_entry = entry
            break

    if not track_entry:
        return False, f"El usuario '{username}' no se encontró en los registros."

    original_creator_id = track_entry.get("creator_id")

    # Verificar permisos (igual que en delete)
    load_dotenv()
    original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
    try: original_admin_id = int(original_admin_id_str) if original_admin_id_str else None
    except ValueError: original_admin_id = None

    is_creator = (original_creator_id == admin_id)
    is_main_admin = (admin_id == original_admin_id)

    if not is_creator and not is_main_admin:
        return False, f"No tienes permiso para renovar a '{username}' (Creado por: {original_creator_id})."

    # Calcular nueva fecha
    now = datetime.datetime.now()
    new_expiration_date = now + datetime.timedelta(days=30)
    new_expiration_date_str = new_expiration_date.strftime("%Y-%m-%d %H:%M:%S")

    # Actualizar fecha en la entrada
    track_entry["expiration_date"] = new_expiration_date_str
    # Opcional: Actualizar también creation_date si se quiere reflejar la renovación como "nueva creación"
    # track_entry["creation_date"] = now.strftime("%Y-%m-%d %H:%M:%S")

    # Guardar tracking_data
    if _save_tracking_data(tracking_data):
        logger_usermanager.info(f"Usuario '{username}' renovado por {admin_id} hasta {new_expiration_date_str}.")
        # No es estrictamente necesario reiniciar zivpn aquí si el usuario ya estaba en config.json
        # Pero si queremos asegurar consistencia por si zivpn lee fechas (improbable), lo hacemos.
        # if not _restart_zivpn_service(): logger_usermanager.warning(f"No se pudo reiniciar zivpn.service después de renovar a '{username}'.")
        return True, f"Usuario '{username}' renovado. Nuevo vencimiento: {new_expiration_date.strftime('%Y-%m-%d')}."
    else:
        logger_usermanager.error(f"Error al guardar tracking data al renovar a '{username}'.")
        return False, f"Error crítico al guardar la renovación para '{username}'. Revisa los logs."

def get_all_users(admin_id: int) -> List[Dict[str, Any]]:
    """Obtiene detalles (username, creator, expiration) de usuarios creados por admin_id (o todos si es main admin)."""
    tracking_data = _load_tracking_data()

    load_dotenv()
    original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
    try: original_admin_id = int(original_admin_id_str) if original_admin_id_str else None
    except ValueError: original_admin_id = None

    is_main_admin = (admin_id == original_admin_id)

    if is_main_admin:
        filtered_users = tracking_data # Devuelve la lista completa de dicts
    else:
        filtered_users = [entry for entry in tracking_data if entry.get("creator_id") == admin_id]

    # Opcional: Ordenar por fecha de expiración o nombre
    try:
        filtered_users.sort(key=lambda x: x.get("username", "").lower())
    except Exception as e:
        logger_usermanager.warning(f"No se pudo ordenar la lista de usuarios: {e}")

    return filtered_users # Devuelve lista de diccionarios

def check_and_expire_users() -> bool:
    """Verifica usuarios expirados, los elimina de ambos archivos y reinicia zivpn si hubo cambios."""
    logger_usermanager.info("Iniciando chequeo de usuarios expirados...")
    tracking_data = _load_tracking_data()
    main_data = _load_data()
    config_list = main_data.get("auth", {}).get("config", [])
    now = datetime.datetime.now()
    expired_usernames = []
    users_changed = False

    # Identificar expirados
    for entry in tracking_data:
        username = entry.get("username")
        exp_date_str = entry.get("expiration_date")
        if not username or not exp_date_str:
            continue
        try:
            exp_date = datetime.datetime.strptime(exp_date_str, "%Y-%m-%d %H:%M:%S")
            if exp_date < now:
                # No eliminar 'root' aunque hipotéticamente tuviera fecha
                if username.lower() != "root":
                    expired_usernames.append(username)
        except ValueError:
            logger_usermanager.warning(f"Formato de fecha inválido para usuario '{username}' en tracking: {exp_date_str}")

    if not expired_usernames:
        logger_usermanager.info("No se encontraron usuarios expirados.")
        return False # No hubo cambios

    logger_usermanager.info(f"Usuarios expirados encontrados: {', '.join(expired_usernames)}")

    # Eliminar de tracking_data
    new_tracking_data = [entry for entry in tracking_data if entry.get("username") not in expired_usernames]
    if len(new_tracking_data) != len(tracking_data):
        users_changed = True

    # Eliminar de config_list
    new_config_list = [user for user in config_list if user not in expired_usernames]
    if len(new_config_list) != len(config_list):
        main_data["auth"]["config"] = new_config_list
        users_changed = True

    # Guardar si hubo cambios
    if users_changed:
        logger_usermanager.info("Guardando cambios por expiración...")
        save_config_ok = _save_data(main_data)
        save_tracking_ok = _save_tracking_data(new_tracking_data)

        if save_config_ok and save_tracking_ok:
            logger_usermanager.info("Archivos actualizados. Reiniciando zivpn.service...")
            if not _restart_zivpn_service():
                logger_usermanager.error("¡FALLO CRÍTICO! No se pudo reiniciar zivpn.service después de eliminar usuarios expirados.")
            return True # Hubo cambios y se guardaron (independiente del reinicio)
        else:
            logger_usermanager.error("¡FALLO CRÍTICO! Error al guardar uno o ambos archivos después de procesar expiraciones. Estado inconsistente.")
            # Aquí podríamos intentar revertir, pero es complejo. Loguear es crucial.
            return False # Indicar que hubo un error al guardar
    else:
        # Esto no debería pasar si expired_usernames no estaba vacío, pero por seguridad.
        logger_usermanager.info("No se realizaron cambios efectivos en los archivos.")
        return False

# --- Funciones de gestión de acceso al bot ---

def add_bot_manager(user_id: int) -> tuple[bool, str]:
    """Añade un ID de usuario a la lista de gestores autorizados."""
    managers = _load_bot_managers()

    # Cargar ADMIN_TELEGRAM_ID para evitar añadirlo
    load_dotenv()
    original_admin_id_str = os.getenv('ADMIN_TELEGRAM_ID')
    try:
        original_admin_id = int(original_admin_id_str) if original_admin_id_str else None
    except ValueError:
        original_admin_id = None

    if user_id == original_admin_id:
        return False, "El administrador principal ya tiene acceso por defecto."

    if user_id in managers:
        return False, f"El usuario {user_id} ya está autorizado."

    managers.append(user_id)
    if _save_bot_managers(managers):
        logger_usermanager.info(f"Acceso concedido al usuario {user_id}.")
        return True, f"Acceso concedido al usuario {user_id}."
    else:
        return False, f"Error al guardar la lista de gestores al añadir a {user_id}."

def remove_bot_manager(user_id: int) -> tuple[bool, str]:
    """Elimina un ID de usuario de la lista de gestores autorizados."""
    managers = _load_bot_managers()

    if user_id not in managers:
        return False, f"El usuario {user_id} no se encontró en la lista de autorizados."

    managers.remove(user_id)
    if _save_bot_managers(managers):
        logger_usermanager.info(f"Acceso revocado al usuario {user_id}.")
        return True, f"Acceso revocado al usuario {user_id}."
    else:
        return False, f"Error al guardar la lista de gestores al revocar a {user_id}."

def is_bot_manager(user_id: int) -> bool:
    """Verifica si un ID de usuario está en la lista de gestores autorizados."""
    managers = _load_bot_managers()
    return user_id in managers

# --- Función de Backup ---

def create_backup() -> str | None:
    """Crea una copia de seguridad de config.json, tracking.json y bot_managers.json."""
    backup_paths = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    files_to_backup = {
        CONFIG_FILE: "config.json",
        TRACKING_FILE: "manager_tracking.json",
        BOT_MANAGERS_FILE: "bot_managers.json" # Añadido
    }

    success = True
    for file_path, base_name in files_to_backup.items():
        if not os.path.exists(file_path):
            logger_usermanager.error(f"Error: El archivo {file_path} no existe. No se puede crear backup.")
            success = False
            continue

        backup_filename = f"{base_name}_{timestamp}.bak"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        try:
            shutil.copy2(file_path, backup_path)
            logger_usermanager.info(f"Backup de {base_name} creado exitosamente en: {backup_path}")
            backup_paths.append(backup_path)
        except Exception as e:
            logger_usermanager.error(f"Error al crear el backup de {file_path}: {e}")
            success = False

    config_backup_path = next((p for p in backup_paths if CONFIG_FILE in p), None)
    return config_backup_path if success and config_backup_path else None

