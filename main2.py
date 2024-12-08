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

MAX_MAINTENANCE_ATTEMPTS = 5  # Максимальное количество попыток поддержания сессии
MAINTENANCE_RETRY_DELAY = 10  # Задержка между попытками поддержания сессии (в секундах)
MAX_LOGIN_ATTEMPTS = 5  # Максимальное количество попыток входа
LOGIN_RETRY_DELAY = 10  # Задержка между попытками входа (в секундах)
NUM_THREADS = config['num_threads']
ACCOUNTS_FILE = config['accounts_file']
PROXIES_FILE = config['proxies_file']
SESSION_INTERVAL = config['session_interval']
EXTENSION_PATH = './extension/caacbgbklghmpodbdafajbgdnegacfmo/1.0.14_0/'


def load_data(filename):
    """Load data from a file (e.g., accounts or proxies)."""
    try:
        with open(filename, 'r') as f:
            data = [line.strip() for line in f if line.strip()]
        if not data:
            logging.error(f"{filename} is empty!")
        return data
    except Exception as e:
        logging.error(f"Error loading file {filename}: {str(e)}")
        return []


def setup_driver(proxy):
    """Set up the Selenium WebDriver with the given proxy."""
    chrome_options = uc.ChromeOptions()

    proxy_options = {
        "proxy": {
            "http": proxy,
            "https": proxy,
        },
        'disable_encoding': True,
        'suppress_connection_errors': True,
        'verify_ssl': False,
        'connection_timeout': None,
        'connection_keep_alive': True,
        'no_proxy': ''
    }

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

    driver = uc.Chrome(seleniumwire_options=proxy_options, options=chrome_options, user_data_dir=user_data_dir,
                       user_multi_procs=True, use_subprocess=True)

    return driver


def wait_for_page_load(driver):
    """Wait for the page to load completely."""
    try:
        WebDriverWait(driver, 120).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        time.sleep(15)
        logging.info("Page fully loaded")
    except Exception as e:
        logging.error(f"Timeout waiting for page load: {str(e)}")
        raise


def close_popups(driver):
    """Close popups on the page if they exist."""
    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'flex-row-center') and contains(@class, 'bg-[#fff]') and contains(@class, 'rounded-full')]"))
        )
        close_button.click()
        logging.info("Closed first type of popup")
    except Exception:
        logging.info("First type of popup not found or unable to close")

    try:
        got_it_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(@class, 'w-full') and contains(text(), 'I got it')]"))
        )
        got_it_button.click()
        logging.info("Closed 'I got it' popup")
    except Exception:
        logging.info("'I got it' popup not found or unable to close")


def login_to_extension(driver, username, password):
    """Log into the extension using the provided username and password."""
    try:
        driver.get('chrome-extension://caacbgbklghmpodbdafajbgdnegacfmo/popup.html')
        wait_for_page_load(driver)
        logging.info("Extension page loaded")

        while len(driver.window_handles) < 2:
            pass
        logging.info("Second tab opened")

        driver.switch_to.window(driver.window_handles[-1])
        wait_for_page_load(driver)
        logging.info("Switched to the second tab")

        time.sleep(random.randint(1, 5))

        email_input = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[2]/div[1]/input")
        email_input.send_keys(username)
        wait_for_page_load(driver)
        logging.info("Email entered")

        time.sleep(random.randint(1, 5))

        password_input = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[2]/div[2]/span/input")
        password_input.send_keys(password)
        wait_for_page_load(driver)
        logging.info("Password entered")

        time.sleep(random.randint(1, 3))

        login_button = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[4]/button[1]")

        if not login_button.is_displayed():
            logging.error("Login button is not visible")
            return False

        try:
            login_button.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", login_button)
            except Exception:
                ActionChains(driver).move_to_element(login_button).click().perform()

        wait_for_page_load(driver)
        logging.info("Login button clicked")

        if driver.find_elements(By.XPATH, "//div[contains(@class, 'dashboard')]"):
            logging.info("Successfully logged in")
            wait_for_page_load(driver)
            close_popups(driver)
        else:
            logging.error("Login was not successful")
            return False

        time.sleep(random.randint(1, 5))

        driver.switch_to.window(driver.window_handles[0])
        wait_for_page_load(driver)
        logging.info("Switched back to extension tab")

        if driver.current_url.startswith('chrome-extension://'):
            logging.info("Successfully returned to extension page")
            driver.refresh()
            wait_for_page_load(driver)
            logging.info("Extension page refreshed")
            time.sleep(random.randint(1, 5))

            close_popups(driver)
            time.sleep(random.randint(1, 5))

            return True
        else:
            logging.error("Failed to return to extension page")
            return False

    except Exception as e:
        logging.error(f"Unexpected error during login: {str(e)}")
        return False


