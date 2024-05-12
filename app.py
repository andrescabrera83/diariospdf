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

from unidecode import unidecode

import re

from collections import defaultdict
from multiprocessing import Pool, Manager
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

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

def page_counting(file_path):
    
    doc = fitz.open(file_path)
    total_pages = doc.page_count
    doc.close()
    
    return total_pages

def text_formatting_a(words):
    #there are several situations me might encounter when dealing with formatting texts.
    # inside quotation marks, with empty characters or with accents.
    #lets first try to resolve quotation makrs:
    
    # Remove quotation marks and white spaces from each word
    words_formatted = [word.replace('"', '').replace("'", '').strip() for word in words]
    
    words_formatted.sort()
    
    
    return words_formatted
    

def text_formatting_b(words):
    
    processed_words = []
    
    # add to the list a no accent version of any version that contains any accent
    for word in words:
        noaccent_word = unidecode(word)
        processed_words.append(noaccent_word)
        
    words.extend(processed_words)
    words.sort()
    
    # Convert each word to uppercase using list comprehension
    words_upper = [word.upper() for word in words]
            
    return words_upper


def search_matches(chunk, file_path, words_to_highlight):
    """
    Search for matches in a chunk of pages.
    
    Args:
        chunk (tuple): Tuple containing the start and end page numbers of the chunk.
        file_path (str): Path to the PDF file.
        words_to_highlight (list): List of words to search for.
        
    Returns:
        list: List of matches found in the chunk.
    """
    
    start_page, end_page = chunk
    unique_matches = []
    unique_bbox = set()
    
    if os.path.exists(file_path):
    
        doc = fitz.open(file_path)
        
        
        
       
        
        for page_number in range(start_page, end_page + 1):
            page = doc.load_page(page_number - 1)  # Page numbers are 0-indexed
            text = page.get_text()
            page_matches = set()
            for keyword in words_to_highlight:
                regex = r'\b{}\b'.format(re.escape(keyword))
                for match in re.finditer(regex, text, re.IGNORECASE):
                    
                    #unifythem 
                    
                    position_info = (match.start(), match.end())
                    if position_info not in page_matches:
                        page_matches.add(position_info)
                        matched_text = match.group()
                        if re.search(r'\b{}\b'.format(re.escape(matched_text)), text, re.IGNORECASE):
                            occurrences = page.search_for(matched_text)
                            for bbox in occurrences:
                                    if bbox not in unique_bbox:
                                        unique_bbox.add(bbox)
                                    
                                            
                                        unique_matches.append((matched_text, page_number, bbox))
                                        
                                        
                                    

                         
    return unique_matches



def divide_into_chunks(total_pages, num_chunks):
    """
    Divide the total number of pages into chunks, adjusting for the remainder.
    
    Args:
        total_pages (int): Total number of pages in the PDF file.
        num_chunks (int): Number of chunks to divide the pages into.
        
    Returns:
        list: List of tuples containing the start and end page numbers of each chunk.
    """
    chunk_size = total_pages // num_chunks
    remainder = total_pages % num_chunks  # Calculate the remainder
    chunks = []
    start_page = 1
    for i in range(num_chunks):
        end_page = start_page + chunk_size - 1
        if i < remainder:
            end_page += 1  # Distribute the remainder pages among the first few chunks
        chunks.append((start_page, end_page))
        start_page = end_page + 1
    return chunks

################################################################################################################

