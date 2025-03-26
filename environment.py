from PSQLConnector.connector import PSQLConnection as Database
from GPSystem import GPSystem

print("loading environment variables...")
import os
from dotenv import load_dotenv

load_dotenv()
print("loaded environment variables")

print("setting main variables")
# main variables
domain = os.environ['DOMAIN']
port = os.environ['PORT']  # the port
secret = os.environ['SECRET']
is_production = os.environ['IS_PRODUCTION'] == 1
debug = not is_production  # debugging?

# Gentry's Quest
gq_rater = GPSystem().rater
gq_version = "V"

# instance variables
bcrypt = None  # the instance of bcrypt
socket = None  # the instance of socketio

# DB
db_user = os.environ['DB_USER']
db_password = os.environ['DB_PASSWORD']
db_hostname = os.environ['DB_HOSTNAME']
db_port = 5432
db = os.environ['DB']

# osu
osu_secret = os.environ['OSU_SECRET']
osu_api_key = os.environ['OSU_API_KEY']
osu_client_id = os.environ['CLIENT_ID']

print("loading database")

database = Database
database.connect(
    db_user,
    db_password,
    db_hostname,
    db
)
