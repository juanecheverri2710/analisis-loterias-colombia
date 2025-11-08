# gunicorn_config.py - VERSIÓN CORREGIDA
import multiprocessing
import os

cpu_count = multiprocessing.cpu_count()

bind = "0.0.0.0:8000"
workers = cpu_count * 2
worker_class = "sync"
worker_connections = 1000

# ⭐ AUMENTAR TIMEOUT A 180 SEGUNDOS (3 MINUTOS)
timeout = 180

keepalive = 5
max_requests = 1000
max_requests_jitter = 50

accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(q)s" "%(D)s"'
errorlog = "-"
loglevel = "info"

daemon = False
pidfile = None
umask = 0
user = None
group = None
keyfile = None
certfile = None

# ⭐ AGREGAR ESTO (importante):
graceful_timeout = 180