@app.route('/upload', methods=['POST'])
def upload_file():

    
     # Record the start time
    start_time = time.time()
    
    
    keywords = request.form.get('palavras-chaves')
    splited = keywords.splitlines()
    words_to_highlight_a = text_formatting_a(splited)
    words_to_highlight = text_formatting_b(words_to_highlight_a)
    
    # print(words_to_highlight)
    
    keyword_info = []
    
    #select name file
    file_names = request.form.getlist('file_names[]')
    
    for fn in file_names:
        if fn:
            #print(fn)
            pass
        else:
            print("no file names")
            
        # Construct the file path
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
        #print("file path is: ", file_path)
            
            
    
        num_chunks = 3  # Number of chunks to divide the PDF file into
        total_pages = page_counting(file_path=file_path)
        chunks = divide_into_chunks(total_pages, num_chunks)
        
        if os.path.exists(file_path):
            
            # Initialize a dictionary to store page numbers where each keyword is found
            keyword_pages = {keyword: [] for keyword in words_to_highlight}
            # Initialize a dictionary to store the count of occurrences of each keyword
            keyword_counts = {keyword: 0 for keyword in words_to_highlight}
            
        
            # Create a multiprocessing Pool
            with Pool() as pool:
                # Search for matches in each chunk of pages concurrently
                results = pool.starmap(search_matches, [(chunk, file_path, words_to_highlight) for chunk in chunks])
                
            # # Flatten the list of matches
            all_matches = [match for sublist in results for match in sublist]
            
            
            
                
                
            # Open the PDF file and add highlights
            doc = fitz.open(file_path)
            for matched_text, page_number, bbox in all_matches:
                page = doc.load_page(page_number - 1)
                highlight = page.add_highlight_annot(bbox)  # Yellow color
                #print(matched_text, " ", keyword_pages, " ", keyword_counts)
                highlight.update()
                
                # If keyword is found, increment the count for the keyword
                keyword_counts[matched_text.upper()] += 1
                #print(keyword_counts)
                # Add the page number to the list of pages where the keyword was found
                if page_number not in keyword_pages[matched_text.upper()]:
                    keyword_pages[matched_text.upper()].append(page_number)
                
                    # Append keyword information to the keyword_info list
                
                
            for keyword, pages in keyword_pages.items():
                    found = bool(pages)
                    count = keyword_counts[keyword]  # Get the count from keyword_counts
                    keyword_info.append({"keyword": keyword, "found": found, "count": count, "pages": pages})
                    
            
            
            #here
            
            # Encode the keyword information into the URL parameters
            keyword_info_encoded = "&".join([f"keyword={info['keyword']}&count={info['count']}&found={info['found']}&pages={info['pages']}" for info in keyword_info])
            
            
            # Save the modified PDF with highlights
            output_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'marcado_' + fn)
            doc.save(output_file_path, garbage=4, deflate=True, clean=True)
            
            doc.close()
            
            
                
            # Record the end time
            end_time = time.time()
                
            # Calculate the elapsed time
            elapsed_time = end_time - start_time
            print("novo algoritmo: tempo de demora com multiprocessing: ", elapsed_time)
            
            # Redirect to a route to render a template with a download button
            return redirect(url_for('render_download_page', filename='marcado_' + fn, keyword_info=keyword_info_encoded))   
            
        else:
            return 'Invalid file format'
            

        
        

@app.route('/upload2', methods=['POST'])
def upload_file2():

   

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

            for keyword in words_to_highlight:

                 # Construct the regular expression pattern for whole-word matching
                regex = r'\b{}\b'.format(re.escape(keyword))
                print(regex)
                for page_number, page in enumerate(doc, start=1):

                    # Search for the keyword on the page using regular expression
                    matches = re.finditer(regex, page.get_text(), re.IGNORECASE)
                    print(matches)
                    
                    for match in matches:
                        # If keyword is found, increment the count for the keyword
                        keyword_counts[keyword] += 1
                        print(keyword_counts)
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
                            print(occurrences) 
                            # Iterate through each occurrence and highlight it
                            for bbox in occurrences:
                                print(bbox)
                                # Highlight the keyword on the page
                                # Highlight the keyword on the page with yellow color
                                highlight = page.add_highlight_annot(bbox)  # Yellow color
                                print(highlight)
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
    #print("this: ",keyword_info)
    
    return render_template('displayer.html', filename=filename, keyword_info=keyword_info)
            

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True, download_name=filename, mimetype='application/pdf')
        

#host='62.72.9.159'


if __name__ == "__main__":

    app.run(host='62.72.9.159')
