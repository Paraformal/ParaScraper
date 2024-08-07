import logging
from DbHandler import process_html_files

# Configure logging
logging.basicConfig(level=logging.INFO)

def main():
    html_files_directory = 'C:\\Users\\Owner\\Desktop\\Spring2024\\IStay_Scraper\\lebanese_rulings\\lebanese_rulings\\spiders\\laws_html'
    
    logging.info('Starting processing of HTML files...')
    
    process_html_files(html_files_directory)

    logging.info('Finished processing HTML files.')

if __name__ == "__main__":
    main()
