import scrapy
import json
import os
import logging
from jinja2 import Template
from scrapy.crawler import CrawlerProcess
from dotenv import load_dotenv
from scrapy.utils.project import get_project_settings

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
            url = f'{AdvancedLawsSearchYearUrl}{year}&articleNumber='
            yield scrapy.Request(url=url, callback=self.parse_year, meta={'year': year})

    def parse_year(self, response):
        law_links = response.css('a[href*="Law.aspx?lawId="]::attr(href)').extract()
        for law_link in law_links:
            law_id = law_link.split('lawId=')[1]
            law_url = f'{AdvancedLawDetailsUrl}{law_id}'
            yield scrapy.Request(url=law_url, callback=self.parse_law_details, meta={'year': response.meta['year'], 'law_id': law_id})

    def parse_law_details(self, response):
        law_id = response.meta['law_id']
        year = response.meta['year']

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
            yield scrapy.Request(url=articles_url, callback=self.parse_articles, meta={'law_details': law_details})
        else:
            self.laws.append(law_details)

    def parse_articles(self, response):
        law_details = response.meta['law_details']
        articles = response.css('td.ArticleText').getall()
        law_details['articles'] = articles

        self.laws.append(law_details)

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
                body { font-family: Arial, sans-serif; direction: rtl; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 20px; direction: rtl; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }
                th { cursor: pointer; }
                #search { margin-bottom: 20px; width: 100%; }
            </style>
            <script>
                function sortTable(n) {
                    var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
                    table = document.getElementById("lawsTable");
                    switching = true;
                    dir = "asc"; 
                    while (switching) {
                        switching = false;
                        rows = table.rows;
                        for (i = 1; i < (rows.length - 1); i++) {
                            shouldSwitch = false;
                            x = rows[i].getElementsByTagName("TD")[n];
                            y = rows[i].getElementsByTagName("TD")[n + 1];
                            if (dir == "asc") {
                                if (x.innerHTML.toLowerCase() > y.innerHTML.toLowerCase()) {
                                    shouldSwitch = true;
                                    break;
                                }
                            } else if (dir == "desc") {
                                if (x.innerHTML.toLowerCase() < y.innerHTML.toLowerCase()) {
                                    shouldSwitch = true;
                                    break;
                                }
                            }
                        }
                        if (shouldSwitch) {
                            rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                            switching = true;
                            switchcount ++;      
                        } else {
                            if (switchcount == 0 && dir == "asc") {
                                dir = "desc";
                                switching = true;
                            }
                        }
                    }
                }

                function searchTable() {
                    var input, filter, table, tr, td, i, j, txtValue;
                    input = document.getElementById("search");
                    filter = input.value.toLowerCase();
                    table = document.getElementById("lawsTable");
                    tr = table.getElementsByTagName("tr");
                    for (i = 1; i < tr.length; i++) {
                        tr[i].style.display = "none";
                        td = tr[i].getElementsByTagName("td");
                        for (j = 0; j < td.length; j++) {
                            if (td[j]) {
                                txtValue = td[j].textContent || td[j].innerText;
                                if (txtValue.toLowerCase().indexOf(filter) > -1) {
                                    tr[i].style.display = "";
                                    break;
                                }
                            } 
                        }
                    }
                }
            </script>
        </head>
        <body>
            <input type="text" id="search" onkeyup="searchTable()" placeholder="ابحث عن العناوين..">
            <table id="lawsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">السنة</th>
                        <th onclick="sortTable(1)">الرقم</th>
                        <th onclick="sortTable(2)">التفاصيل</th>
                        <th onclick="sortTable(3)">المواد</th>
                    </tr>
                </thead>
                <tbody>
                    {% for law in laws %}
                    <tr>
                        <td>{{ law.year }}</td>
                        <td>{{ law.law_id }}</td>
                        <td><a href="{{ AdvancedLawDetailsUrl }}{{ law.law_id }}" target="_blank">التفاصيل</a></td>
                        <td>
                            {% for article in law.articles %}
                                {{ article }}
                            {% endfor %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
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
