from PSQLConnector.connector import PSQLConnection as Database
from utils.printy import *
import os
from dotenv import load_dotenv
from GPSystem import GPSystem
import math
import datetime as dt

# region Importing Environment Variables
print_start("Importing Environment Variables")
load_dotenv()
domain = os.environ['DOMAIN']
port = os.environ['PORT']  # the port
secret = os.environ['SECRET']
is_production = int(os.environ['IS_PRODUCTION']) == 1
debug = not is_production  # debugging?

smtp_host = os.environ['SMTP_HOST']
smtp_email = os.environ['SMTP_EMAIL']
smtp_password = os.environ['SMTP_PASSWORD']

bucket_path = os.environ['BUCKET_PATH']

db_user = os.environ['DB_USER']
db_password = os.environ['DB_PASSWORD']
db_hostname = os.environ['DB_HOSTNAME']
db_port = 5432
db = os.environ['DB']

osu_secret = os.environ['OSU_SECRET']
osu_api_key = os.environ['OSU_API_KEY']
osu_client_id = os.environ['CLIENT_ID']

stripe_public_key = os.environ['STRIPE_PUBLIC_KEY']
stripe_secret_key = os.environ['STRIPE_SECRET_KEY']
stripe_webhook_secret = os.environ['STRIPE_WEBHOOK_SECRET']
print_end()
# endregion

# region Loading Gentry's Quest
print_start("Loading Gentry's Quest")
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
gq_level_colors = [

    [1, "#444444", "#2e2e2e"],
    [10, "#9c1b1b", "#5f1010"],
    [20, "#c45f14", "#7a3a0d"],
    [40, "#d89a16", "#8e6610"],
    [50, "#4fa828", "#2f6819"],
    [60, "#00a6cc", "#006d85"],
    [70, "#3550ff", "#222f9c"],
    [75, "#7b2bff", "#4b1a9e"],
    [80, "#c22bff", "#78199e"],
    [85, "#ff2ba8", "#9e1a68"],
    [90, "#ff4088", "#c22f64"],
    [91, "#ff5079", "#c23a58"],
    [92, "#ff606a", "#c2444c"],
    [93, "#ff705b", "#c24e40"],
    [94, "#ff814c", "#c25834"],
    [95, "#ff923d", "#c26228"],
    [96, "#ffa32e", "#c26c1c"],
    [97, "#ffb41f", "#c27610"],
    [98, "#ffc510", "#c28004"],
    [99, "#ffd602", "#c28a00"],
    [100, "#fff200", "#ffb900"],
]

print_end()
# endregion

# region Allocating Global Variables
print_start("Allocating Global Variables")
bcrypt = None  # the instance of bcrypt
socket = None  # the instance of socketio
database = Database  # the instance of the database
print_end()
# endregion

# region Connecting to Database
print_start("Connecting to Database")
database.connect(
    db_user,
    db_password,
    db_hostname,
    db
)
print_end()
# endregion

# region Cleaning Up Database
print_start("Cleaning Up Database")
now = dt.datetime.now(tz=dt.timezone.utc)
Database.execute(
    """
    DELETE
    FROM api_keys
    WHERE expires_at < %s
        AND expires_at IS NOT NULL
    """,
    params=(now,)
)
print_end()
# endregion

# region Payment Setup
print_start("Payment Setup")
weekly_cost = 100  # cents
print_end()
# endregion
