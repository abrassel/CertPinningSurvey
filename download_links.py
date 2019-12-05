#!/usr/bin/python3

import argparse
import re
from queue import Queue
import os
from pathlib import Path
from scrape_apkmirror import \
    NUM_WORKERS, NUM_CONCURRENT_DOWNLOADS, \
    APKPureScraper, Downloader
from threading import Thread, Semaphore, Lock

DONE = None

class APKMirrorWorkerCopy(Thread):
    def __init__(self, downloader,
                 queue,
                 headless=True
    ):
        Thread.__init__(self)
        self.scraper = APKPureScraper([], [], headless)
        self.queue = queue
        self.downloader = downloader

        
    def run(self):
        while True:

            next_app_id_list = self.queue.get()

            if next_app_id_list == None:
                break
            
            app_id, links = next_app_id_list
            
            try:
                os.mkdir(
                    "{}".format(
                        app_id
                    )
                )
            except FileExistsError:
                '''File already exists'''
                pass

            sorted_download_links = sorted(list(links), reverse=True)

            for download in sorted_download_links:
                version=re.search("/download/(\d+)-", download)
                if not version:
                    print("There's a problem")
                    continue

                version = version[1]
            
                file_name = "{}/{}.{}".format(
                    app_id,
                    version,
                    "xapk" if "XAPK" in download else "apk"
                )
                
                target_download = self.scraper.download_link(download, self.downloader.download_semaphore)
                self.downloader.submit_task(target_download, file_name)
                


def download_versions(download_dir, headless=True):
    if headless:
        chrome_download_location = download_dir
    else:
        chrome_download_location = os.path.join(str(Path.home()), "Downloads")

    if not os.path.exists(download_dir):
        print("Path does not exist!")
        exit()

    os.chdir(download_dir)
        
    app_ids_to_download_links= {}
    for filename in os.listdir(download_dir):
        if not "_links.txt" in filename:
            continue

        with open(filename, "r") as link_file:
            links = link_file.read().strip()

        links = [link + "APK" for link in links.split("APK")[:-1]]
        

        app_ids_to_download_links[filename.split("_")[0]] = links

    downloader = Downloader(chrome_download_location,
                            Semaphore(NUM_CONCURRENT_DOWNLOADS))

    queue = Queue()
    downloader.start()
    workers = [
        APKMirrorWorkerCopy(
            downloader,
            queue,
            headless
            )
        for i in range(NUM_WORKERS)
    ]

    for worker in workers:
        worker.start()

    for app_id in app_ids_to_download_links:
        queue.put((app_id, app_ids_to_download_links[app_id]))
    
    for i in range(NUM_WORKERS):
        queue.put(DONE)

    for worker in workers:
        worker.join()

    downloader.shutdown()
    downloader.join()
            


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download a versioned set of apks based on a folder of text files')

    parser.add_argument(
        "-d", "--download_dir",
        help="location where the downloads live, absolute directory",
        type=str,
        nargs="?",
        default=os.getcwd()
    )
    parser.add_argument(
        "--debug",
        help="add this flag to run without headless mode",
        action='store_false'
    )

    args = parser.parse_args()

    download_versions(
        args.download_dir,
        args.debug
    )
