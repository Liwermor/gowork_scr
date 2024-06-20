import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import schedule
from datetime import datetime
from PIL import Image, ImageDraw

# Konfiguracja email
EMAIL_ADDRESS = 'aaaaaa@gmail.com'
EMAIL_PASSWORD = 'bbbbbb'

# URL strony GoWork
GOWORK_URL = 'https://www.gowork.pl/opinie_czytaj,[thread id]'

# Plik do przechowywania ostatniego sprawdzonego wpisu
LAST_ENTRY_FILE = 'last_entry.txt'

# Plik z adresami email odbiorców
RECIPIENTS_FILE = 'recipients.txt'

def load_recipients(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]

def send_email(subject, body, attachment_path=None):
    recipients = load_recipients(RECIPIENTS_FILE)
    for recipient in recipients:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = recipient
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        if attachment_path:
            with open(attachment_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(attachment_path)}')
                msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, recipient, text)
        server.quit()

def get_last_entry():
    if os.path.exists(LAST_ENTRY_FILE):
        with open(LAST_ENTRY_FILE, 'r') as file:
            return file.read().strip()
    return None

def save_last_entry(entry):
    with open(LAST_ENTRY_FILE, 'w') as file:
        file.write(entry)

def take_full_page_screenshot(driver, file_path, highlight_element=None):
    # Calculate total width and height of the page
    total_width = driver.execute_script("return document.body.scrollWidth")
    total_height = driver.execute_script("return document.body.scrollHeight")

    # Set the window size to the total width and height of the page
    driver.set_window_size(total_width, total_height)

    # Take screenshot
    driver.save_screenshot(file_path)

    if highlight_element:
        left = highlight_element.location['x']
        top = highlight_element.location['y']
        right = left + highlight_element.size['width']
        bottom = top + highlight_element.size['height']

        # Open the image and draw a rectangle around the element
        image = Image.open(file_path)
        draw = ImageDraw.Draw(image)
        draw.rectangle([left, top, right, bottom], outline="red", width=5)
        image.save(file_path)

def extract_entries(soup):
    entries = []
    threads = soup.find_all('div', class_='js-thread thread-item clearfix')
    for thread in threads:
        entries.append(thread)
        replies_list = thread.find('div', class_='review-replies-list')
        if replies_list:
            replies = replies_list.find_all('div', class_='review')
            entries.extend(replies)
    return entries

def check_gowork():
    print("Sprawdzanie nowego wpisu na GoWork...")
    options = FirefoxOptions()
    options.add_argument('--headless')

    driver = webdriver.Firefox(service=FirefoxService(), options=options)
    driver.get(GOWORK_URL)

    try:
        # Poczekaj, aż wpisy będą widoczne na stronie
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'js-threads'))
        )
    except:
        print("Timeout: Elementy nie zostały załadowane.")
        driver.quit()
        return

    time.sleep(5)  # Dodatkowe czekanie na załadowanie strony

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    entries = extract_entries(soup)
    print(f"Liczba znalezionych wpisów: {len(entries)}")

    if entries:
        latest_entry = None
        latest_entry_date = None

        for entry in entries:
            date_element = entry.find('time', class_='review__date')
            if date_element:
                entry_date_str = date_element['datetime']
                entry_date = datetime.strptime(entry_date_str, '%d.%m.%Y %H:%M')
                #print(f"Znaleziono wpis z datą: {entry_date_str}, parsed: {entry_date}")

                if not latest_entry_date or entry_date > latest_entry_date:
                    latest_entry_date = entry_date
                    latest_entry = entry

        if latest_entry:
            user_name = latest_entry.find('span', class_='author__nick').get_text(strip=True)
            review_date = latest_entry.find('time', class_='review__date')['datetime']
            review_time = latest_entry.find('time', class_='review__date').get_text(strip=True)
            review_text = latest_entry.find('p', class_='js-review-text').get_text("\n", strip=True)

            latest_entry_text = f"Użytkownik: {user_name}\nData: {review_date}\n\n{review_text}"
            last_entry = get_last_entry()

            #print(f"Ostatni zapisany wpis: {last_entry}")
            #print(f"Najnowszy znaleziony wpis: {latest_entry_text}")

            if latest_entry_text != last_entry:
                screenshot_path = 'gowork_screenshot.png'
                element = driver.find_element(By.XPATH, f"//*[contains(text(), '{review_text[:30]}')]")
                take_full_page_screenshot(driver, screenshot_path, element)

                subject = 'Nowy wpis na GoWork'
                body = f'Pojawił się nowy wpis na stronie GoWork: {GOWORK_URL}.\n\nTreść wpisu:\n{latest_entry_text}'
                send_email(subject, body, screenshot_path)

                save_last_entry(latest_entry_text)
                print("Nowy wpis znaleziony i wysłany.")

            else:
                print("Brak nowych wpisów.")
        else:
            print("Nie znaleziono żadnych wpisów z poprawną datą.")
    else:
        print("Nie znaleziono żadnych wpisów.")

    driver.quit()

# Wyślij mail testowy po uruchomieniu
def send_test_email():
    subject = 'Testowy email'
    body = 'To jest testowy email po uruchomieniu skryptu.'
    last_entry = get_last_entry()
    if last_entry:
        body += f'\n\nOstatni wpis:\n{last_entry}'
    send_email(subject, body)

# Harmonogram co minutę
schedule.every(1).minutes.do(check_gowork)

if __name__ == '__main__':
    send_test_email()
    print("Skrypt uruchomiony, wysłano testowy email.")
    while True:
        schedule.run_pending()
        time.sleep(1)

