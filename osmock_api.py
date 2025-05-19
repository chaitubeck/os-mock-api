import openai
from openai import OpenAI
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from faker import Faker
from datetime import datetime, timedelta
import random
import uuid
import os
import json,pathlib
from ragie import RagieInference



# Load OpenAI key once 🔧
with open("gpt-key.txt", "r") as f:
    api_key = f.read().strip()

client = OpenAI(api_key=api_key)  # 🔧 move to global scope

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fake = Faker()

# Mock classes
class Patient:
    def __init__(self, patient_id):
        self.patient_id = patient_id
        self.name = fake.name()
        self.dob = str(fake.date_of_birth(minimum_age=18, maximum_age=90))
        self.gender = random.choice(["Male", "Female"])
        self.zip_code = fake.zipcode()
        self.state = fake.state_abbr()

class Prescription:
    def __init__(self, patient_id):
        self.rx_number = random.randint(10000, 99999)
        self.patient_id = patient_id
        self.drug_name = random.choice(["Atorvastatin", "Levothyroxine", "Lisinopril", "Metformin", "Amlodipine"])
        self.order_status = random.choice(["Pending", "Shipped", "Delivered", "Cancelled"])
        self.refill_total = random.randint(1, 5)
        self.current_refill = random.randint(0, self.refill_total)

patients = [Patient(i) for i in range(1, 101)]
prescriptions = [Prescription(p.patient_id) for p in patients for _ in range(random.randint(1, 3))]

@app.get("/patients")
def get_patients():
    return [vars(p) for p in patients]

@app.get("/prescriptions")
def get_prescriptions(patient_id: int = Query(...)):
    return [vars(rx) for rx in prescriptions if rx.patient_id == patient_id]

@app.get("/patient-detail")
def get_patient_detail(patient_id: int = Query(...)):

    # Load mock data from file
    mock_file = pathlib.Path(__file__).parent / "patients_with_all_event_types.json"
    with open(mock_file, "r") as f:
        mock_data = json.load(f)

    # Match patient_id in the mock file (IDs start from 1)
    matching = next((entry for entry in mock_data if entry["patientId"] == patient_id), None)

    if not matching:
        return {"error": f"No mock data found for patientId {patient_id}"}

    detailed_json = matching

    ragie = RagieInference("ragie_schema.json")
    result = ragie.extract(detailed_json)
    print(result)


    prompt = build_openai_prompt(result)

    response = client.chat.completions.create(
        #model="gpt-4",
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for doctors."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=300
    )

    summary = response.choices[0].message.content.strip()
    return {**result, "summary": summary}



def build_openai_prompt(ragie_result):
    prompt = (
            "You are a helpful assistant for doctors.\n"
            "Given the following structured prescription summary, write a 2-line summary a doctor can quickly understand. No technical codes or IDs.\n\n"
            "Example:\n"
            "- Status: Billing Failed\n"
            "- Urgency: High\n"
            "- Reason: Insurance approved\n"
            "- Recommended Action: Verify the billing error and correct mismatched codes\n"
            " Prescription **billing failed** due to a **code mismatch**. Verify and correct the codes for billing to proceed urgently.\n\n"
            f"- Status: {ragie_result['status']}\n"
            f"- Urgency: {ragie_result['urgency']}\n"
            f"- Reason: {ragie_result['reason']}\n"
            f"- Recommended Action: {ragie_result['recommended_action']}\n"
        )

    return prompt

@app.post("/feedback")
def receive_feedback(feedback: dict):
    with open("feedback_log.jsonl", "a") as f:
        f.write(json.dumps(feedback) + "\n")
    return {"message": "Feedback received"}



