#!/usr/bin/python3
from threading import Thread
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from queue import Queue
import scrape_playstore
import os
import argparse
import re
import requests
import shutil
from pathlib import Path

DONE=None
NUM_WORKERS = 3

ARCHITECTURE_INDEX = 2
SCREEN_DPI_INDEX = 4

ROOT_URL = "https://apkpure.com/"
DOWNLOAD_PAGE = "search?q={}&t=app"
# DOWNLOAD_PAGE = "region-free-apk-download"


def match_range(number, ranges):
    for r in ranges:
        if number >= r[0] and number <= r[1]:
            return True

    return False

def sub_range(sub, ranges):
    for r in ranges:
        if sub[0] >= r[0] and sub[1] <= r[1]:
            return True

    return False


def dpi_match(dpi, dpi_list):
    # first, we look for an exact match
    if dpi in dpi_list["others"]:
        return True

    # next, we strip off any non-numeric leading or trailing characters,
    # and remove any "dpi" strings
    subrange = re.search("(\d+)\s*-\s*(\d+)", dpi)
    if subrange:
        subrange = (int(subrange[1]), int(subrange[2])) 
        if sub_range(subrange, dpi_list["dpi_ranges"]):
            return True

    number= re.search("^\D*(\d+)\D*$", dpi)
    if number:
        number = int(number[1])
        if (number in dpi_list["integer_dpis"] or
            match_range(number, dpi_list["dpi_ranges"])
        ):
            return True



    return False

    

class APKPureScraper:
    def __init__(self, allowed_architectures=[], allowed_dpis=[], headless=True):
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", {
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        })
        if headless:
            chrome_options.add_argument("--headless")            
        self.driver = webdriver.Chrome(options=chrome_options)

        self.allowed_dpis = allowed_dpis
        self.allowed_architectures = set(allowed_architectures)

    ''' def get_app_page(self, app_id):
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
        return self.driver.current_url + "/versions" '''
    
    def _go_to_app_page(self, app_id):
        self.driver.get(ROOT_URL + DOWNLOAD_PAGE.format(app_id))
        sleep(1)

        version_elms = self.driver.find_elements_by_xpath(
            "//a[contains(@href, '/" + app_id + "')]"
        )

        if not version_elms:
            print ("no matches for {}".format(app_id))
            return False

        for version_elm in version_elms:
            destination_url = version_elm.get_attribute("href") + "/versions"

            if (requests.get(destination_url).status_code == 200):
                self.driver.get(destination_url)
                return True
                break
            
        print ("No version available for {}".format(app_id))
        return False
        

    def get_all_version_links(self, app_id):
        if not self._go_to_app_page(app_id):
            return []

        sleep(2)

        version_elms = self.driver.find_elements_by_xpath(
            "//a[contains(@href, '/{}/variant/')]".format(app_id)
        )

        if not version_elms:
            version_elms = self.driver.find_elements_by_xpath(
                "//a[contains(@href, '/download/')]"
            )

            return set(download.get_attribute("href").split("?")[0] for download in
                    version_elms)

        versions = [
            version_card.get_attribute("href")
            for version_card in
            version_elms
        ]

        return list(filter(lambda x: not not x, [self.filter_link(link) for link in versions]))


    def filter_link(self, link):
        self.driver.get(link)
        sleep(1)

        download_link = None

        for row_elm in self.driver.find_elements_by_class_name("table-row")[1:]:  # skip header
            arches = row_elm.find_element_by_xpath(
                './div[{}]'.format(
                    ARCHITECTURE_INDEX
                )
            ).text.split("\n")

            dpi = row_elm.find_element_by_xpath(
                './div[{}]'.format(
                    SCREEN_DPI_INDEX
                )
            ).text
            
            if (set(arches).intersection(self.allowed_architectures) and
                dpi_match(dpi, self.allowed_dpis)
            ):
                download_link = row_elm.find_element_by_link_text("Download APK")
                break

        return download_link.get_attribute("href").split("?")[0] if download_link else None


    def download_link(self, link):
        self.driver.get(link)
        download_file_elm_name = self.driver.find_element_by_class_name("file").text
        download_file_elm_name = re.match("(.*) \(", download_file_elm_name)[1]
        return download_file_elm_name
        
        
    

