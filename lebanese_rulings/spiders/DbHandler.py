import pymysql
import logging
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')


# This was written assuming the scraper will ONLY be scraping data from the spicific given website.
# I am well aware that it is not reusable if codebase grows for multi website and needs to be scaled.
def connect_to_db():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def save_to_db(rulings):
    logging.info('Saving to database...')
    connection = connect_to_db()
    try:
        with connection.cursor() as cursor:
            for ruling in rulings:
                cursor.execute(
                    "INSERT INTO courts (court_name) VALUES (%s) ON DUPLICATE KEY UPDATE court_id=LAST_INSERT_ID(court_id)",
                    (ruling['court'],)
                )
                court_id = cursor.lastrowid

                if ruling['president']:
                    cursor.execute(
                        "INSERT INTO judges (judge_name) VALUES (%s) ON DUPLICATE KEY UPDATE judge_id=LAST_INSERT_ID(judge_id)",
                        (ruling['president'],)
                    )
                    president_id = cursor.lastrowid
                else:
                    president_id = None

                cursor.execute(
                    "INSERT INTO rulings (court_id, ruling_number, year, date, president_id, full_text) VALUES (%s, %s, %s, %s, %s, %s)",
                    (court_id, ruling['number'], ruling['year'], ruling['date'], president_id, ruling['full_text'])
                )
                ruling_id = cursor.lastrowid

                if ruling['members']:
                    members = ruling['members'].split('/')
                    for member in members:
                        member_name = member.strip()
                        if member_name:
                            cursor.execute(
                                "INSERT INTO judges (judge_name) VALUES (%s) ON DUPLICATE KEY UPDATE judge_id=LAST_INSERT_ID(judge_id)",
                                (member_name,)
                            )
                            member_id = cursor.lastrowid
                            cursor.execute(
                                "INSERT INTO ruling_members (ruling_id, judge_id, role) VALUES (%s, %s, %s)",
                                (ruling_id, member_id, 'member')
                            )

            connection.commit()
            logging.info('Saved to database. (ATTENTION: Data saved to Db IS NOT sorted nor filtered.)')
    except Exception as e:
        logging.error(f"Error saving to database: {e}")
    finally:
        connection.close()
