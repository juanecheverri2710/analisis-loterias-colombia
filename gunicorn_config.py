# gunicorn_config.py - Configuración de Gunicorn para Koyeb
import multiprocessing
import os

cpu_count = multiprocessing.cpu_count()

# Configuración de Binding
bind = "0.0.0.0:8000"

# Workers (procesos paralelos)
workers = cpu_count * 2
worker_class = "sync"
worker_connections = 1000

# ⭐ TIMEOUT MÁS IMPORTANTE ⭐
# ANTES: 30s (fallaba)
# AHORA: 120s (2 minutos, permite análisis)
timeout = 120

# Keep-Alive
keepalive = 5

# Límites de requests
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(q)s" "%(D)s"'
errorlog = "-"
loglevel = "info"

# Otros
daemon = False
pidfile = None
umask = 0
user = None
group = None
keyfile = None
certfile = None