class APKMirrorWorker(Thread):
    def __init__(self, downloader,
                 in_queue,
                 allowed_architectures,
                 allowed_dpis,
                 headless=True
    ):
        Thread.__init__(self)
        self.scraper = APKPureScraper(allowed_architectures, allowed_dpis, headless)
        self.in_queue = in_queue
        self.downloader = downloader

        
    def run(self):
        while True:
            scraped_app = self.in_queue.get()

            if scraped_app == DONE:
                break
            
            category, app_id = scraped_app
            try:
                links = self.scraper.get_all_version_links(app_id)
            except:
                print("Problem with scraping {}".format(app_id))
                continue
            
            print ("links retrieved {}".format(links))

            # next step, sort the links in order from largest apk number to smallest
            # it's ok to take a questionable sorting step here since we dont need perfection
            
            
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

            sorted_download_links = sorted(list(links), reverse=True)
            test_download = sorted_download_links[0]
            version=re.search("/download/(\d+)-", test_download)
            if not version:
                print("There's a problem")
                continue

            version = version[1]
            
            file_name = "{}/{}/{}.{}".format(
                category,
                app_id,
                version,
                "xapk" if "XAPK" in test_download else "apk"
            )
                
            target_download = self.scraper.download_link(test_download)
            self.downloader.submit_task(target_download, file_name)
            
            link_file = "{}/{}/{}_links.txt".format(
                category,
                app_id,
                app_id
            )

            with open(link_file, "w") as out_file:
                for link in sorted_download_links[1:]:
                    out_file.write(link + "\n")

class Downloader(Thread):
    def __init__(self, download_dir):
        Thread.__init__(self)
        self.home = download_dir
        self.q = Queue()


    def run(self):
        while True:
            file_name, target_path = self.q.get()
            print("looking for: {}".format(os.path.join(self.home, file_name)))
            while not os.path.isfile(os.path.join(self.home, file_name)):
                sleep(1.5)

            os.replace(os.path.join(self.home, file_name), target_path)
        

    def submit_task(self, file_name, target_path):
        self.q.put((file_name, target_path))


def download_mirrors(download_directory, num_apps=150, dpi_list=[], architecture_list=[], headless=True, default_download_directory=os.path.join(str(Path.home()), "Downloads")):
    # 3 different categories of apis - a valid range, a valid number, and "nodpi".  Filtered for other possible options though
    if headless:
        default_download_directory = download_directory
    
    integer_dpis = set(map(int, filter (lambda x: x.isdigit(), dpi_list)))
    dpi_ranges = set(map(lambda lowhigh: (int(lowhigh[0]), int(lowhigh[1])),
                         filter(lambda proposed_range: len(proposed_range)==2,
                                map(lambda dpi: dpi.split("-"), dpi_list)))
    )
    others = set(dpi_list) - set(integer_dpis) - set(dpi_ranges)

    dpi_lists = {"others": others,
                "dpi_ranges": dpi_ranges,
                "integer_dpis": integer_dpis
    }


    if not os.path.exists(download_directory):
        print("Path does not exist!")
        exit()

    shutil.rmtree(download_directory)
    os.mkdir(download_directory)

    downloader = Downloader(default_download_directory)

    downloader.start()
    
    os.chdir(download_directory)
        
    for category in scrape_playstore.CHARTS:
        try:
            os.mkdir(category)
        except FileExistsError:
            '''working in a directory that's already been used before'''
            pass

            
    q = Queue()
    workers = [APKMirrorWorker(downloader, q, architecture_list, dpi_lists, headless) for i in range(NUM_WORKERS)]
    for worker in workers:
        worker.start()

    count = 0
    for category, app_id in scrape_playstore.gen_app_ids(num_apps, headless=True):
        if count < num_apps*NUM_WORKERS:
            print ((category, app_id))
            q.put((category, app_id))
            count += 1
        elif count == num_apps*NUM_WORKERS:
            for i in range(NUM_WORKERS):
                q.put(DONE)
        else:
            pass  # exhaust the chunk    
        
            
    for worker in workers:
        worker.join()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch android apk mirrors')
    parser.add_argument(
        "-d", "--download_dir",
        help="location to download apks to --absolute directory please",
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
    parser.add_argument(
        "--debug",
        help="add this flag to run in headless mode",
        action='store_false'
    )

    args = parser.parse_args()
    
    download_mirrors(
        args.download_dir,
        args.num_apps,
        args.dpi,
        args.architectures,
        args.debug
    )
