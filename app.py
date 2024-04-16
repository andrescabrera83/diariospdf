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

diario_folder = 'DOU-MG'

DIARIO_FOLDER = os.path.join('static', diario_folder)

UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DIARIO_FOLDER'] = DIARIO_FOLDER

# Get absolute path of the upload directory
upload_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
print("Upload directory:", upload_dir)

#get ENVIRONMENT VARIABLES
app.config['IP_ADDRESS'] = environ.get('IP_ADDRESS')
ip_addres = app.config['IP_ADDRESS']

host='62.72.9.159'



#print("my ip: ", ip_addres)


################################################################################################################

# Function to check if the file extension is allowed
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to retrieve list of PDF files starting with 'highlighted_'
def get_highlighted_pdf_files():
    pdf_folder = app.config['UPLOAD_FOLDER']
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith('.pdf')]
    
    return pdf_files

###################################################################################################################

# Route to render the upload form
@app.route('/')
def index():
    diario_path = app.config['DIARIO_FOLDER']
    dp_specific = diario_path.split("/")[-1] 
    pdf_files = get_highlighted_pdf_files()
    return render_template('index2.html', pdf_files=pdf_files, diario_path=dp_specific)

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

    #select diario
    select_diario = request.form.get('select-diario-input')
    print(select_diario)

     #select keywords
    keywords = request.form.get('palavras-chaves')
    words_to_highlight = keywords.splitlines()
    print(words_to_highlight)

    #select name file
    file_names = request.form.getlist('file_names[]')
    
    for fn in file_names:
        if fn:
            print(fn)
        else:
            print("no file names")

        # Construct the file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
        print("file path is: ", file_path)

        if os.path.exists(file_path):
            #open the pdf file
            doc = fitz.open(file_path)

             # Iterate through each page in the PDF
            for page in doc:
                # Iterate through each keyword
                for keyword in words_to_highlight:
                    # Search for the keyword on the page
                    text_instances = page.search_for(keyword, quads=True)
                    for inst in text_instances:
                        highlight = page.add_highlight_annot(inst)
                        highlight.update()
    
            #save the modified pdf with highlights

            output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'highlighted_' + fn)
            doc.save(output_file_path, garbage=4, deflate=True, clean=True)

            # Close the PDF document
            doc.close()

            #return the modified PDF as a downloadable file
            return send_file(output_file_path, as_attachment=True, download_name='highlighted_' + fn, mimetype='application/pdf')

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
    #run_spider()  # Start the Scrapy spider
    app.run( debug=True)
