import socket
import threading
import sys
import time
import configparser

def load_config(file_path="config.conf"):
    config = configparser.ConfigParser()
    config.read(file_path)

    try:
        cache_expiration_time = config.getint("cache", "expiration_time", fallback=60)
    except ValueError as e:
        print(f"[ERREUR CONFIGURATION] 'expiration_time' doit être un entier valide : {e}")
        sys.exit(1)

    return {
        "proxy_host": config.get("proxy", "host", fallback="0.0.0.0"),
        "proxy_port": config.getint("proxy", "port", fallback=8000),
        "apache_host": config.get("apache", "host", fallback="127.0.0.1"),
        "apache_port": config.getint("apache", "port", fallback=80),
        "cache_expiration_time": cache_expiration_time
    }

try:
    CONFIG = load_config("config.conf")
except (configparser.Error, FileNotFoundError) as e:
    print(f"[ERREUR CONFIGURATION] Impossible de charger le fichier de configuration : {e}")
    sys.exit(1)

PROXY_HOST = CONFIG["proxy_host"]
PROXY_PORT = CONFIG["proxy_port"]
APACHE_HOST = CONFIG["apache_host"]
APACHE_PORT = CONFIG["apache_port"]
CACHE_EXPIRATION_TIME = CONFIG["cache_expiration_time"]

server_running = True
server_lock = threading.Lock()
server = None

cache = {}

def is_cache_expired(cache_entry):
    """Vérifie si l'entrée de cache a expiré."""
    creation_time = cache_entry['timestamp']
    current_time = time.time()
    return (current_time - creation_time) > CACHE_EXPIRATION_TIME

def generate_cache_key(request_line):
    """Utilise directement la requête comme clé pour le cache."""
    return request_line.strip().lower()

def handle_client(client_socket):
    try:
        request = client_socket.recv(4096).decode()
        if not request:
            client_socket.close()
            return

        request_line = request.splitlines()[0]
        cache_key = generate_cache_key(request_line)

        if cache_key in cache:
            cache_entry = cache[cache_key]
            if is_cache_expired(cache_entry):
                print(f"[CACHE EXPIRE] La réponse pour la requête {request_line} a expiré.")
                del cache[cache_key]
            else:
                print(f"[CACHE HIT] Pour la requête : {request_line}")
                client_socket.sendall(cache_entry['data'])
                return

        print(f"[CACHE MISS] Pour la requête : {request_line}")
        apache_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        apache_socket.connect((APACHE_HOST, APACHE_PORT))
        apache_socket.sendall(request.encode())

        response = b""
        while True:
            chunk = apache_socket.recv(4096)
            if not chunk:
                break
            response += chunk
        apache_socket.close()

        cache[cache_key] = {
            'data': response,
            'timestamp': time.time()
        }

        client_socket.sendall(response)
    except Exception as e:
        print(f"[ERREUR CLIENT] {e}")
    finally:
        client_socket.close()

def start_proxy():
    global server, server_running
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((PROXY_HOST, PROXY_PORT))
    server.listen(5)
    print(f"[SERVEUR PROXY EN ÉCOUTE] Sur {PROXY_HOST}:{PROXY_PORT}")

    try:
        while True:
            with server_lock:
                if not server_running:
                    break
            try:
                client_socket, addr = server.accept()
                print(f"[CONNEXION ACCEPTÉE] Depuis {addr}")

                client_handler = threading.Thread(target=handle_client, args=(client_socket,))
                client_handler.start()
            except socket.error:
                break
    finally:
        if server:
            server.close()
        print("[SERVEUR PROXY ARRÊTÉ]")

def command_interface():
    global server_running, server
    while True:
        command = input("$server@proxy> ").strip().lower()
        if command == "clear cache" or command == "clear":
            cache.clear()
            print("[CACHE VIDÉ]")
        elif command.startswith("del "):
            _, cache_key = command.split(" ", 1)
            cache_key = cache_key.strip().lower()
            if cache_key in cache:
                del cache[cache_key]
                print(f"[CACHE SUPPRIMÉ] Clé : {cache_key}")
            else:
                print(f"[CACHE NON TROUVÉ] Clé : {cache_key}")
        elif command == "ls" or command == "liste":
            if cache:
                print("[LISTE DES CLÉS DE CACHES STOCKÉES] :")
                for i, key in enumerate(cache.keys(), start=1):
                    print(f"{i}. Clé : {key}")
            else:
                print("[CACHE VIDE]")
        elif command == "exit":
            print("[ARRÊT DU SERVEUR]")
            with server_lock:
                server_running = False
            if server:
                server.close()
            sys.exit(0)
        else:
            print(f"[COMMANDE INCONNUE] : {command}")

if __name__ == "__main__":
    try:
        proxy_thread = threading.Thread(target=start_proxy, daemon=True)
        proxy_thread.start()

        command_interface()

        proxy_thread.join()
        print("[APPLICATION TERMINÉE]")
    except KeyboardInterrupt:
        print("\n[ARRÊT PAR CTRL+C]")
        with server_lock:
            server_running = False
        if server:
            server.close()
        sys.exit(0)
