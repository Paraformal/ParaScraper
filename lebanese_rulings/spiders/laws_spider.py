import scrapy
import json
import os
import logging
from jinja2 import Template
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException

# Load environment variables from .env file
load_dotenv()

# Get URLs and paths from environment variables
AdvancedLawsSearchYearUrl = os.getenv('AdvancedLawsSearchYearUrl')
AdvancedLawDetailsUrl = os.getenv('AdvancedLawDetailsUrl')
AdvancedLawArticlesUrl = os.getenv('AdvancedLawArticlesUrl')
LawsYearFile = os.getenv('LawsYearFile')

class LawsSpider(scrapy.Spider):
    name = 'laws_spider'
    custom_settings = {
        'FEED_EXPORT_ENCODING': 'utf-8',
    }

    def __init__(self, *args, **kwargs):
        super(LawsSpider, self).__init__(*args, **kwargs)
        self.laws = []

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

        law_links = response.css('a[href*="Law.aspx?lawId="]::attr(href)').extract()
        if not law_links and page_number == 1:
            return

        with ThreadPoolExecutor(max_workers=10) as executor:  # Adjust the number of workers as needed
            future_to_law = {executor.submit(self.fetch_law_details, law_link, year): law_link for law_link in law_links}
            for future in as_completed(future_to_law):
                try:
                    future.result()
                except Exception as exc:
                    logging.error(f'Law {future_to_law[future]} generated an exception: {exc}')

        next_page_number = page_number + 1
        next_page = response.css(f'a[href*="pageNumber={next_page_number}"]::attr(href)').get()
        if next_page:
            next_page_url = f'{AdvancedLawsSearchYearUrl}{year}&articleNumber=&pageNumber={next_page_number}&language='
            yield self.make_request(next_page_url, year, next_page_number)

    def fetch_law_details(self, law_link, year):
        law_id = law_link.split('lawId=')[1]
        law_url = f'{AdvancedLawDetailsUrl}{law_id}'

        try:
            response = requests.get(law_url)
            if response.status_code == 200:
                self.parse_law_details(response.text, year, law_id)
            else:
                logging.error(f'Failed to fetch law details for {law_id}: {response.status_code}')
        except RequestException as e:
            logging.error(f'Failed to fetch law details for {law_id}: {str(e)}')

    def parse_law_details(self, response_text, year, law_id):
        response = scrapy.Selector(text=response_text)

        subdetails = response.css('#MainContent_subdetails::text').get()
        publish_date = response.css('#MainContent_divOJPublishDate::text').get()
        page_number = response.css('#MainContent_divOJPage::text').get()
        notes = response.css('#MainContent_divNotes span::text').getall()
        notes_text = ' '.join(notes).strip()

        law_tree_section_id = response.css('a[href*="LawTreeSectionID="]::attr(href)').re_first(r'LawTreeSectionID=(\d+)')

        law_details = {
            'year': year,
            'law_id': law_id,
            'subdetails': subdetails,
            'publish_date': publish_date,
            'page_number': page_number,
            'notes': notes_text,
            'articles': []
        }

        if law_tree_section_id:
            articles_url = f'{AdvancedLawArticlesUrl}{law_tree_section_id}&LawID={law_id}&language=ar'
            try:
                response = requests.get(articles_url)
                if response.status_code == 200:
                    law_details['articles'] = self.parse_articles(response.text)
            except RequestException as e:
                logging.error(f'Failed to fetch articles for law {law_id}: {str(e)}')

        self.laws.append(law_details)

    def parse_articles(self, response_text):
        response = scrapy.Selector(text=response_text)
        return response.css('td.ArticleText').getall()

    def errback_httpbin(self, failure):
        self.logger.error(repr(failure))

    def close(self, reason):
        logging.info('Spider closing...')
        with open('laws.json', 'w', encoding='utf-8') as f:
            json.dump(self.laws, f, ensure_ascii=False, indent=4)
        logging.info('laws.json file created.')
        self.save_as_html()

    def save_as_html(self):
        laws_by_year = self.organize_laws_by_year()
        self.write_html_files(laws_by_year)

    def organize_laws_by_year(self):
        laws_by_year = {}
        for law in self.laws:
            year = law['year']
            if year not in laws_by_year:
                laws_by_year[year] = []
            laws_by_year[year].append(law)
        return laws_by_year

    def write_html_files(self, laws_by_year):
        all_years = sorted(laws_by_year.keys())
        current_file_size = 0
        current_file_index = 1
        current_file_years = []

        for year in all_years:
            year_laws = laws_by_year[year]
            year_html = self.render_html(year_laws)
            year_html_size = len(year_html.encode('utf-8'))

            if current_file_size + year_html_size > 2 * 1024 * 1024 and current_file_years:
                self.save_html_file(current_file_index, current_file_years)
                logging.info(f'Saved HTML file laws_{current_file_index}.html with size {current_file_size} bytes.')
                current_file_size = 0
                current_file_index += 1
                current_file_years = []

            current_file_years.append((year, year_html))
            current_file_size += year_html_size

        if current_file_years:
            self.save_html_file(current_file_index, current_file_years)
            logging.info(f'Saved HTML file laws_{current_file_index}.html with size {current_file_size} bytes.')

    def render_html(self, laws):
        template = Template("""
        <!DOCTYPE html>
        <html lang="ar">
        <head>
            <meta charset="UTF-8">
            <title>Laws</title>
            <style>
                body { font-family: Arial, sans-serif; direction: rtl; background-color: #f9f9f9; }
                .container { width: 90%; margin: auto; }
                .law { margin-bottom: 20px; padding: 20px; border: 1px solid #ddd; border-radius: 5px; background-color: #fff; }
                .law h2 { margin: 0 0 10px 0; color: #333; }
                .law .details, .law .articles { margin-bottom: 10px; }
                .law .details p, .law .articles p { margin: 5px 0; }
                .law .articles h3 { margin-top: 10px; color: #555; }
                #search { margin-bottom: 20px; width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            </style>
            <script>
                function searchLaws() {
                    var input, filter, laws, lawDiv, i, txtValue;
                    input = document.getElementById('search');
                    filter = input.value.toLowerCase();
                    laws = document.getElementsByClassName('law');
                    for (i = 0; i < laws.length; i++) {
                        lawDiv = laws[i];
                        txtValue = lawDiv.textContent || lawDiv.innerText;
                        if (txtValue.toLowerCase().indexOf(filter) > -1) {
                            lawDiv.style.display = "";
                        } else {
                            lawDiv.style.display = "none";
                        }
                    }
                }
            </script>
        </head>
        <body>
            <div class="container">
                <input type="text" id="search" onkeyup="searchLaws()" placeholder="ابحث عن القوانين..">
                <div id="lawsContainer">
                    {% for law in laws %}
                    <div class="law">
                        <h2>السنة: {{ law.year }}</h2>
                        <div class="details">
                            <p>الرقم: {{ law.law_id }}</p>
                            <p>{{ law.subdetails }}</p>
                            <p>تاريخ النشر: {{ law.publish_date }}</p>
                            <p>الصفحة: {{ law.page_number }}</p>
                            <p>ملاحظات: {{ law.notes }}</p>
                        </div>
                        <div class="articles">
                            <h3>المواد:</h3>
                            {% for article in law.articles %}
                                <p>{{ article }}</p>
                            {% endfor %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </body>
        </html>
        """)
        return template.render(laws=laws)

    def save_html_file(self, file_index, years_html):
        file_path = f'laws_{file_index}.html'
        with open(file_path, 'w', encoding='utf-8') as f:
            for year, html in years_html:
                f.write(f'<!-- Year: {year} -->\n')
                f.write(html)
                f.write('\n\n')

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())
    process.crawl(LawsSpider)
    process.start()
