# Owner's Desktop / Peter El Khoury

# Using scrapy lib to perform the web requests,
# Using scrapy implemented multi threading for more data scraping speed and performance,
import scrapy
import json
import os
import logging
from jinja2 import Template
from scrapy.crawler import CrawlerProcess
from dotenv import load_dotenv
from scrapy.utils.project import get_project_settings
from DbHandler import save_to_db
from bs4 import BeautifulSoup
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Get URLs and paths from environment variables
AdvancedRulingsSearchYearUrl = os.getenv('AdvancedRulingsSearchYearUrl')
AdvancedRulingsSearchDetailsUrl = os.getenv('AdvancedRulingsSearchDetailsUrl')
RulingsYearFile = os.getenv('RulingsYearFile')

class RulingsSpider(scrapy.Spider):
    name = 'rulings_spider'
    custom_settings = {
        'FEED_EXPORT_ENCODING': 'utf-8',
    }

    def __init__(self, *args, **kwargs):
        super(RulingsSpider, self).__init__(*args, **kwargs)
        self.rulings = []

    def start_requests(self):
        with open(RulingsYearFile) as f:
            years = json.load(f).get('years', [])
        
        for year in years:
            url = f'{AdvancedRulingsSearchYearUrl}{year}&judjes='
            yield scrapy.Request(url=url, callback=self.parse_year, meta={'year': year})

    def parse_year(self, response):
        ruling_links = response.css("a::attr(href)").re(r"ViewRulePage\.aspx\?ID=(\d+)&selection=")
        for ruling_id in ruling_links:
            ruling_url = f'{AdvancedRulingsSearchDetailsUrl}{ruling_id}&selection='
            yield scrapy.Request(url=ruling_url, callback=self.parse_ruling, meta={'year': response.meta['year']})

        next_page = response.css('a.next::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse_year, meta=response.meta)

    def parse_ruling(self, response):
        court = response.css('#MainContent_lblcourtName::text').get()
        number = response.css('#MainContent_lblNumber::text').get()
        year = response.meta['year']
        date = response.css('#MainContent_lblDate::text').get()
        president = response.css('#MainContent_lblJudge::text').get()
        members = response.css('#MainContent_lblMembers::text').get()
        full_text_html = response.css('#MainContent_RulingText').getall()
        full_text = ' '.join([BeautifulSoup(text, "html.parser").get_text() for text in full_text_html]).strip()

        try:
            date = datetime.strptime(date, '%d/%m/%Y').date()
        except ValueError:
            date = None

        ruling = {
            'court': court,
            'number': number,
            'year': year,
            'date': date,
            'president': president,
            'members': members,
            'full_text': full_text
        }

        self.rulings.append(ruling)
        yield ruling


    # Data saved in html file is sorted.
    # Data saved in sql database is not sorted. (There is no need to waste resource by sorting it, 
    # we can just apply query to sort when needed)
    # As well data is saved in json file as fall back if saving to html/db fails.
    def close(self, reason):
        logging.info('Spider closing...')
        self.save_as_html()
        save_to_db(self.rulings)
        # with open('rulings.json', 'w', encoding='utf-8') as f:
        #     json.dump(self.rulings, f, ensure_ascii=False, indent=4)
        # logging.info('rulings.json file created.')

    def save_as_html(self):
        rulings_by_year = self.organize_rulings_by_year()
        self.write_html_files(rulings_by_year)

    def organize_rulings_by_year(self):
        rulings_by_year = {}
        for ruling in self.rulings:
            year = ruling['year']
            if year not in rulings_by_year:
                rulings_by_year[year] = []
            rulings_by_year[year].append(ruling)
        return rulings_by_year

    def write_html_files(self, rulings_by_year):
        all_years = sorted(rulings_by_year.keys())
        current_file_size = 0
        current_file_index = 1
        current_file_years = []

        for year in all_years:
            year_rulings = rulings_by_year[year]
            year_html = self.render_html(year_rulings)
            year_html_size = len(year_html.encode('utf-8'))

            # Ensure the whole year's data is in one file, even if it exceeds the size limit
            if current_file_size + year_html_size > 2 * 1024 * 1024 and current_file_years:
                self.save_html_file(current_file_index, current_file_years)
                logging.info(f'Saved HTML file rulings_{current_file_index}.html with size {current_file_size} bytes.')
                current_file_size = 0
                current_file_index += 1
                current_file_years = []

            current_file_years.append((year, year_html))
            current_file_size += year_html_size

        if current_file_years:
            self.save_html_file(current_file_index, current_file_years)
            logging.info(f'Saved HTML file rulings_{current_file_index}.html with size {current_file_size} bytes.')

    def render_html(self, rulings):
        # Loading the HTML template from a file for better code reusability
        template_path = os.path.join(os.path.dirname(__file__), 'html_saving_templates', 'rulings_template.html')
        with open(template_path, 'r', encoding='utf-8') as file:
            template = Template(file.read())
        
        return template.render(rulings=rulings)


    def save_html_file(self, index, year_html_list):
        filename = f'rulings_{index}.html'
        with open(filename, 'w', encoding='utf-8') as f:
            for year, html in year_html_list:
                f.write(html)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    process = CrawlerProcess(get_project_settings())
    process.crawl(RulingsSpider)
    process.start()
