import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
workers = 4
worker_class = "sync"
timeout = 30
graceful_timeout = 30
keepalive = 5
accesslog = "-"
# %(U)s is the path without the query string, so encoded content stays out of access logs
access_log_format = '%(h)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s %(L)ss'
errorlog = "-"
loglevel = "info"
