import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
# Threads keep an idle or slow connection (e.g. a browser preconnect) from tying up a whole
# worker until the timeout. Rate limits are kept per worker process, so fewer processes
# also keep the effective per-IP limit closer to the configured one.
workers = 2
worker_class = "gthread"
threads = 4
timeout = 30
graceful_timeout = 30
keepalive = 5
accesslog = "-"
# %(U)s is the path without the query string, so encoded content stays out of access logs
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)ss'
errorlog = "-"
loglevel = "info"
# The runtime control socket (gunicorn 26+) is not used; don't expose it
control_socket_disable = True
# Heartbeat files live in tmpfs so the container root filesystem can be read-only
worker_tmp_dir = "/dev/shm"
