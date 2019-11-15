#!/bin/usr/python3
from threading import Thread
from selenium import webdriver
from queue import Queue
import scrape_playstore

NUM_WORKERS = 1

ALLOWED_DPIS = []
ALLOWED_ARCHITECTURES = []

class APKMirrorWorker(Thread):
    def __init__(self, in_queue):
        Thread.__init__(self)
        self.scraper = APKMirrorScraper()
        self.in_queue = in_queue
        

    def run(self):
        while True:
            app_id = in_queue.get()
            links_and_versions = self.scraper.get_compatible_mirror_links_and_versions()
            print(links)
            in_queue.task_done()


def download_mirrors(dpi_list=[], architecture_list=[]):
    ALLOWED_DPIS = dpi_list
    ALLOWED_ARCHITECTURES = architecture_list

    q = Queue()

    for i in range(NUM_WORKERS):
        APKMirrorWorker(q).start()


    for cat_app_id_chunk in scrape_playstore.gen_app_ids_by_chunk():
        for _,app_id in cat_app_id_chunk:
            q.put(app_id)
        
    q.join()
