import os
import queue
import base64
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("PDFDownloader")

task_list = []

def pdf_worker(worker_id: int, task_queue: queue.Queue):
    logger.debug(f"[Worker-{worker_id}] Started")

    chrome_options = Options()
    # Eager strategy: waits for DOMContentLoaded, not full assets. 
    # We handle fonts/complete state in our custom script.
    chrome_options.page_load_strategy = 'eager'
    
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage") # Critical for docker
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    
    # Low-resource & Performance Tuning
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--no-zygote") 
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--safebrowsing-disable-auto-update")
    chrome_options.add_argument("--disable-features=VizDisplayCompositor")
    chrome_options.add_argument("--disk-cache-size=0") # Disable disk cache
    
    # Suppress logging
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--silent")

    service = Service(log_output=os.devnull)

    def init_driver():
        return webdriver.Chrome(service=service, options=chrome_options)

    driver = None
    try:
        driver = init_driver()
        driver.set_page_load_timeout(60) # Prevent zombies
        driver.set_script_timeout(60)
    except Exception as e:
        logger.error(f"[Worker-{worker_id}] Init failed: {e}")
        return

    processed_count = 0
    
    try:
        while True:
            # Restart driver periodically to release memory leaks
            if processed_count > 0 and processed_count % 50 == 0:
                logger.debug(f"[Worker-{worker_id}] Recycling driver to free memory...")
                try:
                    driver.quit()
                except:
                    pass
                driver = init_driver()
                driver.set_page_load_timeout(60)
                driver.set_script_timeout(60)

            try:
                task = task_queue.get(timeout=1)
            except queue.Empty:
                continue

            if task is None:
                task_queue.task_done()
                break

            url, final_path = task
            start_time = time.time()
            
            if os.path.exists(final_path):
                try:
                    os.remove(final_path)
                except OSError:
                    pass

            target_dir = os.path.dirname(final_path)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)
            
            # logger.debug(f'[Worker-{worker_id}] Downloading {final_path} from {url}')
    
            try:
                driver.get(url)
                
                # Custom wait for stability + fonts
                driver.execute_async_script("""
                    var callback = arguments[arguments.length - 1];
                    var start = Date.now();
                    
                    function check() {
                        if (document.readyState === 'complete' && document.fonts.status === 'loaded') {
                            requestAnimationFrame(() => requestAnimationFrame(callback));
                        } else if (Date.now() - start > 30000) {
                             callback();
                        } else {
                            setTimeout(check, 100);
                        }
                    }
                    
                    if (document.readyState === 'complete') {
                        document.fonts.ready.then(() => {
                            requestAnimationFrame(() => requestAnimationFrame(callback));
                        });
                    } else {
                        window.addEventListener('load', () => {
                            document.fonts.ready.then(() => {
                                requestAnimationFrame(() => requestAnimationFrame(callback));
                            });
                        });
                    }
                """)

                pdf_params = {
                    "printBackground": True,
                    "paperWidth": 8.27,
                    "paperHeight": 11.69,
                    "marginTop": 1.0,
                    "marginBottom": 1.0,
                    "marginLeft": 0.75,
                    "marginRight": 0.75,
                    "preferCSSPageSize": True
                }
                
                result = driver.execute_cdp_cmd("Page.printToPDF", pdf_params)
                
                with open(final_path, "wb") as f:
                    f.write(base64.b64decode(result['data']))

                elapsed = time.time() - start_time
                rel_path = os.path.relpath(final_path, os.getcwd())
                logger.info(f"[Worker-{worker_id}] [OK] {elapsed:.2f}s | {rel_path}")

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[Worker-{worker_id}] [FAIL] {elapsed:.2f}s | {url} | Error: {e}")

            processed_count += 1
            task_queue.task_done()

    except Exception as e:
        logger.critical(f"[Worker-{worker_id}] Critical Error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        logger.debug(f"[Worker-{worker_id}] Finished.")

def add_task(task):
    task_list.append(task)

def start_tasks(max_threads: int = int(os.getenv('MAX_THREADS', 4))):
    logger.info(f"--- Task Start: {len(task_list)} URLs | Max Concurrency {max_threads} ---")
    task_queue = queue.Queue()
    for item in task_list:
        if os.path.exists(item[1]):
            try:
                os.remove(item[1])
            except OSError:
                pass
        task_queue.put(item)
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        for i in range(max_threads):
            executor.submit(pdf_worker, i, task_queue)
        task_queue.join()
        for _ in range(max_threads):
            task_queue.put(None)
    logger.info("--- All Tasks Completed ---")
