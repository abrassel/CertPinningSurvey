import argparse
import os
import Path
from scrape_apkmirror import \
    NUM_WORKERS, NUM_CONCURRENT_DOWNLOADS, \
    APKPureScraper, Downloader
from threading import Thread, Semaphore, Lock



class APKMirrorWorker(Thread):
    def __init__(self, downloader,
                 iterator,
                 lock,
                 headless=True
    ):
        Thread.__init__(self)
        self.scraper = APKPureScraper([], [], headless)
        self.iterator = iterator
        self.downloader = downloader
        self.lock = lock

        
    def run(self):
        while True:
            self.lock.acquire()
            if 
            
            category, app_id = scraped_app
            try:
                links = self.scraper.get_all_version_links(app_id)
            except Exception as e:
                print("Problem with scraping {}".format(app_id))
                print(e)
                continue
            
            print ("# links retrieved {}".format(len(links)))

            # next step, sort the links in order from largest apk number to smallest
            # it's ok to take a questionable sorting step here since we dont need perfection
            
            
            # go to category directory
            # go to app_id directory (create if not exists)
            # download apk with name: version.apk

            if not links:
                continue  # don't create an empty folder
            
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
            test_download = sorted_download_links[0]
            version=re.search("/download/(\d+)-", test_download)
            if not version:
                print("There's a problem")
                continue

            version = version[1]
            
            file_name = "{}/{}.{}".format(
                app_id,
                version,
                "xapk" if "XAPK" in test_download else "apk"
            )
                
            target_download = self.scraper.download_link(test_download, self.downloader.download_semaphore)
            self.downloader.submit_task(target_download, file_name)
            
            link_file = "{}/{}_links.txt".format(
                app_id,
                app_id
            )

            attr_file = "{}/{}_cats.txt".format(
                app_id,
                app_id
            )

            with open(link_file, "w") as out_file:
                out_file.writelines(sorted_download_links[1:])

            with open(attr_file, "w") as out_file:
                out_file.write(category + "\n")










def download_versions(download_dir, headless=True):
    if headless:
        chrome_download_location = download_dir
    else:
        chrome_download_location = os.path.join(str(Path.home()), "Downloads")

    if not os.path.exists(download_dir):
        print("Path does not exist!")
        exit()
        
    app_ids_to_download_links= {}
    for filename in os.listdir(download_dir):
        app_ids_to_download_links[filename] = (
            line.strip() for line in open(filename, "r"))

    downloader = Downloader(chrome_download_location,
                            Semaphore(NUM_CONCURRENT_DOWNLOADS))

    access_lock = Lock()
    iterator = iter(app_ids_to_download_links)
    downloader.start()
    os.chdir(download_directory)
    workers = [
        APKMirrorWorkerCopy(
            downloader,
            iterator,
            access_lock,
            headless
            )
        for i in range(NUM_WORKERS)
    ]
    
            
            


if __name__ == "__main__":
    parser = argeparse.ArgumentParser(description='Download a versioned set of apks based on a folder of text files')

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
