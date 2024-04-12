import hashlib
import importlib
import json
import sqlite3
from datetime import datetime
from os import system

config_version = 4
config = {
    "secret_key": "ReplaceWithYourSecretKey",
    "database": "database.db",
    "uploads": {"upload_folder": "./uploads", "max_content_length": 2048},
    "downloads": {
        "session_timeout": 3600,
    },
    "geetest": {
        "enable": False,
        "captcha_id": "ReplaceWithYourCaptchaID",
        "captcha_key": "ReplaceWithYourCaptchaKey",
        "api_server": "http://gcaptcha4.geetest.com",
    },
}
database_version = 2
database = ""


def install_dependencies():
    dependencies = {
        "flask": "flask",
        "flask_uploads": "git+https://github.com/riad-azz/flask-uploads",
        "flask_apscheduler": "flask-apscheduler",
    }
    for key, value in dependencies.items():
        try:
            importlib.import_module(key)
            print(f"{key} already installed.")
        except ImportError:
            print(f"Installing {key}...")
            system(f"pip install {value}")


def create_config():
    global config
    with open("config.json", "w") as f:
        json.dump(config, f)
    print("Created config file, please check and edit if you need.")
    input("After editing, press Enter to continue > ")
    with open("config.json", "r") as f:
        config = json.load(f)


def create_database():
    global database
    database = config["database"]
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
        shreport     TEXT default null
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


def create_default_user():
    print("This user will have all permissions.")
    username = input("Username > ")
    password = input("Password > ")
    group = "operator"
    password = hashlib.sha256(password.encode()).hexdigest()
    conn = sqlite3.connect(database)
    c = conn.cursor()
    c.execute(
        """INSERT INTO users (uid, username, password, "group")
    VALUES (0, ?, ?, ?);""",
        (username, password, group),
    )
    conn.commit()
    conn.close()
    print("Successfully registered user with UID 0.")


def migrate_config():
    global config
    with open("config.json", "r") as f:
        old_config = json.load(f)
    for key, value in config.items():
        if key not in old_config:
            old_config[key] = value
    with open("config.json", "w") as f:
        json.dump(old_config, f)
    config = old_config
    print(
        f"Your config.json version is {config_version}, but setup.lock is {setup_lock['config_version']}. We've tried to update your config.json, please check and edit if you need."
    )


def migrate_database(low, high):
    migrate_query = [
        [
            """
        create table uploads_dg_tmp
        (
            uuid        TEXT               not null
                constraint uploads_pk
                    primary key
                constraint uploads_uniqpk
                    unique,
            filename    TEXT               not null,
            code        integer            not null,
            upload_time integer            not null,
            keep_time   integer default -1 not null,
            upload_user integer            not null,
            shareport   text    default null
        );""",
            """insert into uploads_dg_tmp(uuid, filename, code, upload_time, keep_time, upload_user, shareport)
        select uuid, filename, code, upload_time, keep_time, upload_user, receive_user
        from uploads;
        """,
            "drop table uploads;",
            """alter table uploads_dg_tmp
            rename to uploads;
        """,
        ]
    ]
    for i in range(low, high):
        print(f"Migrate database from version {i} to {i+1}...")
        conn = sqlite3.connect(database)
        c = conn.cursor()
        for query in migrate_query[i - 1]:
            c.execute(query)
        conn.commit()
        conn.close()
    print(f"Successfully migrate database from version {low} to {high}.")


scripts_list = []

try:
    with open("setup.lock", "r") as f:
        setup_lock = json.load(f)
    if setup_lock["setup"]:
        setup_time = datetime.fromtimestamp(setup_lock["time"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        print(
            f"setup.lock exist. FileDock may be installed at {setup_time}.\nTry to check for update instead."
        )
        if config_version != setup_lock["config_version"]:
            scripts_list.append("migrate_config()")
        database = config["database"]
        if database_version != setup_lock["database_version"]:
            scripts_list.append(
                "migrate_database("
                + str(setup_lock["database_version"])
                + ","
                + str(database_version)
                + ")"
            )
except FileNotFoundError:
    scripts_list.append("install_dependencies()")
    scripts_list.append("create_config()")
    scripts_list.append("create_database()")
    scripts_list.append("create_default_user()")


if len(scripts_list) == 0:
    print("\nEverything up to date.")
    exit(0)
for func in scripts_list:
    print(f"\n> Running script {func}...")
    eval(func)
with open("setup.lock", "w") as f:
    json.dump(
        {
            "setup": True,
            "time": int(datetime.now().timestamp()),
            "config_version": config_version,
            "database_version": database_version,
        },
        f,
    )
print(
    "\n\nSuccessfully configured FileDock!\nTo run server, use 'flask run' and it'll be run on port 5000.\nFor more information please visit FileDock Wiki and Flask Website."
)
