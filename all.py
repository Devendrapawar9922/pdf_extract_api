from flask import Flask, request, jsonify
import pytesseract
from PIL import Image
import re
import tempfile
import os
from pdf2image import convert_from_path

app = Flask(__name__)

def extract_data_from_image(image):
    text = pytesseract.image_to_string(image)
    test_data = []
    pattern = r"([\w\s]+)\s+([\d.]+)\s+([a-zA-Z/%]+)"
    
    for line in text.split('\n'):
        match = re.match(pattern, line)
        if match:
            test_name, value, unit = match.groups()
            test_data.append({
                "test_name": test_name.strip(),
                "value": value.strip(),
                "unit": unit.strip()
            })
    
    return test_data

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        file_path = temp_pdf.name
        file.save(file_path)

    test_data = []
    try:
        images = convert_from_path(file_path)  

        output_dir = "./extracted_images"
        os.makedirs(output_dir, exist_ok=True)

        for i, image in enumerate(images):
            page_data = extract_data_from_image(image)
            test_data.extend(page_data)
            
            project_image_path = os.path.join(output_dir, f"page_{i + 1}.png")
            image.save(project_image_path)

        return jsonify(test_data)
    finally:
        os.remove(file_path)  
if __name__ == '__main__':
    app.run(debug=True, port=5050)
