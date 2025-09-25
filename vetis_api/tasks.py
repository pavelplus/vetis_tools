from celery import Celery

app = Celery('tasks', broker='pyamqp://guest@192.168.101.242//')

@app.task
def add(x, y):
    return x + y