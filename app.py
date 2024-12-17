from flask import Flask, request, jsonify
from flask_cors import CORS
# import pytesseract
import re
import os
import threading
import requests
import json
from dotenv import load_dotenv    # python-dotenv
import pdfplumber  


load_dotenv()

STATUS_URL = "https://urjjaa-api.assimilate.co.in/api/LabMonitoring/SaveAiTestStaus"
POST_URL = "https://urjjaa-api.assimilate.co.in/api/LabMonitoring/Post"

os.makedirs("downloads", exist_ok=True)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# test_pattern = re.compile(r'^(.*?)\s+(\d+\.?\d*)\s+([a-zA-Z%/]+|thou/mm3|mill/mm3|mL/min/1.73m2)\s+([<>\s0-9.\s-]+)$')
# test_pattern = re.compile(r'^(.*?)\s+(\d+\.?\d*)\s+([a-zA-Z%/.-]+|thou/mm3|mill/mm3|mL/min/1.73m2)\s+([<>\s0-9.-]+)$')

test_pattern = re.compile(
    r'^(.*?\s+)?' 
    r'(\d+\.?\d*\s*\*?|Nil|Light Yellow|Traces(10.0 mg/dL)|Negative|Normal|Few|None seen|3-4 WBC/HPF|Positive|Indeterminate|Abnormal|Out of Range|Mild|Moderate|Severe|Rare|Many|Normal Range|)\s*'
    r'([a-zA-Z%/\*.\^\d/-]+|thou/mm3|mill/mm3|mL/min/1\.73m2|X 10³ / µL|X 10\^6/µL|µIU/mL|mL/min/1.73m2)\s+' 
    r'([<>\s0-9.\*\-\/]*)$'  
)

test_names = [
    "COMPLETE BLOOD COUNT",
    "Differential Leucocyte Count (DLC)",
    "Absolute Leucocyte Count",
    "LIVER & KIDNEY PANEL, SERUM",
    "LIPID SCREEN, SERUM",
    "HbA1c (GLYCOSYLATED HEMOGLOBIN), BLOOD",
    "GLUCOSE, FASTING (F), PLASMA",
    "THYROID PROFILE,TOTAL, SERUM",
    "VITAMIN B12; CYANOCOBALAMIN, SERUM",
    "URINE EXAMINATION, ROUTINE; URINE, R/E",
    "LIPID",
    "LIVER",
    "RENAL",
    "THYROID",
    "DIABETES",
    "COMPLETE HEMOGRAM",
]

@app.route('/UploadDocument', methods=['POST'])
def process_file():
    data = request.json
    if 'fileUrl' not in data or not data['fileUrl']:
        return jsonify({"error": "No fileUrl provided"}), 400

    file_url = data['fileUrl']
    userid = data['userid']
    bookingId = data['bookingId']

    thread = threading.Thread(target=process_pdf_in_background, args=(file_url, userid, bookingId))
    thread.start()

    return jsonify({"message": "(ReportReceived) Processing started", 'id': 3}), 202


def process_pdf_in_background(file_url, userid, bookingId):
    all_data_list = []
    text_content = []
    

    text_file_path = "downloads/extracted_text.txt"
    try:
        response = requests.get(file_url)
        if response.status_code != 200:
            print(f"Failed to download file: {response.status_code}")
            send_status("Download failed", userid,bookingId)
            return

        file_path = os.path.join("downloads", f"temp_{userid}.pdf")

        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"File processing complete. Extracted text saved to {text_file_path}")


        send_status("In-Process", userid, bookingId)

    
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)
                    data_list = process_text(page_text, userid,bookingId)
                    all_data_list.extend(data_list)

        with open(text_file_path, 'w', encoding='utf-8') as text_file:
            text_file.write("\n\n".join(text_content))

        send_status("Completed", userid, bookingId)
        send_extracted_data(all_data_list)

        

    except Exception as e:
        print(f"Error during PDF processing: {e}")
        send_status(f"Processing failed due to: {str(e)}", userid, bookingId)
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


def process_text(text, userid, bookingId):
    matches = test_pattern.findall(text)

    data_list = []
    current_test_name = ""

    lines = text.split('\n')
    for line in lines:
        line = line.strip()

        for test_name in test_names:
            if test_name in line:
                current_test_name = test_name
                break

        match = test_pattern.match(line)
        if match:
            parameter = match.group(1).strip()  
            result = match.group(2)            
            unit = match.group(3)              

            data_dict = {
                "testName": current_test_name,
                "parameter": parameter,
                "value": result,
                "unitName": unit,
                "status": 8,
                "userid": userid,
                "bookingId": bookingId
            }
            data_list.append(data_dict)

    return data_list


def send_status(status_message, userid, bookingId):
    status_payload = {
        "testName": "Antitrypsin",  
        "statusName": status_message,
        "userid": userid,
        "bookingId": bookingId
    }
    status_payload_str = json.dumps(status_payload, ensure_ascii=False)  # This keeps Unicode symbols intact
    print(f"Sending status payload: {status_payload_str}")
    
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(STATUS_URL, data=status_payload_str, headers=headers)  # Send the raw JSON string
        if response.status_code in [200, 202]:
            print("Status sent successfully")
        else:
            print(f"Failed to send status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending status: {e}")


def send_extracted_data(all_data_list):
    payload = {
        "labMonitoringRequest": all_data_list
    }
    
    payload_str = json.dumps(payload, ensure_ascii=False) 
    print(f"Sending full data payload: {payload_str}")
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(POST_URL, data=payload_str, headers=headers) 
        if response.status_code in [200, 202]:
            print("Data sent successfully")
        else:
            print(f"Failed to send data: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data: {e}")


if __name__ == '__main__':
    app.run(debug=False, port=5568)
    
    
# {
#     "fileKey": "2a57488a-d5fa-4cfb-9639-cbf469e618e4_SREEJITH-3.pdf",
#     "fileUrl": "https://at-erp-dev.s3.ap-south-1.amazonaws.com/2a57488a-d5fa-4cfb-9639-cbf469e618e4_SREEJITH-3.pdf?X-Amz-Expires=604800&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIARUFMKKPRR37TQCXV%2F20241111%2Fap-south-1%2Fs3%2Faws4_request&X-Amz-Date=20241111T092913Z&X-Amz-SignedHeaders=host&X-Amz-Signature=ae4847321b47085ca7b8a6536c1ec857aeec691116306ea5e68a483af3af33f8"
# }