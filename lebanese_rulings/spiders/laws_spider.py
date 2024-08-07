import scrapy
import json
import os
import logging
import threading
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException
from jinja2 import Template

# Load environment variables from .env file
load_dotenv()

# Get URLs and paths from environment variables
AdvancedLawsSearchYearUrl = os.getenv('AdvancedLawsSearchYearUrl')
AdvancedLawDetailsUrl = os.getenv('AdvancedLawDetailsUrl')
AdvancedLawViewUrl = os.getenv('AdvancedLawArticlesUrl')
LawsYearFile = os.getenv('LawsYearFile')

class LawsSpider(scrapy.Spider):
    name = 'laws_spider'
    custom_settings = {
        'FEED_EXPORT_ENCODING': 'utf-8',
    }

    def __init__(self, *args, **kwargs):
        super(LawsSpider, self).__init__(*args, **kwargs)
        self.laws = []
        self.html_file_index = 1
        self.current_file_size = 0
        self.visited_pages = set()
        self.processed_laws = set()
        self.lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=10)  # Adjust the number of workers as needed
        self.file_years = {}

    def start_requests(self):
        with open(LawsYearFile) as f:
            years = json.load(f).get('years', [])
        
        for year in years:
            url = f'{AdvancedLawsSearchYearUrl}{year}&articleNumber=&pageNumber=1&language='
            yield scrapy.Request(url=url, callback=self.parse_year, meta={'year': year, 'page_number': 1}, dont_filter=True, errback=self.errback_httpbin)

    def make_request(self, url, year, page_number):
        return scrapy.Request(url=url, callback=self.parse_year, meta={'year': year, 'page_number': page_number}, dont_filter=True, errback=self.errback_httpbin)

    def parse_year(self, response):
        year = response.meta['year']
        page_number = response.meta.get('page_number', 1)
        current_page_url = response.url

        with self.lock:
            if current_page_url in self.visited_pages:
                return
            self.visited_pages.add(current_page_url)

        # Find the maximum page number
        pagination_links = response.css('ul.pagination a::attr(href)').extract()
        max_page_number = 1
        for link in pagination_links:
            if 'pageNumber=' in link:
                try:
                    page_num = int(link.split('pageNumber=')[1].split('&')[0])
                    if page_num > max_page_number:
                        max_page_number = page_num
                except ValueError:
                    continue

        logging.info(f'Year: {year}, Page Number: {page_number}, Max Page Number: {max_page_number}')

        law_links = response.css('a[href*="Law.aspx?lawId="]::attr(href)').extract()
        if not law_links and page_number == 1:
            return

        futures = [self.executor.submit(self.fetch_law_details, law_link, year) for law_link in law_links]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logging.error(f'Law {future_to_law[future]} generated an exception: {exc}')
        

        if page_number + 1 < max_page_number:
            logging.info(f'Year: {year}, Page Number: {page_number}, Max Page Number: {max_page_number}')
            next_page_number = page_number + 1
            next_page_url = f'{AdvancedLawsSearchYearUrl}{year}&articleNumber=&pageNumber={next_page_number}&language='
            if next_page_number <= max_page_number:
                if next_page_url not in self.visited_pages:
                    yield self.make_request(next_page_url, year, next_page_number)
        else:
            logging.info(f'Reached the last page ({page_number}) for year {year}. Stopping.')


    def fetch_law_details(self, law_link, year):
        law_id = law_link.split('lawId=')[1]
        law_url = f'{AdvancedLawViewUrl}{law_id}'

        try:
            response = requests.get(law_url)
            if response.status_code == 200:
                self.save_law_html(response.content, year, law_id)
            else:
                logging.error(f'Failed to fetch law details for {law_id}: {response.status_code}')
        except RequestException as e:
            logging.error(f'Failed to fetch law details for {law_id}: {str(e)}')

    def save_law_html(self, html_content, year, law_id):
        if not os.path.exists('laws_html'):
            os.makedirs('laws_html')

        with self.lock:
            if law_id in self.processed_laws:
                return
            self.processed_laws.add(law_id)

            law_entry = {
                'year': year,
                'law_id': law_id,
                'html_content': html_content
            }

            current_file_path = f'laws_html/laws_{self.html_file_index}.html'
            file_size = 0

            if os.path.exists(current_file_path):
                with open(current_file_path, 'rb') as f:
                    file_size = len(f.read())

            if file_size + len(html_content) > 10 * 1024 * 1024:  # 10 MB
                self.html_file_index += 1
                current_file_path = f'laws_html/laws_{self.html_file_index}.html'

            if self.html_file_index not in self.file_years:
                self.file_years[self.html_file_index] = set()
            self.file_years[self.html_file_index].add(year)

            with open(current_file_path, 'ab') as f:
                f.write(f'<!-- Year: {law_entry["year"]}, Law ID: {law_entry["law_id"]} -->\n'.encode('utf-8'))
                f.write(law_entry['html_content'])
                f.write(b'\n\n')

    def errback_httpbin(self, failure):
        self.logger.error(repr(failure))

    def close(self, reason):
        logging.info('Spider closing...')
        self.save_as_html_index()
        self.rename_files_by_year()
        self.executor.shutdown(wait=True)

    def save_as_html_index(self):
        index_template = Template("""
        <!DOCTYPE html>
        <html lang="ar">
        <head>
            <meta charset="UTF-8">
            <title>Index of Laws</title>
            <style>
                body { font-family: Arial, sans-serif; direction: rtl; background-color: #f9f9f9; }
                .container { width: 90%; margin: auto; }
                .law-link { margin-bottom: 10px; }
                .law-link a { text-decoration: none; color: #333; }
                #search { margin-bottom: 20px; width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            </style>
            <script>
                function searchLaws() {
                    var input, filter, links, linkDiv, i, txtValue;
                    input = document.getElementById('search');
                    filter = input.value.toLowerCase();
                    links = document.getElementsByClassName('law-link');
                    for (i = 0; i < links.length; i++) {
                        linkDiv = links[i];
                        txtValue = linkDiv.textContent || linkDiv.innerText;
                        if (txtValue.toLowerCase().indexOf(filter) > -1) {
                            linkDiv.style.display = "";
                        } else {
                            linkDiv.style.display = "none";
                        }
                    }
                }
            </script>
        </head>
        <body>
            <div class="container">
                <input type="text" id="search" onkeyup="searchLaws()" placeholder="ابحث عن القوانين..">
                <div id="linksContainer">
                    {% for year in years %}
                    <h3>السنة: {{ year }}</h3>
                    {% for law in laws[year] %}
                    <div class="law-link">
                        <a href="laws_html/laws_{{ law.file_index }}.html#{{ law.law_id }}" target="_blank">قانون {{ law.law_id }} لسنة {{ year }}</a>
                    </div>
                    {% endfor %}
                    {% endfor %}
                </div>
            </div>
        </body>
        </html>
        """)
        laws_by_year = self.organize_laws_by_year()
        html_index = index_template.render(years=sorted(laws_by_year.keys()), laws=laws_by_year)
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_index)
        logging.info('index.html file created.')

    def organize_laws_by_year(self):
        laws_by_year = {}
        for file_index in range(1, self.html_file_index + 1):
            file_path = f'laws_html/laws_{file_index}.html'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        if line.startswith('<!-- Year: '):
                            year = int(line.split('Year: ')[1].split(',')[0])
                            law_id = line.split('Law ID: ')[1].split(' -->')[0]
                            if year not in laws_by_year:
                                laws_by_year[year] = []
                            laws_by_year[year].append({'law_id': law_id, 'file_index': file_index})
        return laws_by_year

    def rename_files_by_year(self):
        for file_index, years in self.file_years.items():
            old_path = f'laws_html/laws_{file_index}.html'
            if os.path.exists(old_path):
                year_range = "_".join(map(str, sorted(years)))
                new_path = f'laws_html/laws_{year_range}_{file_index}.html'
                os.rename(old_path, new_path)
                logging.info(f'Renamed {old_path} to {new_path}')

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())
    process.crawl(LawsSpider)
    process.start()