def maintain_session(driver, username):
    """Maintain the session by refreshing the dashboard periodically."""
    attempts = 0
    while attempts < MAX_MAINTENANCE_ATTEMPTS:
        try:
            driver.switch_to.window(driver.window_handles[1])
            logging.info(f"[{username}] Switched to dashboard tab")

            time.sleep(1)

            driver.refresh()
            wait_for_page_load(driver)
            logging.info(f"[{username}] Dashboard page refreshed")

            time.sleep(random.randint(1, 5))

            points_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[1]/div[2]/main/div/div/div[2]/div/div[1]/div[2]/div[1]"))
            )

            points = points_element.text
            logging.info(f"[{username}] Current points: {points}")

            driver.switch_to.window(driver.window_handles[0])
            logging.info(f"[{username}] Switched back to extension tab")

            time.sleep(1)

            driver.refresh()
            wait_for_page_load(driver)
            logging.info(f"[{username}] Extension page refreshed")

            logging.info(f"[{username}] Session maintained successfully")
            return
        except Exception as e:
            attempts += 1
            logging.error(f"[{username}] Error during session maintenance (Attempt {attempts}/{MAX_MAINTENANCE_ATTEMPTS}): {str(e)}")

            if attempts < MAX_MAINTENANCE_ATTEMPTS:
                logging.info(f"[{username}] Retrying session maintenance in {MAINTENANCE_RETRY_DELAY} seconds...")
                time.sleep(MAINTENANCE_RETRY_DELAY)

                try:
                    driver.switch_to.window(driver.window_handles[0])
                    driver.refresh()
                    wait_for_page_load(driver)
                    logging.info(f"[{username}] Returned to extension tab and refreshed")
                except Exception as switch_error:
                    logging.error(f"[{username}] Error switching to extension tab: {str(switch_error)}")
            else:
                logging.error(f"[{username}] Max session maintenance attempts reached. Giving up.")


def run_session_maintenance(driver, interval, username):
    """Run session maintenance in a separate thread.""" 
    while True:
        maintain_session(driver, username)
        time.sleep(interval)


def farm_points(account, proxy):
    """Main function to log in and farm points.""" 
    username, password = account.split(':')
    logging.info(f"[{username}] Starting farm_points function") 
    driver = None 
    login_attempts = 0

    while login_attempts < MAX_LOGIN_ATTEMPTS:
        try:
            if driver: 
                driver.quit()  # Close the previous driver if it exists

            driver = setup_driver(proxy)

            if login_to_extension(driver, username, password): 
                logging.info(f"[{username}] Successfully logged in")

                # Start session maintenance in a separate thread 
                maintenance_thread = threading.Thread(target=run_session_maintenance, args=(driver, SESSION_INTERVAL, username)) 
                maintenance_thread.daemon = True  # Thread will end when the main thread ends 
                maintenance_thread.start()

                # Main farming loop
                while True: 
                    time.sleep(60)  # Pause to prevent CPU overload 
            else:
                raise Exception("Login failed")

        except Exception as e:
            login_attempts += 1
            logging.error(f"[{username}] Error occurred (Attempt {login_attempts}/{MAX_LOGIN_ATTEMPTS}): {str(e)}")

            if login_attempts < MAX_LOGIN_ATTEMPTS:
                logging.info(f"[{username}] Retrying login in {LOGIN_RETRY_DELAY} seconds...") 
                time.sleep(LOGIN_RETRY_DELAY) 
            else:
                logging.error(f"[{username}] Max login attempts reached. Giving up.") 

        finally:
            if driver:
                driver.quit()

    logging.error(f"[{username}] Failed to farm points after {MAX_LOGIN_ATTEMPTS} attempts.")


def main():
    """Main function to run the farming process.""" 
    accounts = load_data(ACCOUNTS_FILE) 
    proxies = load_data(PROXIES_FILE) 

    logging.info(f"Loaded {len(accounts)} accounts and {len(proxies)} proxies") 
    logging.info(f"NUM_THREADS set to {NUM_THREADS}") 

    threads = [] 
    for i in range(min(NUM_THREADS, len(accounts), len(proxies))):
        username = accounts[i].split(':')[0]
        logging.info(f"Starting thread for account: {username}") 
        thread = threading.Thread(target=farm_points, args=(accounts[i], proxies[i])) 
        threads.append(thread) 
        thread.start()

    logging.info(f"Started {len(threads)} threads")

    for thread in threads:
        thread.join()

    logging.info("All threads completed")

if __name__ == "__main__":
    main()
