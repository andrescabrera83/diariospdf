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
from datetime import datetime, timedelta

from urllib.parse import urlparse, parse_qs
from urllib.parse import urlencode

import re



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

host='62.72.9.159'



#print("my ip: ", ip_addres)


################################################################################################################

# Function to check if the file extension is allowed
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to retrieve list of PDF files starting with 'highlighted_'
def get_jmg_files():
    pdf_folder = app.config['UPLOAD_FOLDER']
    jmg_files = [f for f in os.listdir(pdf_folder) if f.startswith('caderno1') and f.endswith('.pdf')]
    
    return jmg_files

def get_dou_files():
    today = datetime.today().strftime('%Y_%m')
    pdf_folder = app.config['UPLOAD_FOLDER']
    dou_files = [f for f in os.listdir(pdf_folder) if f.startswith(today) and f.endswith('.pdf')]
    print("here: ", dou_files)

    return dou_files

def get_jmg_file_today():
    pdf_folder = app.config['UPLOAD_FOLDER']
    # Get today's date
    today = datetime.today().strftime('%Y-%m-%d')
     # Construct the filename pattern
    filename_pattern = f'caderno1_{today}.pdf'
    print(filename_pattern)
     # Filter PDF files based on the filename pattern
    today_jmg_file = [f for f in os.listdir(pdf_folder) if f.startswith('caderno1') and f.endswith(f'_{today}.pdf')]
    
    return today_jmg_file

def get_dou_file_today():
    pdf_folder = app.config['UPLOAD_FOLDER']
    # GEt Today´s Date
    today = datetime.today().strftime('%Y_%m_%d')
    # Construct the filename pattern
    filename_pattern = f'{today}_ASSINADO_do1.pdf'

    today_dou_file = [f for f in os.listdir(pdf_folder) if f.startswith(today) and f.endswith('.pdf')]

    return today_dou_file

###################################################################################################################

# Route to render the upload form
@app.route('/')
def index():
    
    jmg_files = get_jmg_files()
    dou_files = get_dou_files()
    today_jmg_file = get_jmg_file_today()
    today_dou_file = get_dou_file_today()
    return render_template('index2.html', jmg_files=jmg_files, dou_files=dou_files, today_jmg=today_jmg_file, today_dou=today_dou_file )



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

# Function to preprocess input text
def preprocess_input(text):
    # Replace any non-standard line breaks with standard '\n'
    text = re.sub(r'\r\n|\r', '\n', text)
    # Remove any trailing punctuation marks from each line
    lines = text.split('\n')
    lines = [line.rstrip('.').strip() for line in lines]
    # Join the lines back together with '\n' separator
    preprocessed_text = '\n'.join(lines)
    return preprocessed_text

    ################################################################################################################

@app.route('/upload', methods=['POST'])
def upload_file():

    #select diario
    select_diario = request.form.get('select-diario-input')
    print(select_diario)

     #select keywords
    keywords = request.form.get('palavras-chaves')
    words_to_highlight = keywords.splitlines()
    print(words_to_highlight)

    # Create a list to store information about each keyword
    keyword_info = []


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

            # Initialize a dictionary to store page numbers where each keyword is found
            keyword_pages = {keyword: [] for keyword in words_to_highlight}
            # Initialize a dictionary to store the count of occurrences of each keyword
            keyword_counts = {keyword: 0 for keyword in words_to_highlight}

            # Iterate through each page in the PDF
            for page_number, page in enumerate(doc, start=1):
                # Iterate through each keyword
                for keyword in words_to_highlight:
    
                    # Construct the regular expression pattern for whole-word matching
                    regex = r'\b{}\b'.format(re.escape(keyword))
                    
                    # Search for the keyword on the page using regular expression
                    matches = re.finditer(regex, page.get_text(), re.IGNORECASE)
                    
                    for match in matches:
                        # If keyword is found, increment the count for the keyword
                        keyword_counts[keyword] += 1
                        # Add the page number to the list of pages where the keyword was found
                        if page_number not in keyword_pages[keyword]:
                            keyword_pages[keyword].append(page_number)
                        
                        
                        # Get the start and end indices of the match
                        start_index, end_index = match.span()
                        
                         # Get the text of the match
                        matched_text = match.group()
                        # Add the keyword to highlight only if it's a standalone word
                        if re.search(r'\b{}\b'.format(re.escape(matched_text)), page.get_text(), re.IGNORECASE):
                            # Find the bounding box of the matched text on the page
                            occurrences = page.search_for(matched_text)   
                            # Iterate through each occurrence and highlight it
                            for bbox in occurrences:
                                # Highlight the keyword on the page
                                # Highlight the keyword on the page with yellow color
                                highlight = page.add_highlight_annot(bbox)  # Yellow color
                                highlight.update()
                                
    
            #save the modified pdf with highlights

            output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'marcado_' + fn)
            doc.save(output_file_path, garbage=4, deflate=True, clean=True)

            # Close the PDF document
            doc.close()

            # Append keyword information to the keyword_info list
            for keyword, pages in keyword_pages.items():
                found = bool(pages)
                count = keyword_counts[keyword]  # Get the count from keyword_counts
                keyword_info.append({"keyword": keyword, "found": found, "count": count, "pages": pages})
                print(keyword_info)


            # Encode the keyword information into the URL parameters
            keyword_info_encoded = "&".join([f"keyword={info['keyword']}&count={info['count']}&found={info['found']}&pages={info['pages']}" for info in keyword_info])

           # Redirect to a route to render a template with a download button
            return redirect(url_for('render_download_page', filename='marcado_' + fn, keyword_info=keyword_info_encoded))

        else:
            return 'Invalid file format'
        

        
@app.route('/pdf-marcado/<filename>')
def render_download_page(filename):
     # Get the encoded keyword information from the URL parameters
    keyword_info_encoded = request.args.get('keyword_info', '')
    # Decode the keyword information into a dictionary
    keyword_info = parse_qs(keyword_info_encoded)
    print("this: ",keyword_info)
    
    return render_template('displayer.html', filename=filename, keyword_info=keyword_info)
            

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True, download_name=filename, mimetype='application/pdf')
        

#host='62.72.9.159'


if __name__ == "__main__":

    app.run(debug=True)
