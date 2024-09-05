from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf2image import convert_from_path
import pytesseract
import re
import os
import threading
import requests
import json
from dotenv import load_dotenv


load_dotenv()

STATUS_URL = os.getenv('STATUS_URL')
POST_URL = os.getenv('POST_URL') 

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.route('/UploadDocument', methods=['POST'])
def process_file():
    data = request.json
    if 'fileUrl' not in data or not data['fileUrl']:
        return jsonify({"error": "No fileUrl provided"}), 400

    file_url = data['fileUrl']
    userid = data['userid']

    thread = threading.Thread(target=process_pdf_in_background, args=(file_url, userid,))
    thread.start()

    return jsonify({"message": "Processing started"}), 202

def process_pdf_in_background(file_url, userid):
    all_data_list = []
    try:

        response = requests.get(file_url)
        if response.status_code != 200:
            print(f"Failed to download file: {response.status_code}")
            send_status("Download failed", userid)
            return

        file_path = os.path.join("downloads", f"temp_{userid}.pdf")

        with open(file_path, 'wb') as file:
            file.write(response.content)

        pages = convert_from_path(file_path) #Number

        for page_number, page in enumerate(pages):
            page_text = pytesseract.image_to_string(page)

            data_list = process_text(page_text, userid)
            all_data_list.extend(data_list)

        
        send_status("Completed", userid)
        send_extracted_data(all_data_list)
        
        #print(f"File processing complete")
        
    except Exception as e:
        print(f"Error during PDF processing: {e}")
        send_status("Processing failed", userid)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
 
       


def send_status(status_message, userid):
    status_payload = {
        "testName": "Antitrypsin",
        "statusName": status_message,
        "userid": userid
    }
    status_payload_str = json.dumps(status_payload)
    print(f"Sending status payload: {status_payload_str}")
    print(f"Successfully send status payload:")
    
    try:
        response = requests.post(STATUS_URL, json=status_payload)
        if response.status_code in [200, 202]:
            print("Status sent successfully")
        else:
            print(f"Failed to send status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending status: {e}")

def process_text(text, userid):
    pattern = r"(\b[A-Z ]+\s*\([A-Z]+\)\s*[A-Z.]*|[\w\s-]+)\s+([A-Z.]+\s*[A-Z]*)\s+([\d.]+)\s+(\S+)"
    matches = re.findall(pattern, text, re.DOTALL)

    data_list = []
    for match in matches:
        value_str = match[2].strip()
        try:
            if '.' in value_str:
                value = float(value_str)
            else:
                value = int(value_str) 
        except ValueError:
            value = 0  

        data_dict = {
            "testName": match[0].strip(),
            "value": value,  
            "unitName": match[3].strip(),
            "status": 8,
            "userid": userid
        }
        data_list.append(data_dict)
    return data_list

def send_extracted_data(all_data_list):
    payload = {
        "labMonitoringRequest": all_data_list
    }
    
    payload_str = json.dumps(payload)
    print(f"Sending full data payload: {payload_str}")
    print(f"Successfully send full data payload ")

    try:
        response = requests.post(POST_URL, json=payload)
        if response.status_code in [200, 202]:
            print("Data sent successfully")
        else:
            print(f"Failed to send data: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data: {e}")

if _name_ == '__main__':
    os.makedirs("downloads", exist_ok=True)
    app.run(debug=False, port=5568)