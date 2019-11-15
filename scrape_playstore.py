#!/usr/bin/python3

from selenium import webdriver
from time import sleep
from selenium.webdriver.chrome.options import Options
chrome_options = Options()
chrome_options.add_argument("--headless")
from threading import Thread
from queue import Queue

BASE_URL="https://play.google.com/store/apps/top"
SEARCH_URL="/store/apps/details?id="

SCROLL_PAUSE_TIME = 1

CHARTS = {
    "TOP_FREE": "Top Free Apps",
    "TOP_GAMES": "Top Free Games",
    "TOP_GROSSING": "Top Grossing Apps",
    "TOP_GROSSING_GAMES": "Top Grossing Games"
}
   

class AppController:
    def __init__(self):
        self.driver = webdriver.Chrome(options=chrome_options)
        
        
    def infinite_scroll(self, task):
        # Get scroll height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while True:

            yield task()
            
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait to load page
            sleep(SCROLL_PAUSE_TIME)

            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
        
    def navigate_to(self, chart_option):
        self.driver.get(BASE_URL)
        result = self.driver.find_element_by_link_text(CHARTS[chart_option])
        result.click()

    
    def gen_app_id_chunks(self, category, size=150):
        def task(): 
            app_list = self.driver.find_elements_by_xpath(
                "//a[contains(@href,'{}')]".format(SEARCH_URL)
            )

            sleep(1)
            new_app_ids = set([
                app.get_attribute("href").split("?id=")[-1]
                for app in app_list
            ])  # remove duplicates

            return new_app_ids

        self.navigate_to(category)

        app_ids = set()
        for new_app_ids in self.infinite_scroll(task):

            if not new_app_ids - app_ids or len(app_ids) > size:
                break

            yield new_app_ids - app_ids
            app_ids = app_ids.union(new_app_ids)    


    def get_app_ids(self, category, size=150):
        return [
            app_id for app_ids_chunk in
            app_ids_chunk for app_ids_chunk in
            self.gen_app_id_chunks(category)
        ]
    
            
    def shutdown(self):
        self.driver.quit()


    def _debug(self, elm):
        attrs = self.driver.execute_script('var items = {}; for (index = 0; index < arguments[0].attributes.length; ++index) { items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; return items;', elm)
        return attrs
    
DONE=None
def gen_app_ids(results_per_category=150):
    '''generator that simultaneously pulls from each category'''
    
    found_app_ids = Queue()

    def gen_apps(in_queue, chart_key, num_results):
        app_controller = AppController()

        for app_id_chunk in app_controller.gen_app_id_chunks(chart_key, num_results):
            for app_id in app_id_chunk:
                in_queue.put((chart_key, app_id))

        app_controller.shutdown()
        in_queue.put(DONE)
        

    for chart_key in CHARTS:
        Thread(
            target = gen_apps,
            args=(found_app_ids, chart_key, results_per_category)
        ).start()

    dones_remaining = len(CHARTS)
    while dones_remaining > 0:
        app_id = found_app_ids.get()
        if app_id == DONE:
            dones_remaining -= 1
            continue

        yield app_id
        
            
if __name__=="__main__":
    for app_id in gen_app_ids():
        print(app_id)
