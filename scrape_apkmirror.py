#!/usr/bin/python3
from threading import Thread
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from queue import Queue
import scrape_playstore
import os
import argparse

DONE=None
NUM_WORKERS = 2

ALLOWED_DPIS = []
ALLOWED_ARCHITECTURES = []

ARCHITECTURE_INDEX = 2
SCREEN_DPI_INDEX = 4

ROOT_URL = "https://apkpure.com/"
DOWNLOAD_PAGE = "region-free-apk-download"
LOCATION = None

class APKPureScraper:
    def __init__(self):
        self.driver = webdriver.Chrome()


    def get_app_page(self, app_id):
        self.driver.get(ROOT_URL + DOWNLOAD_PAGE)
        sleep(1)
        text_element = self.driver.find_element_by_id('region-package')
        text_element.send_keys(Keys.CONTROL + "a")
        text_element.send_keys(Keys.DELETE)

        sleep(.1)
        # now we add our app_id
        text_element.send_keys(app_id)
        sleep(.1)
        text_element.send_keys(Keys.ENTER)
        sleep(.5)
        return self.driver.current_url + "/versions"


    def _go_to_app_page(self, app_id):
        self.driver.get(self.get_app_page(app_id))
    

    def get_all_version_links(self, app_id):
        self._go_to_app_page(app_id)
        sleep(2)

        version_elms = self.driver.find_elements_by_xpath(
            "//a[contains(@href, '/{}/variant/')]".format(app_id)
        )

        versions = [
            version_card.get_attribute("href")
            for version_card in
            version_elms
        ]

        return versions


    def filter_link(self, link):
        self.driver.get(link)
        sleep(1)

        download_link = None

        for row_elm in self.driver.find_elements_by_class_name("table-row")[1:]:  # skip header
            arch = row_elm.find_element_by_xpath(
                './div[{}]'.format(
                    ARCHITECTURE_INDEX
                )
            ).text

            dpi = row_elm.find_element_by_xpath(
                './div[{}]'.format(
                    SCREEN_DPI_INDEX
                )
            ).text
            
            if (arch in ALLOWED_ARCHITECTURES and
                dpi in ALLOWED_DPIS
            ):
                download_link = row_elm.find_element_by_link_text("Download APK")
                break

        return download_link
    

    def get_filtered_versions_download(self, app_id):
        version_links = self.get_all_version_links(app_id)

        final_links = []
        for link in version_links:
            valid_link = self.filter_link(link)

            if valid_link:
                final_links.append(valid_link)
            sleep(.5)

        return final_links         
    

class APKMirrorWorker(Thread):
    def __init__(self, in_queue):
        Thread.__init__(self)
        self.scraper = APKPureScraper()
        self.in_queue = in_queue
        

    def run(self):
        while True:
            scraped_app = self.in_queue.get()

            if scraped_app == DONE:
                break
            
            category, app_id = scraped_app
            links = self.scraper.get_filtered_versions_download(app_id)
            
            # go to category directory
            # go to app_id directory (create if not exists)
            # download apk with name: version.apk

            if not links:
                continue  # don't create an empty folder
            
            try:
                os.mkdir(
                    "{}/{}".format(
                        category,
                        app_id
                    )
                )
            except FileExistsError:
                '''File already exists'''
                pass


def download_mirrors(download_directory, num_apps=150, dpi_list=[], architecture_list=[]):
    global ALLOWED_DPIS; ALLOWED_DPIS = dpi_list
    global ALLOWED_ARCHITECTURES; ALLOWED_ARCHITECTURES = architecture_list
    LOCATION = download_directory

    if not os.path.exists(download_directory):
        print("Path does not exist!")
        exit()

    os.chdir(download_directory)
        
    for category in scrape_playstore.CHARTS:
        try:
            os.mkdir(category)
        except FileExistsError:
            '''working in a directory that's already been used before'''
            pass

            
    q = Queue()
    workers = [APKMirrorWorker(q) for i in range(NUM_WORKERS)]
    for worker in workers:
        worker.start()

    generated = 0  # it's hacky code time
    for category, app_id in scrape_playstore.gen_app_ids(num_apps):
        generated += 1
        if generated > num_apps:
            break
        q.put((category, app_id))


    for i in range(len(workers)):
        q.put(DONE)
    
    for worker in workers:
        worker.join()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch android apk mirrors')
    parser.add_argument(
        "-d", "--download_dir",
        help="location to download apks to",
        type=str,
        nargs="?",
        default=os.getcwd()
    )
    parser.add_argument(
        "-n", "--num_apps",
        help="the number of apps to download per category (as given by CHARTS)",
        type=int,
        nargs="?",
        default=150
    )
    parser.add_argument(
        "-a", "--architectures",
        help="list of valid architectures for this download",
        type=str,
        nargs="+",
        required=True
    )
    parser.add_argument(
        "--dpi",
        help="list of valid dpi types for this download",
        type=str,
        nargs="+",
        required=True
    )

    args = parser.parse_args()
    
    download_mirrors(
        args.download_dir,
        args.num_apps,
        args.dpi,
        args.architectures
    )
