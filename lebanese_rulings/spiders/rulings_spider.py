import scrapy
import json
import os

class RulingsSpider(scrapy.Spider):
    name = 'rulings_spider'

    def start_requests(self):
        # Load years from JSON file
        with open('C:\\Users\\Owner\\Desktop\\Spring2024\\IStay_Scraper\\lebanese_rulings\\lebanese_rulings\\spiders\\years.json') as f:
            years = json.load(f).get('years', [])
        
        # Generate initial URLs for each year
        for year in years:
            url = f'http://77.42.251.205/AdvancedRulingSearch.aspx?searchText=&AndOr=AND&courtID=0&rulNumber=0&rulYear={year}&judjes='
            yield scrapy.Request(url=url, callback=self.parse_year)

    def parse_year(self, response):
        # Extract ruling IDs from the search result page
        ruling_links = response.css("a::attr(href)").re(r"ViewRulePage\.aspx\?ID=(\d+)&selection=")
        for ruling_id in ruling_links:
            ruling_url = f'http://77.42.251.205/ViewRulePage.aspx?ID={ruling_id}&selection='
            yield scrapy.Request(url=ruling_url, callback=self.parse_ruling, meta={'year': response.url.split('rulYear=')[1].split('&')[0]})

        # Follow pagination links
        next_page = response.css('a.next::attr(href)').get()
        if next_page is not None:
            yield response.follow(next_page, self.parse_year)

    def parse_ruling(self, response):
        # Extract details of the ruling
        court = response.css('#MainContent_lblcourtName::text').get()
        number = response.css('#MainContent_lblNumber::text').get()
        year = response.meta['year']
        date = response.css('#MainContent_lblDate::text').get()
        president = response.css('#MainContent_lblJudge::text').get()
        members = response.css('#MainContent_lblMembers::text').get()
        full_text = response.css('#MainContent_RulingText::text').getall()
        full_text = ' '.join(full_text).strip()

        yield {
            'court': court,
            'number': number,
            'year': year,
            'date': date,
            'president': president,
            'members': members,
            'full_text': full_text
        }

    def close(self, reason):
        # Save the collected rulings into HTML files
        self.save_as_html()

    def save_as_html(self):
        # Load collected data
        if not os.path.exists('rulings.json'):
            return
        
        with open('rulings.json', 'r', encoding='utf-8') as file:
            try:
                rulings = json.load(file)
            except json.JSONDecodeError:
                return
        
        # Split data into 10 parts
        chunk_size = len(rulings) // 10
        chunks = [rulings[i:i + chunk_size] for i in range(0, len(rulings), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            with open(f'rulings_part_{i + 1}.html', 'w', encoding='utf-8') as file:
                file.write('<html><body>\n')
                for ruling in chunk:
                    file.write(f"<h1>المحكمة: {ruling['court']}</h1>\n")
                    file.write(f"<p>الرقم: {ruling['number']}</p>\n")
                    file.write(f"<p>السنة: {ruling['year']}</p>\n")
                    file.write(f"<p>تاريخ الجلسة: {ruling['date']}</p>\n")
                    file.write(f"<p>الرئيس: {ruling['president']}</p>\n")
                    file.write(f"<p>الأعضاء: {ruling['members']}</p>\n")
                    file.write(f"<p>{ruling['full_text']}</p>\n")
                    file.write('<hr/>\n')
                file.write('</body></html>')

