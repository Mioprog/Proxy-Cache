# Proxy-Cache

Un proxy HTTP avec cache et **tableau de bord web** d'administration.

## Fonctionnalités

- **Proxy HTTP** : relaie les requêtes clients vers un serveur Apache backend.
- **Cache en mémoire** : met en cache les réponses avec TTL configurable.
- **Dashboard web** : interface graphique accessible dans le navigateur pour visualiser les statistiques, parcourir les entrées en cache et effectuer des actions d'administration.
- **API REST** : endpoints JSON consommés par l'UI (et interrogeables directement).

---

## Démarrage rapide

### 1. Prérequis

```bash
pip install -r requirements.txt
```

### 2. Configuration

Copiez ou éditez `config.conf` :

```ini
[proxy]
host = 0.0.0.0
port = 8000

[apache]
host = 127.0.0.1
port = 80

[cache]
expiration_time = 60   # TTL en secondes

[dashboard]
host = 127.0.0.1       # 127.0.0.1 = accès local uniquement
port = 8080
# token = mysecrettoken  # décommentez pour activer l'auth par token
```

### 3. Lancer l'application

```bash
python proxyCache.py
```

Cela démarre simultanément :
- le **proxy** sur `0.0.0.0:8000` (configurable)
- le **dashboard** sur `http://127.0.0.1:8080` (configurable)

Ouvrez `http://127.0.0.1:8080` dans votre navigateur pour accéder au tableau de bord.

---

## Dashboard

Le dashboard affiche en temps réel (rafraîchissement automatique toutes les 10 s) :

| Indicateur | Description |
|------------|-------------|
| Cache Hits | Nombre de requêtes servies depuis le cache |
| Cache Misses | Nombre de requêtes transmises au backend |
| Taux de hit | `hits / (hits + misses)` en % |
| Entrées en cache | Nombre d'entrées actuellement stockées |
| Taille du cache | Taille totale des données mises en cache |
| Uptime | Durée de fonctionnement du proxy |
| TTL | Durée d'expiration des entrées |

### Actions disponibles

- **Rafraîchir** : recharge manuellement la liste des entrées.
- **Vider le cache** : supprime toutes les entrées.
- **Supprimer** (par ligne) : supprime une entrée spécifique.

---

## API REST

Tous les endpoints retournent du JSON.

### `GET /api/health`

Vérifie que le dashboard est opérationnel.

```bash
curl http://127.0.0.1:8080/api/health
```

```json
{"status": "ok", "timestamp": 1714000000.123}
```

---

### `GET /api/stats`

Retourne les statistiques du proxy/cache.

```bash
curl http://127.0.0.1:8080/api/stats
```

```json
{
  "hits": 42,
  "misses": 8,
  "cache_entries": 15,
  "cache_size_bytes": 204800,
  "cache_expiration_seconds": 60,
  "uptime_seconds": 3600.5
}
```

---

### `GET /api/cache`

Retourne la liste paginée des entrées en cache.

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `page` | int | 1 | Numéro de page |
| `per_page` | int | 20 | Entrées par page (max 200) |

```bash
curl "http://127.0.0.1:8080/api/cache?page=1&per_page=10"
```

```json
{
  "total": 15,
  "page": 1,
  "per_page": 10,
  "entries": [
    {
      "key": "get /index.html http/1.1",
      "size_bytes": 4096,
      "created_at": 1714000000.0,
      "expires_at": 1714000060.0,
      "expired": false
    }
  ]
}
```

---

### `DELETE /api/cache`

Vide tout le cache.

```bash
curl -X DELETE http://127.0.0.1:8080/api/cache
```

```json
{"cleared": 15}
```

---

### `DELETE /api/cache/{key}`

Supprime une entrée spécifique. La clé est la ligne de requête HTTP (ex : `get /index.html http/1.1`), encodée en URL.

```bash
curl -X DELETE "http://127.0.0.1:8080/api/cache/get%20%2Findex.html%20http%2F1.1"
```

```json
{"deleted": "get /index.html http/1.1"}
```

---

## Sécurité

### Accès local uniquement (défaut)

Par défaut `dashboard.host = 127.0.0.1` — le dashboard n'est accessible que depuis la machine locale.

### Token d'authentification (optionnel)

Pour exposer le dashboard sur un réseau, activez le token dans `config.conf` :

```ini
[dashboard]
host = 0.0.0.0
port = 8080
token = mysecrettoken
```

Puis passez le token dans chaque requête API :

```bash
curl -H "Authorization: Bearer mysecrettoken" http://<host>:8080/api/stats
```

> ⚠️ Pour une exposition publique, placez le dashboard derrière un reverse-proxy (nginx/caddy) avec TLS.

---

## Variables d'environnement / paramètres

Tous les paramètres sont définis dans `config.conf`. Il n'y a pas de variables d'environnement dédiées ; modifiez le fichier de configuration avant le démarrage.

| Section | Clé | Défaut | Description |
|---------|-----|--------|-------------|
| `[proxy]` | `host` | `0.0.0.0` | Adresse d'écoute du proxy |
| `[proxy]` | `port` | `8000` | Port d'écoute du proxy |
| `[apache]` | `host` | `127.0.0.1` | Adresse du serveur backend |
| `[apache]` | `port` | `80` | Port du serveur backend |
| `[cache]` | `expiration_time` | `60` | TTL du cache (secondes) |
| `[dashboard]` | `host` | `127.0.0.1` | Adresse d'écoute du dashboard |
| `[dashboard]` | `port` | `8080` | Port du dashboard |
| `[dashboard]` | `token` | *(vide)* | Token d'auth optionnel |

---

## Interface en ligne de commande

Le proxy expose également une interface CLI :

```
$server@proxy> clear        # vider le cache
$server@proxy> del <clé>    # supprimer une entrée
$server@proxy> ls            # lister les clés en cache
$server@proxy> exit          # arrêter le serveur
```

---

## Tests

```bash
pytest tests/test_dashboard.py -v
```
