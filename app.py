import hashlib
import json
import os
import random
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, request, send_file, render_template
from flask_apscheduler import APScheduler
from flask_uploads import (
    UploadSet,
    ALL,
    configure_uploads,
    patch_request_class,
)  # pip install git+https://github.com/riad-azz/flask-uploads

import geetest
import scheduler

with open("config.json", "r") as f:
    config = json.load(f)

app = Flask(__name__)
app.secret_key = config["secret_key"]
database = config["database"]

app.config["UPLOADED_FILEINPUT_DEST"] = config["uploads"]["upload_folder"]
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * config["uploads"]["max_content_length"]
files = UploadSet("fileInput", ALL)
configure_uploads(app, files)
patch_request_class(app, 32 * 1024 * config["uploads"]["max_content_length"])

session = {}
downloads_tasks = {}


def get_user_group(session_id):
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (session[session_id]["uid"],))
    user = c.fetchone()
    group = user[3]
    conn.close()
    return group


def get_group(group):
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM groups WHERE name=?", (group,))
    group = c.fetchone()
    conn.close()
    if group:
        return {
            "name": group[0],
            "operations": True if group[1] == 1 else False,
            "max_size:": group[2],
        }


def get_unix_time():
    return int(datetime.now().timestamp())


def get_user_ip(request):
    if request.headers.get("X-Forwarded-For"):
        return request.headers["X-Forwarded-For"]
    elif request.headers.get("X-Real-Ip"):
        return request.headers["X-Real-Ip"]
    else:
        return request.remote_addr


@app.route("/api/v1/user/login", methods=["POST"])
def user_login():
    try:
        username = request.json["username"]
        password = request.json["password"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute(
        "SELECT * FROM users WHERE username=? AND password=?", (username, password)
    )
    user = c.fetchone()
    conn.close()
    if user:
        session_id = uuid.uuid4().hex
        session[session_id] = {
            "uid": user[0],
            "username": user[1],
            "login_time": datetime.now().timestamp(),
        }
        return {
            "code": 200,
            "success": True,
            "data": {
                "session_id": session_id,
                "uid": user[0],
                "username": user[1],
                "group": user[3],
            },
        }
    else:
        return {
            "code": 404,
            "success": False,
            "data": {"message": "Invalid username or password"},
        }


@app.route("/api/v1/user/logout", methods=["POST"])
def user_logout():
    try:
        session_id = request.headers["X-Session-ID"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request "},
        }
    if session_id in session:
        del session[session_id]
        return {"code": 200, "success": True, "data": {"message": "Logged out"}}
    else:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }


@app.route("/api/v1/user/info", methods=["POST"])
def user_info():
    try:
        username = request.json["uid"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (username,))
    user = c.fetchone()
    conn.close()
    if user:
        return {
            "code": 200,
            "success": True,
            "data": {
                "uid": user[0],
                "username": user[1],
                "group": user[3],
            },
        }
    else:
        return {
            "code": 404,
            "success": False,
            "data": {"message": "User not found"},
        }


