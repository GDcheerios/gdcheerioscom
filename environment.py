from PSQLConnector.connector import PSQLConnection as Database
from utils.printy import *

print_start("loading environment variables...")
import os
from dotenv import load_dotenv

load_dotenv()
print_end()

print_start("setting main variables")
# main variables
domain = os.environ['DOMAIN']
port = os.environ['PORT']  # the port
secret = os.environ['SECRET']
is_production = int(os.environ['IS_PRODUCTION']) == 1
debug = not is_production  # debugging?
smtp_host = os.environ['SMTP_HOST']
smtp_email = os.environ['SMTP_EMAIL']
smtp_password = os.environ['SMTP_PASSWORD']
bucket_path = os.environ['BUCKET_PATH']
print_end()

print_start("setting gq variables")
# Gentry's Quest
from GPSystem import GPSystem
import math

gq_rater = GPSystem().rater
gq_version = "V"
gq_levels = []

for level in range(100):
    level += 1
    xp = (level * 10000) * math.exp(level * 0.1)
    gq_levels.append(xp)

for level in range(400):
    level += 1
    xp = gq_levels[99] + (2854810277 * level)
    gq_levels.append(xp)

gq_levels[0] = 10000

print_end()

print_start("allocating instance variables")
# instance variables
bcrypt = None  # the instance of bcrypt
socket = None  # the instance of socketio
print_end()

print_start("setting db variables")
# DB
db_user = os.environ['DB_USER']
db_password = os.environ['DB_PASSWORD']
db_hostname = os.environ['DB_HOSTNAME']
db_port = 5432
db = os.environ['DB']
print_end()

print_start("setting osu variables")
# osu
osu_secret = os.environ['OSU_SECRET']
osu_api_key = os.environ['OSU_API_KEY']
osu_client_id = os.environ['CLIENT_ID']
print_end()

print_start("loading database")
database = Database
database.connect(
    db_user,
    db_password,
    db_hostname,
    db
)
print_end()
