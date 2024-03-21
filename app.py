import hashlib
import os
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, render_template, request, send_file

app = Flask(__name__)

database = "database.db"

session = {}


def get_unix_time():
    return datetime.now().timestamp()


def get_user_group(session_id):
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE uid=?', (session[session_id]['uid'],))
    user = c.fetchone()
    group = user[3]
    conn.close()
    return group


def get_group(group):
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM groups WHERE name=?', (group,))
    group = c.fetchone()
    conn.close()
    if group:
        return {
            'name': group[0],
            'operations': True if group[1] == 1 else False,
            'max_size:': group[2]
        }


@app.route('/api/v1/user/info', methods=['GET'])
def user_info():
    try:
        username = request.json['uid']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE uid=?', (username,))
    user = c.fetchone()
    conn.close()
    if user:
        return {
            'code': 200,
            'success': True,
            'data': {
                'uid': user[0],
                'username': user[1],
                'group': user[3],
            }
        }
    else:
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'User not found'
            }
        }


@app.route('/api/v1/user/login', methods=['POST'])
def user_login():
    try:
        username = request.json['username']
        password = request.json['password']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        session_id = uuid.uuid4().hex
        session[session_id] = {
            'uid': user[0],
            'username': user[1],
            'login_time': datetime.now().timestamp()
        }
        return {
            'code': 200,
            'success': True,
            'data': {
                'session_id': session_id,
                'uid': user[0],
                'username': user[1],
                'group': user[3]
            }
        }
    else:
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'Invalid username or password'
            }
        }


@app.route('/api/v1/user/logout', methods=['POST'])
def user_logout():
    try:
        session_id = request.json['session_id']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request '
            }
        }
    if session_id in session:
        del session[session_id]
        return {
            'code': 200,
            'success': True,
            'data': {
                'message': 'Logged out'
            }
        }
    else:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }


@app.route('/api/v1/user/create', methods=['POST'])
def user_create():
    try:
        session_id = request.json['session_id']
        username = request.json['userdata']['username']
        password = request.json['userdata']['password']
        group = request.json['userdata']['group']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username=?', (username,))
    if c.fetchone():
        return {
            'code': 409,
            'success': False,
            'data': {
                'message': 'Username already exists'
            }
        }
    new_uid = c.execute('SELECT MAX(uid) FROM users').fetchone()[0] + 1
    c.execute('INSERT INTO users (uid, username, password, "group") VALUES (?, ?, ?, ?)',
              (new_uid, username, password, group))
    conn.commit()
    conn.close()
    return {
        'code': 201,
        'success': True,
        'data': {
            'uid': new_uid,
            'username': username,
            'group': group
        }
    }


@app.route('/api/v1/user/delete', methods=['POST'])
def user_delete():
    try:
        session_id = request.json['session_id']
        uid = request.json['uid']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE uid=?', (uid,))
    if not c.fetchone():
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'User not found'
            }
        }
    c.execute('DELETE FROM users WHERE uid=?', (uid,))
    conn.commit()
    conn.close()
    return {
        'code': 200,
        'success': True,
        'data': {
            'message': 'User deleted'
        }
    }

@app.route('/api/v1/user/list', methods=['GET'])
def user_list():
    try:
        session_id = request.json['session_id']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users')
    users = c.fetchall()
    conn.close()
    ret = {
        'code': 200,
        'success': True,
        'data': {
            'users': []
        }
    }
    for user in users:
        ret['data']['users'].append({
            'uid': user[0],
            'username': user[1],
            'group': user[3]
        })
    return ret

@app.route('/api/v1/user/update', methods=['POST'])
def user_update():
    try:
        session_id = request.json['session_id']
        uid = request.json['uid']
        username = request.json['userdata']['username']
        group = request.json['userdata']['group']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE uid=?', (uid,))
    if not c.fetchone():
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'User not found'
            }
        }
    c.execute('UPDATE users SET username=? WHERE uid=?', (username, uid))
    c.execute('UPDATE users SET "group"=? WHERE uid=?', (group, uid))
    conn.commit()
    conn.close()
    return {
        'code': 200,
        'success': True,
        'data': {
            'message': 'User updated'
        }
    }

@app.route('/api/v1/user/changepass', methods=['POST'])
def user_changepass():
    try:
        session_id = request.json['session_id']
        uid = request.json['uid']
        password = request.json['password']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }
    if not get_group(get_user_group(session_id))['operations'] and session[session_id]['uid'] != uid:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE uid=?', (uid,))
    if not c.fetchone():
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'User not found'
            }
        }
    c.execute('UPDATE users SET password=? WHERE uid=?', (password, uid))
    conn.commit()
    conn.close()
    return {
        'code': 200,
        'success': True,
        'data': {
            'message': 'Password changed'
        }
    }

@app.route('/api/v1/upload', methods=['POST'])
def upload():
    uploaded_file = request.files['file']
    filename = uploaded_file.filename
    file_ext = os.path.splitext(filename)[1]
    if file_ext != '.php':
        return 'File not allowed', 400

    uuid_filename = uuid.uuid4().hex + file_ext
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute('INSERT INTO uploads (filename, uuid_filename, uploaded_time) VALUES (?, ?)',
              (filename, uuid_filename, get_unix_time()))
    conn.commit()
    conn.close()
    uploaded_file.save('uploads/' + uuid_filename)

@app.route('/favicon.ico')
def favicon():
    return send_file('static/favicon/favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/')
def index():
    return render_template('index.html')
