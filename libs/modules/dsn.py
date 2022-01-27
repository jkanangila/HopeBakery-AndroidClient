import os
from dotenv import load_dotenv, find_dotenv


load_dotenv(find_dotenv())

dsn = f"host={os.getenv('DB_HOST')} dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} password={os.getenv('DB_PASSWORD')}"