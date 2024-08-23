from flask import Flask, request, jsonify
from pdf2image import convert_from_path
import pytesseract
import re
import os


pytesseract.pytesseract.tesseract_cmd = r'C:\DATA SCIENCE\AT_SETUPS\tesseract_setup\tesseract.exe'

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        file_path = os.path.join("uploads", file.filename)
        file.save(file_path)
        text = extract_text_from_pdf(file_path)  
        data_list = process_text(text)  
        return jsonify(data_list), 200

def extract_text_from_pdf(pdf_path):
    pages = convert_from_path(pdf_path)
    text = ""
    for page_number, page in enumerate(pages):
        page_text = pytesseract.image_to_string(page)
        text += page_text
        print(f"Extracted text from page {page_number + 1}")
    return text

def process_text(text):
    pattern = r"(\b[A-Z ]+\s*\([A-Z]+\)\s*[A-Z.]*|[\w\s-]+)\s+([A-Z.]+\s*[A-Z]*)\s+([\d.]+)\s+(\S+)"
    matches = re.findall(pattern, text, re.DOTALL)

    data_list = []
    for match in matches:
        data_dict = {
            'TEST NAME': match[0].strip(),
            'TECHNOLOGY': match[1].strip(),
            'VALUE': match[2].strip(),
            'UNITS': match[3].strip()
        }
        data_list.append(data_dict)
    return data_list

if __name__ == '__main__':
    os.makedirs("uploads", exist_ok=True)
    app.run(debug=True)