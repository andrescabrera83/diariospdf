from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from werkzeug.utils import secure_filename
import os
from os import environ
import fitz
import pandas as pd
from dotenv import load_dotenv
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import Spider
from scrapy.http import Request
from pathlib import Path
import uuid
from PyPDF2 import PdfReader
import scrapy
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import tabula



app = Flask(__name__)

# Configure the upload directory
UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Get absolute path of the upload directory
upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
print("Upload directory:", upload_dir)

#get ENVIRONMENT VARIABLES
app.config['IP_ADDRESS'] = environ.get('IP_ADDRESS')
ip_addres = app.config['IP_ADDRESS']



#print("my ip: ", ip_addres)


################################################################################################################

# Function to check if the file extension is allowed
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to retrieve list of PDF files starting with 'highlighted_'
def get_highlighted_pdf_files():
    pdf_folder = app.config['UPLOAD_FOLDER']
    pdf_files = [f for f in os.listdir(pdf_folder) if f.startswith('highlighted_') and f.endswith('.pdf')]
    return pdf_files

###################################################################################################################

# Route to render the upload form
@app.route('/')
def index():
    pdf_files = get_highlighted_pdf_files()
    return render_template('index.html', pdf_files=pdf_files)

####################################################################################################################

# Define Scrapy spider to download PDF and extract text
class PDFSpider(Spider):
    name = 'pdf_spider'
    start_urls = ['https://www.jornalminasgerais.mg.gov.br']

    def __init__(self):
        self.cursor: None
        chrome_options = Options()
        print("init: ", upload_dir)
        prefs = {'download.default_directory':'/home/rdpuser/diariospdf/pdf_highlighter/static'} #UPDATE ADDRESS CORRESPONDING TO THE MACHINE, FOLDER MUST BE NAMED pdf_files
        chrome_options.add_experimental_option('prefs', prefs)
        #chrome_options.add_argument(f"--download.default_directory={prefs}")
        chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=chrome_options)

    def start_requests(self):
        url = self.start_urls[0]
        self.driver.get(url)
        time.sleep(3)
        self.driver.find_element(By.ID, "linkDownloadPDF").click()
        time.sleep(4)
        yield scrapy.Request(url, self.parse)

    def parse(self, response):
        pdf_url = response.xpath('//*[@id="linkDownloadPDF"]/@href').get()
        if pdf_url:
             yield Request(pdf_url, callback=self.save_pdf)
        else:
            self.logger.error('PDF URL not found on the webpage')


    def save_pdf(self, response):
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition:
            
            file_name = content_disposition.split('filename=')[-1].strip('"')
            file_path = os.path.join('/home/rdpuser/diariospdf/pdf_highlighter/static', file_name)
            print("File path found:", file_path)
            with open(file_path, 'wb') as f:
                f.write(response.body)
            
        else:
            print("Content-Disposition header not found. Unable to determine file name.")



####################################################################################################################

@app.route('/display_pdf', methods=['GET', 'POST'])
def display_pdf():
    if request.method == 'POST':
        pdf_filename = request.form.get('pdf_select')
    elif request.method == 'GET':
        pdf_filename = request.args.get('pdf_select')
    
    pdf_folder = app.config['UPLOAD_FOLDER']
    return send_from_directory(pdf_folder, pdf_filename)


#######################################################################################################################

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the post request has the file part
    if 'file' not in request.files:
        return redirect(request.url)
    
    # Get the list of uploaded files
    files = request.files.getlist('file')

    
    
    # Get the value from the textarea
    textarea_value = request.form.get('palavras')
    words_to_highlight = textarea_value.splitlines()
    print(words_to_highlight)
    
    for file in files:
        if file.filename == '':
            continue
        
        if file and allowed_file(file.filename):
            # Save the file to a temporary directory
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Open the PDF file
            doc = fitz.open(file_path)
            
            # Iterate through each page in the PDF
            for page in doc:
                text_instances = page.search_for(' '.join(words_to_highlight), quads=True)
                for inst in text_instances:
                    highlight = page.add_highlight_annot(inst)
                    highlight.update()

            
            # Save the modified PDF with highlights
            output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'highlighted_' + filename)
            doc.save(output_file_path, garbage=4, deflate=True, clean=True)
            
            # Close the PDF document
            doc.close()
            
            # Return the modified PDF as a downloadable file
            return send_file(output_file_path, as_attachment=True, download_name='highlighted_' + filename, mimetype='application/pdf')

             # Render the template with the embedded PDF
            #return 
        else:
            return 'Invalid file format'
        
#######################################################################################################################

# Function to start the Scrapy spider
def run_spider():
    process = CrawlerProcess(settings={
        'USER_AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

    })
    process.crawl(PDFSpider)
    process.start()



if __name__ == "__main__":
    run_spider()  # Start the Scrapy spider
    app.run(host='62.72.9.159', debug=True)
