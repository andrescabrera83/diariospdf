from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
import os
import fitz
from werkzeug.utils import secure_filename


app = Flask(__name__)

# Configure the upload directory
UPLOAD_FOLDER = 'static'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to check if the file extension is allowed
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to retrieve list of PDF files starting with 'highlighted_'
def get_highlighted_pdf_files():
    pdf_folder = app.config['UPLOAD_FOLDER']
    pdf_files = [f for f in os.listdir(pdf_folder) if f.startswith('highlighted_') and f.endswith('.pdf')]
    return pdf_files

# Route to render the upload form
@app.route('/')
def index():
    pdf_files = get_highlighted_pdf_files()
    return render_template('index.html', pdf_files=pdf_files)

@app.route('/display_pdf', methods=['GET', 'POST'])
def display_pdf():
    if request.method == 'POST':
        pdf_filename = request.form.get('pdf_select')
    elif request.method == 'GET':
        pdf_filename = request.args.get('pdf_select')
    
    pdf_folder = app.config['UPLOAD_FOLDER']
    return send_from_directory(pdf_folder, pdf_filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the post request has the file part
    if 'file' not in request.files:
        return redirect(request.url)
    
    # Get the list of uploaded files
    files = request.files.getlist('file')
    
    # Get the value from the textarea
    textarea_value = request.form.get('palavras')
    words_to_highlight = textarea_value.split()
    
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
                # Iterate through each word to highlight
                for word in words_to_highlight:
                    # Search for the word on the page
                    text_instances = page.search_for(word)
                    # Highlight the word
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
        


if __name__ == "__main__":
    app.run(debug=True)
