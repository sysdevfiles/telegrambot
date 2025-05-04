import json
import datetime
import os

# Apunta al archivo de log administrativo dedicado
LOG_FILE = '/etc/zivpn/admin_log.json'

def log_action(admin_id: int, action: str, target_username: str | None = None, details: str = ""):
    """Registra una acción administrativa en el archivo JSON."""
    log_entry = {
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'admin_id': admin_id,
        'action': action,
        'target_username': target_username,
        'details': details
    }

    try:
        # Asegurarse de que el archivo exista y sea un JSON válido (lista)
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            # Intenta crear/inicializar el archivo si falta (aunque install.sh debería hacerlo)
            try:
                with open(LOG_FILE, 'w') as f:
                    json.dump([], f)
                print(f"Advertencia: El archivo de log {LOG_FILE} no existía o estaba vacío. Se ha inicializado.")
            except IOError as ie:
                 print(f"Error crítico: No se pudo crear/inicializar el archivo de log {LOG_FILE}: {ie}")
                 print("Verifica los permisos del directorio /etc/zivpn/.")
                 # No continuar si no se puede escribir el log inicial
                 return


        # Leer logs existentes
        logs = [] # Inicializar por si falla la lectura
        try:
            with open(LOG_FILE, 'r') as f:
                logs = json.load(f)
                if not isinstance(logs, list): # Si no es una lista, empezar de nuevo
                    print(f"Advertencia: El archivo de log {LOG_FILE} no contenía una lista JSON válida. Se reiniciará.")
                    logs = []
        except json.JSONDecodeError:
            print(f"Advertencia: Error al decodificar JSON en {LOG_FILE}. Se reiniciará el log.")
            logs = [] # Si hay error de decodificación, empezar de nuevo
        except IOError as e:
             print(f"Error de E/S al leer el log ({LOG_FILE}): {e}")
             # Decide si continuar sin leer logs previos o detenerse
             # Por ahora, intentaremos añadir la nueva entrada a una lista vacía
             logs = []


        # Agregar nueva entrada
        logs.append(log_entry)

        # Escribir logs actualizados
        with open(LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=4)

    except IOError as e:
        print(f"Error de E/S al escribir en el log ({LOG_FILE}): {e}")
        print("Asegúrate de que el script tenga permisos de escritura para este archivo.")
    except Exception as e:
        print(f"Error inesperado al escribir en el log ({LOG_FILE}): {e}")

