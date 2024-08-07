import pymysql
import logging
from bs4 import BeautifulSoup
import os
import re
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')
DB_NAME_V2 = os.getenv('DB_NAME_V2')


# This was written assuming the scraper will ONLY be scraping data from the specific given website.
# I am well aware that it is not reusable if codebase grows for multi website and needs to be scaled.
def connect_to_db(dbName):
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=dbName,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def save_to_db(rulings):
    logging.info('Saving to database...')
    connection = connect_to_db(DB_NAME)
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

def extract_data_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    laws = []
    articles = []

    logging.info('Extracting data from HTML...')

    law_id = re.search(r'LawID=(\d+)', soup.find('form')['action']).group(1)
    year = int(re.search(r'Year: (\d+)', soup.find(text=re.compile(r'Year: \d+'))).group(1))
    title = soup.find(id='litLaw').get_text(strip=True)
    type_ = soup.find(id='lblType').get_text(strip=True).replace('تعريف النص: ', '')
    number = soup.find(id='lblNumber').get_text(strip=True).replace(' رقم ', '')
    date = soup.find(id='lblDate').get_text(strip=True).replace('تاريخ : ', '')
    oj_number = soup.find(id='divOJNumber').get_text(strip=True).replace('عدد الجريدة الرسمية: ', '')
    oj_publish_date = soup.find(id='divOJPublishDate').get_text(strip=True).replace(' تاريخ النشر: ', '')
    oj_page = soup.find(id='divOJPage').get_text(strip=True).replace(' الصفحة: ', '')

    law = {
        'law_id': law_id,
        'year': year,
        'title': title,
        'type': type_,
        'number': number,
        'date': date,
        'oj_number': oj_number,
        'oj_publish_date': oj_publish_date,
        'oj_page': oj_page
    }
    laws.append(law)

    article_sections = soup.find_all('div', id=re.compile(r'divTreeDetails'))
    for section in article_sections:
        h2_tag = section.find('h2')
        if h2_tag:
            article_number_match = re.search(r'المادة (\d+)', h2_tag.get_text(strip=True))
            if article_number_match:
                article_number = int(article_number_match.group(1))
                content_tag = section.find('div', class_='text-1')
                if content_tag:
                    content = content_tag.get_text(strip=True)
                    article = {
                        'law_id': law_id,
                        'article_number': article_number,
                        'content': content
                    }
                    articles.append(article)
                    logging.info(f'Extracted article {article_number} for law {law_id}.')
                else:
                    logging.warning(f'Could not find content for article {article_number} in {law_id}. Skipping.')

    logging.info(f'Extracted {len(laws)} laws and {len(articles)} articles.')

    return laws, articles

def save_laws_and_articles_to_db(laws, articles):
    connection = connect_to_db(DB_NAME_V2)
    try:
        with connection.cursor() as cursor:
            for law in laws:
                cursor.execute(
                    """
                    INSERT INTO laws (law_id, year, title, type, number, date, oj_number, oj_publish_date, oj_page)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    year=VALUES(year), title=VALUES(title), type=VALUES(type), number=VALUES(number),
                    date=VALUES(date), oj_number=VALUES(oj_number), oj_publish_date=VALUES(oj_publish_date), oj_page=VALUES(oj_page)
                    """,
                    (law['law_id'], law['year'], law['title'], law['type'], law['number'], law['date'],
                     law['oj_number'], law['oj_publish_date'], law['oj_page'])
                )

            for article in articles:
                cursor.execute(
                    """
                    INSERT INTO articles (law_id, article_number, content)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE content=VALUES(content)
                    """,
                    (article['law_id'], article['article_number'], article['content'])
                )

            connection.commit()
            logging.info('Laws and articles saved to database.')
    except Exception as e:
        logging.error(f"Error saving laws and articles to database: {e}")
    finally:
        connection.close()

# Process HTML files in batches for more speed
def extract_data_from_html_and_save(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    logging.info('Extracting data from HTML...')

    law_id = re.search(r'LawID=(\d+)', soup.find('form')['action']).group(1)
    year = int(re.search(r'Year: (\d+)', soup.find(text=re.compile(r'Year: \d+'))).group(1))
    title = soup.find(id='litLaw').get_text(strip=True)
    type_ = soup.find(id='lblType').get_text(strip=True).replace('تعريف النص: ', '')
    number = soup.find(id='lblNumber').get_text(strip=True).replace(' رقم ', '')
    date = soup.find(id='lblDate').get_text(strip=True).replace('تاريخ : ', '')
    oj_number = soup.find(id='divOJNumber').get_text(strip=True).replace('عدد الجريدة الرسمية: ', '')
    oj_publish_date = soup.find(id='divOJPublishDate').get_text(strip=True).replace(' تاريخ النشر: ', '')
    oj_page = soup.find(id='divOJPage').get_text(strip=True).replace(' الصفحة: ', '')

    law = {
        'law_id': law_id,
        'year': year,
        'title': title,
        'type': type_,
        'number': number,
        'date': date,
        'oj_number': oj_number,
        'oj_publish_date': oj_publish_date,
        'oj_page': oj_page
    }

    save_to_db([law])

    article_sections = soup.find_all('div', id=re.compile(r'divTreeDetails'))
    for section in article_sections:
        h2_tag = section.find('h2')
        if h2_tag:
            article_number_match = re.search(r'المادة (\d+)', h2_tag.get_text(strip=True))
            if article_number_match:
                article_number = int(article_number_match.group(1))
                content_tag = section.find('div', class_='text-1')
                if content_tag:
                    content = content_tag.get_text(strip=True)
                    article = {
                        'law_id': law_id,
                        'article_number': article_number,
                        'content': content
                    }
                    save_to_db([article])
                    logging.info(f'Saved article {article_number} for law {law_id}.')
                else:
                    logging.warning(f'Could not find content for article {article_number} in {law_id}. Skipping.')

    logging.info('Finished extracting data from HTML.')

def process_html_files(directory, batch_size=100):
    logging.info(f'Processing HTML files in directory: {directory}')

    for filename in os.listdir(directory):
        if filename.endswith('.html'):
            with open(os.path.join(directory, filename), 'r', encoding='utf-8') as file:
                html_content = file.read()
                extract_data_from_html_and_save(html_content)

    logging.info('Finished processing HTML files.')
