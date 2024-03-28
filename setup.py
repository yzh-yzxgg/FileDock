from os import system
import json
import sqlite3
import hashlib
from datetime import datetime

try:
    with open('setup.lock', 'r') as f:
        setup_lock = json.load(f)
    if setup_lock['setup']:
        print(f"Error while initalize setup progress:\nsetup.lock exist. FileDock may be installed at {setup_lock['time']}.\nIf you believe this is an error, please delete setup.lock and continue.")
except:
    # Install dependencies
    dependencies = [
        'flask',
        'git+https://github.com/riad-azz/flask-uploads'
    ]
    print(f"[Step 1] Install {len(dependencies)} dependencies.")
    for depend in dependencies:
        system(f"pip install {depend}")

    # Edit config.json
    print(f"[Step 2] Create config.json")
    config = {
        "secret_key": "ReplaceWithYourSecretKey",
        "database": "database.db",
        "uploads": {
            "upload_folder": "./uploads",
            "max_content_length": 2048
        }
    }
    with open('config.json', 'w') as f:
        json.dump(config, f)
    print("Created config file, please check and edit if you need.")
    input("After editing, press Enter to continue > ")
    with open('config.json', 'r') as f:
        config = json.load(f)

    # Create database
    print(f"[Step 3] Create database.")
    database = config['database']
    sqlite = [
        """create table users
        (
            uid      integer                not null
                constraint users_pk
                    primary key
                constraint users_uniqpk
                    unique,
            username TEXT default 'User'    not null,
            password text                   not null,
            "group"  text default 'default' not null
        );""",
        """create table uploads
        (
            uuid         TEXT               not null
                constraint uploads_pk
                    primary key
                constraint uploads_uniqpk
                    unique,
            filename     TEXT               not null,
            code         integer            not null,
            upload_time  integer            not null,
            keep_time    integer default -1 not null,
            upload_user  integer            not null,
            receive_user integer default null
        );""",
        """create table groups
        (
            name     text                not null
                constraint groups_pk
                    primary key
                constraint groups_uniqpk
                    unique,
            operator integer default 0   not null,
            max_size integer default 512 not null
        );""",
        """INSERT INTO groups (name, operator, max_size)
        VALUES ('default', 0, 512);""",
        """INSERT INTO groups (name, operator, max_size)
        VALUES ('operator', 1, 512);""",
    ]
    conn = sqlite3.connect(database)
    c = conn.cursor()
    for sentence in sqlite:
        c.execute(sentence)
    conn.commit()
    conn.close()
    print(f"Successfully execute {len(sqlite)} queries.")

    # Create default operator
    print(f"[Step 4] Create default operator account.")
    print("This user will have all permissions.")
    username = input("Username > ")
    password = input("Password > ")
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute("""INSERT INTO users (uid, username, password)
    VALUES (0, ?, ?);""", (username,password,))
    conn.commit()
    conn.close()
    print("Successfully registered user with UID 0.")

    # Save setup.lock
    with open('setup.lock', 'w') as f:
        json.dump({
            'setup': True,
            'time': int(datetime.now().timestamp())
        }, f)
    print("\n\nSuccessfully configured FileDock!\nTo run server, use 'flask run' and it'll be run on port 5000.\nFor more information please visit FileDock Wiki and Flask Wensite.")