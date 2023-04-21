from urllib.request import urlopen, Request
from datetime import datetime
from os.path import exists
import json
import sys
import traceback
import smtplib
from bs4 import BeautifulSoup
from time import sleep
import pycron

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select

# Global vars
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36'
TIMEOUT = 20 # Seconds
CONFIGS_LOCATION = None
CONFIG_FILE_PATH = None
BASE_URL = None
POSTCODE = None
POSTCODE_OPTION_VALUE = None
EMAIL_USERNAME = None
EMAIL_PASSWORD = None
RECIPIENT_ADDRESSES = None
CRON_SCHEDULE = None
SLEEP_TIME_SECONDS = 1800

# Selenium webdriver setup
options = Options()
options.add_argument(
    f'user-agent={USER_AGENT}')
options.add_argument("no-sandbox")
options.add_argument("disable-dev-shm-usage")
options.add_argument("--headless")

def init():
    global CONFIGS_LOCATION
    global CONFIG_FILE_PATH

    possible_config_locations = ["./configs/", "/configs/", "/run/secrets/"]
    possible_config_names = ["config.json", "bin-day-config.json"]
    for config_location in possible_config_locations:
        for config_name in possible_config_names:
            config_path = config_location + config_name
            if exists(config_path):
                CONFIGS_LOCATION = config_location
                CONFIG_FILE_PATH = config_path
                break
    
    if CONFIG_FILE_PATH is None:
        exit_with_failure(
            'missing config.json file, could not find in locations: ' + ', '.join(str(x) for x in possible_config_locations)
        )

    load_config(CONFIG_FILE_PATH)

    if BASE_URL is None or POSTCODE is None or POSTCODE_OPTION_VALUE is None or EMAIL_USERNAME is None or EMAIL_PASSWORD is None or EMAIL_USERNAME is None or RECIPIENT_ADDRESSES is None:
        exit_with_failure(
            'missing required credentials in environment variables')
        
def main():
    get_page_html()
    html = ""
    with open("output.html", "r") as input:
        html = input.read().replace('\n', '')
    
    bin_dates = extract_dates(html, [ "Refuse", "Recycling" ])
    if len(bin_dates) <= 0:
        exit_with_failure("No bin dates to work with! Exiting...")
    
    send_bin_due_alert(bin_dates[0])
    
def get_page_html():
    driver = webdriver.Chrome(
        options=options)

    driver.get(f'{BASE_URL}')

    iframe = WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((
        By.ID, "fillform-frame-1")))
    driver.switch_to.frame(iframe)

    postcode_entry = WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((
        By.ID, "PostcodeSearch")))
    postcode_entry.send_keys(POSTCODE)

    submit_button = driver.find_element(By.ID,"button1")
    submit_button.click()

    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, f"option[value='{POSTCODE_OPTION_VALUE}']"))
    )

    select_address = Select(WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((
        By.ID, "ChooseAddress"))))
    WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "option[value='100050498735']"))
    )
    select_address.select_by_value('100050498735')
    
    WebDriverWait(driver, TIMEOUT).until(EC.element_to_be_clickable((By.ID, "moreCollections" ))).click()

    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CLASS_NAME, "repeatable-table-wrapper"))
    )
    
    WebDriverWait(driver, TIMEOUT).until(lambda driver: driver.find_element(By.XPATH, "//th[@style='text-align:center']").get_attribute("innerHTML") == "Refuse Dates")
    
    html = driver.page_source
    with open("output.html", "w") as output:
        output.write(driver.page_source)

def extract_dates(html, headings):
    results = []
    soup = BeautifulSoup(html, features="html.parser")

    for heading in headings:
        heading_element = soup.find('h3', string=heading)
        table = heading_element.next_sibling
        rows = table.find_all('td')
        for i, row in enumerate(rows):
            if(i != 0):
                date = row.get_text()
                parsed_date = datetime.strptime(date, "%A %d %b %Y").date()
                results.append({ 'bin_type' : heading, 'date' : parsed_date })

    results.sort(key=lambda x: x['date'], reverse=False)

    return results

def print_with_timestamp(text):
    print(f'{datetime.now().strftime("%d/%m/%Y %H:%M:%S")} - {text}')


def exit_with_failure(message):
    traceback.print_exc()
    print_with_timestamp(message)
    sys.exit(1)

def load_config(path):
    global BASE_URL
    global POSTCODE
    global POSTCODE_OPTION_VALUE
    global EMAIL_USERNAME
    global EMAIL_PASSWORD
    global RECIPIENT_ADDRESSES
    global CRON_SCHEDULE
    global SLEEP_TIME_SECONDS

    with open(path, 'r') as file:
        data = json.load(file)

        BASE_URL = data['BASE_URL']
        POSTCODE = data['POSTCODE']
        POSTCODE_OPTION_VALUE = data['POSTCODE_OPTION_VALUE']
        EMAIL_USERNAME = data['EMAIL_USERNAME']
        EMAIL_PASSWORD = data['EMAIL_PASSWORD']
        RECIPIENT_ADDRESSES = data['RECIPIENT_ADDRESSES']
        CRON_SCHEDULE = data['CRON_SCHEDULE']
        SLEEP_TIME_SECONDS = data['SLEEP_TIME_SECONDS']

def send_bin_due_alert(bin_object):
    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
    message = get_bin_message(bin_object)

    if message != '':
        for RECIPIENT_ADDRESS in RECIPIENT_ADDRESSES:
            try:
                server.sendmail(EMAIL_USERNAME, [RECIPIENT_ADDRESS], message)
                print(f'{RECIPIENT_ADDRESS}: {message}')
            except:
                print('unable to send:\n' + message)
                raise

    server.quit()

def get_bin_message(bin_object):
    bin_type = bin_object['bin_type']
    bin_date = bin_object['date'].strftime('%A %d/%m/%Y')

    bin_colour = "Blue"
    if bin_type == "Refuse":
        bin_colour = "Green"
    
    return f'Put the {bin_type} bin ({bin_colour}) out for collection on {bin_date}.'

if __name__ == '__main__':
    init()
    check_date = datetime.now()
    print(f"Starting main loop with time: {check_date} and cron: {CRON_SCHEDULE}")
    while True:
        print(f"Checking if cron ({CRON_SCHEDULE}) is between: {check_date} - {datetime.now()}")
        if pycron.has_been(CRON_SCHEDULE, check_date):
            
            print('Getting bin dates')
            try:
                main()
                print("Done.")
            except Exception as e:
                print("Failed to get bin dates")
                print(traceback.format_exc())         
            check_date = datetime.now()     

        print(f"Sleeping for {SLEEP_TIME_SECONDS}s")
        sleep(SLEEP_TIME_SECONDS)                    