@app.route("/api/v1/user/create", methods=["POST"])
def user_create():
    try:
        session_id = request.headers["X-Session-ID"]
        username = request.json["userdata"]["username"]
        password = request.json["userdata"]["password"]
        group = request.json["userdata"]["group"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    if not get_group(get_user_group(session_id))["operations"]:
        return {"code": 403, "success": False, "data": {"message": "Not allowed"}}
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    if c.fetchone():
        return {
            "code": 409,
            "success": False,
            "data": {"message": "Username already exists"},
        }
    new_uid = c.execute("SELECT MAX(uid) FROM users").fetchone()[0] + 1
    c.execute(
        'INSERT INTO users (uid, username, password, "group") VALUES (?, ?, ?, ?)',
        (new_uid, username, password, group),
    )
    conn.commit()
    conn.close()
    return {
        "code": 201,
        "success": True,
        "data": {"uid": new_uid, "username": username, "group": group},
    }


@app.route("/api/v1/user/list", methods=["GET"])
def user_list():
    try:
        session_id = request.headers["X-Session-ID"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    if not get_group(get_user_group(session_id))["operations"]:
        return {"code": 403, "success": False, "data": {"message": "Not allowed"}}
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()
    ret = {"code": 200, "success": True, "data": {"users": []}}
    for user in users:
        ret["data"]["users"].append(
            {"uid": user[0], "username": user[1], "group": user[3]}
        )
    return ret, 200


@app.route("/api/v1/user/delete", methods=["POST"])
def user_delete():
    try:
        session_id = request.headers["X-Session-ID"]
        uid = request.json["uid"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    if not get_group(get_user_group(session_id))["operations"]:
        return {"code": 403, "success": False, "data": {"message": "Not allowed"}}
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (uid,))
    if not c.fetchone():
        return {
            "code": 404,
            "success": False,
            "data": {"message": "User not found"},
        }
    c.execute("DELETE FROM users WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    return {"code": 200, "success": True, "data": {"message": "User deleted"}}


@app.route("/api/v1/user/update", methods=["POST"])
def user_update():
    try:
        session_id = request.headers["X-Session-ID"]
        uid = request.json["uid"]
        username = request.json["userdata"]["username"]
        group = request.json["userdata"]["group"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    if not get_group(get_user_group(session_id))["operations"]:
        return {"code": 403, "success": False, "data": {"message": "Not allowed"}}
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (uid,))
    if not c.fetchone():
        return {
            "code": 404,
            "success": False,
            "data": {"message": "User not found"},
        }
    c.execute("UPDATE users SET username=? WHERE uid=?", (username, uid))
    c.execute('UPDATE users SET "group"=? WHERE uid=?', (group, uid))
    conn.commit()
    conn.close()
    return {"code": 200, "success": True, "data": {"message": "User updated"}}


@app.route("/api/v1/user/changepass", methods=["POST"])
def user_changepass():
    try:
        session_id = request.headers["X-Session-ID"]
        uid = request.json["uid"]
        password = request.json["password"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    if (
        not get_group(get_user_group(session_id))["operations"]
        and session[session_id]["uid"] != uid
    ):
        return {"code": 403, "success": False, "data": {"message": "Not allowed"}}
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE uid=?", (uid,))
    if not c.fetchone():
        return {
            "code": 404,
            "success": False,
            "data": {"message": "User not found"},
        }
    c.execute("UPDATE users SET password=? WHERE uid=?", (password, uid))
    conn.commit()
    conn.close()
    return {"code": 200, "success": True, "data": {"message": "Password changed"}}


@app.route("/api/v1/session/verify", methods=["GET"])
def session_verify():
    try:
        session_id = request.headers["X-Session-ID"]
    except KeyError:
        return {"code": 400, "success": False, "data": {"message": "Invalid request"}}
    if session_id in session:
        return {
            "code": 200,
            "success": True,
            "data": {
                "uid": session[session_id]["uid"],
                "username": session[session_id]["username"],
                "group": get_user_group(session_id),
            },
        }
    else:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }


@app.route("/api/v1/files/upload", methods=["POST"])
def files_create():
    try:
        keep_time = request.form["keep_time"]
        receive_user = request.form["receive_user"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    try:
        session_id = request.headers["X-Session-ID"]
        if session_id not in session:
            return {
                "code": 401,
                "success": False,
                "data": {"message": "Invalid session ID"},
            }
        uid = session[session_id]["uid"]
    except KeyError:
        uid = -1  # Anonymous
    fileuuid = uuid.uuid4().hex
    filename = request.files["fileInput"].filename
    filestorage = files.save(request.files["fileInput"], name=fileuuid)
    conn = sqlite3.connect(database)
    code = random.randint(100000, 999999)
    c = conn.cursor()
    c.execute("SELECT * FROM uploads WHERE code=?", (code,))
    while c.fetchone():
        code = random.randint(100000, 999999)
    c.execute(
        "INSERT INTO uploads (uuid, filename, code, upload_time, keep_time, upload_user, shareport) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (fileuuid, filename, code, get_unix_time(), keep_time, uid, receive_user),
    )
    conn.commit()
    conn.close()
    return {
        "code": 201,
        "success": True,
        "data": {
            "uuid": fileuuid,
            "filename": filename,
            "code": code,
            "upload_time": get_unix_time(),
            "keep_time": keep_time,
            "upload_user": uid,
            "receive_user": receive_user,
        },
    }


@app.route("/api/v1/files/get", methods=["POST"])
def files_download():
    try:
        code = request.json["code"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    try:
        session_id = request.headers["X-Session-ID"]
        if session_id in session:
            reqiure_captcha = False
        else:
            reqiure_captcha = True
    except KeyError:
        reqiure_captcha = True
    if reqiure_captcha:
        try:
            captcha = request.json["captcha"]
            result = geetest.verify_test(
                lot_number=captcha["lot_number"],
                captcha_output=captcha["captcha_output"],
                pass_token=captcha["pass_token"],
                gen_time=captcha["gen_time"],
            )
            if result["result"] != "success":
                return {
                    "code": 403,
                    "success": False,
                    "data": {"message": captcha["reason"]},
                }
        except KeyError:
            return {
                "code": 400,
                "success": False,
                "data": {"message": "Invalid request"},
            }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM uploads WHERE code=?", (code,))
    file = c.fetchone()
    conn.close()
    if not file:
        return {
            "code": 404,
            "success": False,
            "data": {"message": "File not found"},
        }
    filename = file[1]
    task_uuid = uuid.uuid4().hex
    downloads_tasks[task_uuid] = {
        "uuid": file[0],
        "filename": filename,
        "code": code,
        "download_time": get_unix_time(),
        "download_user": get_user_ip(request),
    }
    return {
        "code": 200,
        "success": True,
        "data": {
            "task_uuid": task_uuid,
            "filemeta": {
                "uuid": file[0],
                "filename": file[1],
                "code": file[2],
                "upload_time": file[3],
                "keep_time": file[4],
                "upload_user": file[5],
                "receive_user": file[6],
            },
        },
    }


@app.route("/api/v1/files/download", methods=["GET"])
def files_download_task():
    try:
        task_uuid = request.args["task_uuid"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if task_uuid not in downloads_tasks:
        return {
            "code": 404,
            "success": False,
            "data": {"message": "Task not found"},
        }
    file = downloads_tasks[task_uuid]
    if get_unix_time() - file["download_time"] > config["downloads"]["session_timeout"]:
        del downloads_tasks[task_uuid]
        return {
            "code": 408,
            "success": False,
            "data": {"message": "Download session has timed out, please try again."},
        }
    return send_file(
        "uploads/" + file["uuid"], as_attachment=True, download_name=file["filename"]
    )


@app.route("/api/v1/files/list", methods=["POST"])
def files_list():
    try:
        session_id = request.headers["X-Session-ID"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    uid = session[session_id]["uid"]
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM uploads WHERE upload_user=?", (uid,))
    files = c.fetchall()
    conn.close()
    ret = {"code": 200, "success": True, "data": {"files": []}}
    for file in files:
        ret["data"]["files"].append(
            {
                "uuid": file[0],
                "filename": file[1],
                "code": file[2],
                "upload_time": file[3],
                "keep_time": file[4],
                "upload_user": file[5],
                "receive_user": file[6],
            }
        )
    return ret, 200


@app.route("/api/v1/files/delete", methods=["POST"])
def files_delete():
    try:
        session_id = request.headers["X-Session-ID"]
        uuid = request.json["uuid"]
    except KeyError:
        return {
            "code": 400,
            "success": False,
            "data": {"message": "Invalid request"},
        }
    if session_id not in session:
        return {
            "code": 401,
            "success": False,
            "data": {"message": "Invalid session ID"},
        }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("SELECT * FROM uploads WHERE uuid=?", (uuid,))
    file = c.fetchone()
    if not file:
        return {
            "code": 404,
            "success": False,
            "data": {"message": "File not found"},
        }
    if session[session_id]["uid"] != file[5]:
        return {"code": 403, "success": False, "data": {"message": "Not allowed"}}
    filepath = os.path.join(config["uploads"]["upload_folder"], file[0])
    if os.path.exists(filepath):
        os.remove(filepath)
    c.execute("DELETE FROM uploads WHERE uuid=?", (uuid,))
    conn.commit()
    conn.close()
    return {"code": 200, "success": True, "data": {"message": "File deleted"}}


@app.route("/favicon.ico")
def favicon():
    return send_file("static/favicon/favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/")
def index():
    return render_template("index.html")


app.config.from_object(scheduler.Config())

crontab = APScheduler()
crontab.init_app(app)
crontab.start()

scheduler.uploads_timeout()

if __name__ == "__main__":
    app.run()
