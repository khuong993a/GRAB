import json
import threading
from fake_useragent import UserAgent
import time
import random
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import logging
import tempfile
import seleniumwire.undetected_chromedriver as uc
from selenium.webdriver.common.by import By

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('seleniumwire').disabled = True
logging.getLogger('seleniumwire').setLevel(logging.ERROR)

# Загрузка конфигурации
with open('config.json', 'r') as f:
    config = json.load(f)

MAX_MAINTENANCE_ATTEMPTS = 5
MAINTENANCE_RETRY_DELAY = 10
MAX_LOGIN_ATTEMPTS = 5
LOGIN_RETRY_DELAY = 10
NUM_THREADS = config['num_threads']
ACCOUNTS_FILE = config['accounts_file']
SESSION_INTERVAL = config['session_interval']
EXTENSION_PATH = './extension/caacbgbklghmpodbdafajbgdnegacfmo/1.0.14_0/'

def load_data(filename):
    try:
        with open(filename, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logging.error(f"Error loading file {filename}: {str(e)}")
        return []

def setup_driver():
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'--load-extension={EXTENSION_PATH}')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')

    user_data_dir = tempfile.mkdtemp()

    try:
        driver = uc.Chrome(options=chrome_options, user_data_dir=user_data_dir)
        return driver
    except Exception as e:
        logging.error(f"Error setting up driver: {str(e)}")
        return None

def wait_for_page_load(driver, timeout=120):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        time.sleep(2)
        logging.info("Page fully loaded")
    except Exception as e:
        logging.error(f"Timeout waiting for page load: {str(e)}")
        raise

def close_popups(driver):
    popups = [
        {
            "xpath": "//div[contains(@class, 'flex-row-center') and contains(@class, 'bg-[#fff]') and contains(@class, 'rounded-full')]",
            "description": "First type of popup"
        },
        {
            "xpath": "//button[contains(@class, 'w-full') and contains(text(), 'I got it')]",
            "description": "'I got it' popup"
        }
    ]

    for popup in popups:
        try:
            element = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, popup["xpath"]))
            )
            element.click()
            logging.info(f"Closed {popup['description']}")
        except Exception:
            logging.info(f"{popup['description']} not found or unable to close")

def login_to_extension(driver, username, password):
    try:
        driver.get('chrome-extension://caacbgbklghmpodbdafajbgdnegacfmo/popup.html')
        wait_for_page_load(driver)

        while len(driver.window_handles) < 2:
            pass
        driver.switch_to.window(driver.window_handles[-1])
        wait_for_page_load(driver)

        email_input = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[2]/div[1]/input")
        email_input.send_keys(username)
        password_input = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[2]/div[2]/span/input")
        password_input.send_keys(password)

        login_button = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[4]/button[1]")
        if login_button.is_displayed():
            login_button.click()
        else:
            logging.error("Login button not visible")
            return False

        wait_for_page_load(driver)
        if driver.find_elements(By.XPATH, "//div[contains(@class, 'dashboard')]"):
            close_popups(driver)
            return True
        else:
            logging.error("Login was not successful")
            return False
    except Exception as e:
        logging.error(f"Unexpected error during login: {str(e)}")
        return False

def maintain_session(driver, username):
    attempts = 0
    while attempts < MAX_MAINTENANCE_ATTEMPTS:
        try:
            driver.switch_to.window(driver.window_handles[1])
            driver.refresh()
            wait_for_page_load(driver)

            points_element = driver.find_elements(By.XPATH, "/html/body/div[1]/div[1]/div[2]/main/div/div/div[2]/div/div[1]/div[2]/div[1]")
            if points_element:
                points = points_element[0].text
                logging.info(f"[{username}] Current points: {points}")
            else:
                logging.warning(f"[{username}] Points element not found")

            driver.switch_to.window(driver.window_handles[0])
            return
        except Exception as e:
            attempts += 1
            logging.error(f"[{username}] Error during session maintenance: {str(e)}")
            if attempts < MAX_MAINTENANCE_ATTEMPTS:
                time.sleep(MAINTENANCE_RETRY_DELAY)

def farm_points(account):
    username, password = account.split(':')
    driver = None
    login_attempts = 0

    while login_attempts < MAX_LOGIN_ATTEMPTS:
        driver = setup_driver()
        if not driver:
            break

        if login_to_extension(driver, username, password):
            threading.Thread(target=maintain_session, args=(driver, username)).start()
            while True:
                time.sleep(60)
        else:
            login_attempts += 1
            time.sleep(LOGIN_RETRY_DELAY)
        driver.quit()

def main():
    accounts = load_data(ACCOUNTS_FILE)
    threads = []

    for i in range(min(NUM_THREADS, len(accounts))):
        thread = threading.Thread(target=farm_points, args=(accounts[i],))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
