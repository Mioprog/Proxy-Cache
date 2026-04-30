import threading
import time

# Shared cache storage: key -> {'data': bytes, 'timestamp': float}
cache = {}
cache_lock = threading.Lock()

# Runtime statistics
stats = {
    "hits": 0,
    "misses": 0,
    "start_time": time.time()
}

# Set by proxyCache at startup from config
cache_expiration_time = 60
