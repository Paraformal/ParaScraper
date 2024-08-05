# Owner // Peter El Khoury

# Using Scrapy to scrape rulings from the Lebanese Ministry of Justice website.
# Using Scarpy MultiThreading to speed up the scraping process.
import scrapy
import json
import os
from jinja2 import Template
from scrapy.crawler import CrawlerProcess
from dotenv import load_dotenv
from scrapy.utils.project import get_project_settings

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
        full_text = response.css('#MainContent_RulingText').getall()
        full_text = ' '.join(full_text).strip()

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

    def close(self, reason):
        with open('rulings.json', 'w', encoding='utf-8') as f:
            json.dump(self.rulings, f, ensure_ascii=False, indent=4)

        self.save_as_html()


    # Saving rulings as HTML files, with a maximum file size of 2MB each.
    # Output is sorted by years and ruling numbers for each year.
    def save_as_html(self):
        rulings_by_year = {}
        for ruling in self.rulings:
            year = ruling['year']
            if year not in rulings_by_year:
                rulings_by_year[year] = []
            rulings_by_year[year].append(ruling)

        all_years = sorted(rulings_by_year.keys())
        current_file_size = 0
        current_file_index = 1
        current_file_years = []

        for year in all_years:
            year_rulings = rulings_by_year[year]
            year_html = self.render_html(year_rulings)
            year_html_size = len(year_html.encode('utf-8'))

            if current_file_size + year_html_size > 2 * 1024 * 1024:
                self.save_html_file(current_file_index, current_file_years)
                current_file_size = 0
                current_file_index += 1
                current_file_years = []

            current_file_years.append((year, year_html))
            current_file_size += year_html_size

        if current_file_years:
            self.save_html_file(current_file_index, current_file_years)

    def render_html(self, rulings):
        template = Template("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Rulings</title>
            <style>
                body { font-family: Arial, sans-serif; }
                table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; }
                th { cursor: pointer; }
                #search { margin-bottom: 20px; }
            </style>
            <script>
                function sortTable(n) {
                    var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
                    table = document.getElementById("rulingsTable");
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
                    table = document.getElementById("rulingsTable");
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
            <input type="text" id="search" onkeyup="searchTable()" placeholder="Search for titles..">
            <table id="rulingsTable">
                <thead>
                    <tr>
                        <th onclick="sortTable(0)">Court</th>
                        <th onclick="sortTable(1)">Number</th>
                        <th onclick="sortTable(2)">Year</th>
                        <th onclick="sortTable(3)">Date</th>
                        <th onclick="sortTable(4)">President</th>
                        <th onclick="sortTable(5)">Members</th>
                        <th onclick="sortTable(6)">Full Text</th>
                    </tr>
                </thead>
                <tbody>
                    {% for ruling in rulings %}
                    <tr>
                        <td>{{ ruling.court }}</td>
                        <td>{{ ruling.number }}</td>
                        <td>{{ ruling.year }}</td>
                        <td>{{ ruling.date }}</td>
                        <td>{{ ruling.president }}</td>
                        <td>{{ ruling.members }}</td>
                        <td>{{ ruling.full_text }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </body>
        </html>
        """)
        return template.render(rulings=rulings)

    def save_html_file(self, index, year_html_list):
        filename = f'rulings_{index}.html'
        with open(filename, 'w', encoding='utf-8') as f:
            for year, html in year_html_list:
                f.write(html)

if __name__ == "__main__":
    process = CrawlerProcess(get_project_settings())
    process.crawl(RulingsSpider)
    process.start()
