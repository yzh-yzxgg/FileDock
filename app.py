import hashlib
import json
import random
import sqlite3
import uuid
from datetime import datetime

from flask import Flask, request, send_file, render_template
from flask_uploads import UploadSet, ALL, configure_uploads, \
    patch_request_class  # pip install git+https://github.com/riad-azz/flask-uploads

with open('config.json', 'r') as f:
    config = json.load(f)

app = Flask(__name__)
app.secret_key = config['secret_key']
database = config['database']

app.config['UPLOADED_FILEINPUT_DEST'] = config['uploads']['upload_folder']
files = UploadSet('fileInput', ALL)
configure_uploads(app, files)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * config['uploads']['max_content_length']
patch_request_class(app, 32 * 1024 * config['uploads']['max_content_length'])

session = {}
downloads_tasks = {}


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


def get_unix_time():
    return int(datetime.now().timestamp())


def get_user_ip(request):
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For']
    elif request.headers.get('X-Real-Ip'):
        return request.headers['X-Real-Ip']
    else:
        return request.remote_addr


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
        }, 400
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
        }, 200
    else:
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'Invalid username or password'
            }
        }, 404


@app.route('/api/v1/user/logout', methods=['POST'])
def user_logout():
    try:
        session_id = request.headers['X-Session-ID']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request '
            }
        }, 400
    if session_id in session:
        del session[session_id]
        return {
            'code': 200,
            'success': True,
            'data': {
                'message': 'Logged out'
            }
        }, 200
    else:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401


@app.route('/api/v1/user/info', methods=['POST'])
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
        }, 400
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
        }, 200
    else:
        return {
            'code': 404,
            'success': False,
            'data': {
                'message': 'User not found'
            }
        }, 404


@app.route('/api/v1/user/create', methods=['POST'])
def user_create():
    try:
        session_id = request.headers['X-Session-ID']
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
        }, 400
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }, 403
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
        }, 409
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
    }, 201


@app.route('/api/v1/user/list', methods=['GET'])
def user_list():
    try:
        session_id = request.headers['X-Session-ID']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }, 400
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }, 403
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
    return ret, 200


@app.route('/api/v1/user/delete', methods=['POST'])
def user_delete():
    try:
        session_id = request.headers['X-Session-ID']
        uid = request.json['uid']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }, 400
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }, 403
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
        }, 404
    c.execute('DELETE FROM users WHERE uid=?', (uid,))
    conn.commit()
    conn.close()
    return {
        'code': 200,
        'success': True,
        'data': {
            'message': 'User deleted'
        }
    }, 200


@app.route('/api/v1/user/update', methods=['POST'])
def user_update():
    try:
        session_id = request.headers['X-Session-ID']
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
        }, 400
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401
    if not get_group(get_user_group(session_id))['operations']:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }, 403
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
        }, 404
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
    }, 200


@app.route('/api/v1/user/changepass', methods=['POST'])
def user_changepass():
    try:
        session_id = request.headers['X-Session-ID']
        uid = request.json['uid']
        password = request.json['password']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }, 400
    if session_id not in session:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401
    if not get_group(get_user_group(session_id))['operations'] and session[session_id]['uid'] != uid:
        return {
            'code': 403,
            'success': False,
            'data': {
                'message': 'Not allowed'
            }
        }, 403
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
        }, 404
    c.execute('UPDATE users SET password=? WHERE uid=?', (password, uid))
    conn.commit()
    conn.close()
    return {
        'code': 200,
        'success': True,
        'data': {
            'message': 'Password changed'
        }
    }, 200


@app.route('/api/v1/session/verify', methods=['GET'])
def session_verify():
    try:
        session_id = request.headers['X-Session-ID']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }
    if session_id in session:
        return {
            'code': 200,
            'success': True,
            'data': {
                'uid': session[session_id]['uid'],
                'username': session[session_id]['username'],
                'group': get_user_group(session_id)
            }
        }, 200
    else:
        return {
            'code': 401,
            'success': False,
            'data': {
                'message': 'Invalid session ID'
            }
        }, 401


@app.route('/api/v1/files/upload', methods=['POST'])
def files_create():
    try:
        keep_time = request.form['keep_time']
        receive_user = request.form['receive_user']
    except KeyError:
        return {
            'code': 400,
            'success': False,
            'data': {
                'message': 'Invalid request'
            }
        }, 400
    try:
        session_id = request.headers['X-Session-ID']
        if session_id not in session:
            return {
                'code': 401,
                'success': False,
                'data': {
                    'message': 'Invalid session ID'
                }
            }, 401
        uid = session[session_id]['uid']
    except KeyError:
        uid = -1  # Anonymous
    fileuuid = uuid.uuid4().hex
    filename = request.files['fileInput'].filename
    filestorage = files.save(request.files['fileInput'], name=fileuuid)
    conn = sqlite3.connect(database)
    code = random.randint(100000, 999999)
    c = conn.cursor()
    c.execute('SELECT * FROM uploads WHERE code=?', (code,))
    while c.fetchone():
        code = random.randint(100000, 999999)
    c.execute(
        'INSERT INTO uploads (uuid, filename, code, upload_time, keep_time, upload_user, receive_user) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (fileuuid, filename, code, get_unix_time(), keep_time, uid, receive_user))
    conn.commit()
    conn.close()
    return {
        'code': 201,
        'success': True,
        'data': {
            'uuid': fileuuid,
            'filename': filename,
            'code': code,
            'upload_time': get_unix_time(),
            'keep_time': keep_time,
            'upload_user': uid,
            'receive_user': receive_user
        }
    }, 201


@app.route('/favicon.ico')
def favicon():
    return send_file('static/favicon/favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run()
