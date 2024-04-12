import json
import os
import sqlite3
from datetime import datetime

from flask_apscheduler import APScheduler

scheduler = APScheduler()

with open("config.json", "r") as f:
    config = json.load(f)
database = config["database"]


class Config:
    SCHEDULER_API_ENABLED = True

    JOBS = [
        {
            "id": "uploads_timeout",
            "func": "scheduler:uploads_timeout",
            "trigger": "interval",
            "seconds": 10,
        }
    ]


def uploads_timeout():
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM uploads")
    uploads = cursor.fetchall()
    current = int(datetime.now().timestamp())
    for upload in uploads:
        if current - upload[3] > upload[4] and upload[4] != -1:
            # filepath = files.path(upload[1])
            filepath = os.path.join(config["uploads"]["upload_folder"], upload[0])
            if os.path.exists(filepath):
                os.remove(filepath)
            cursor.execute("DELETE FROM uploads WHERE uuid=?", (upload[0],))
            print(f" > Upload {upload[0]} has expired.")
    conn.commit()
