from flask import Flask, render_template, request
import uuid
import os
import sqlite3

app = Flask(__name__)

database = "database.db"

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
    c.execute('INSERT INTO uploads (filename) VALUES (?)', (uuid_filename,))
    c.commit()
    conn.close()
    uploaded_file.save('uploads/' + uuid_filename)

@app.route('/')
def index():
    return render_template('index.html')