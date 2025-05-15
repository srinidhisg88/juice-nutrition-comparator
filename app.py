import os
import json
import base64
import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import google.generativeai as genai

load_dotenv()

app = FastAPI()

# Load Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable not set")
genai.configure(api_key=GEMINI_API_KEY)

# PostgreSQL DB connection info
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
    raise RuntimeError("Database environment variables not fully set")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fetch_alternatives(nutrition):
    """
    Returns healthier juice alternatives based on:
    - Lower sugar and calories
    - Higher or equal vitamin C (or NULL)
    - No preservatives
    """
    conn = connect_db()
    cursor = conn.cursor()
    query='''SELECT name, brand, sugar_g, calories_kcal, vitamin_c_mg, has_preservatives
FROM juices
WHERE sugar_g <= %s + 5
  AND calories_kcal <= %s + 20
  AND (vitamin_c_mg IS NULL OR vitamin_c_mg >= %s - 10)
ORDER BY has_preservatives ASC, sugar_g ASC, calories_kcal ASC, vitamin_c_mg DESC
LIMIT 5;'''
    # query = """
    #     SELECT name, brand, sugar_g, calories_kcal, vitamin_c_mg, has_preservatives
    #     FROM juices
    #     WHERE sugar_g <= %s
    #       AND calories_kcal <= %s
    #       AND (vitamin_c_mg IS NULL OR vitamin_c_mg >= %s)
    #       AND has_preservatives = FALSE
    #     ORDER BY sugar_g ASC, calories_kcal ASC, vitamin_c_mg DESC
    #     LIMIT 5;
    # """

    cursor.execute(
        query,
        (
            nutrition.get("sugar_g", 100),
            nutrition.get("calories_kcal", 1000),
            nutrition.get("vitamin_c_mg", 0),
        ),
    )

    results = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {
            "name": r[0],
            "brand": r[1],
            "sugar_g": r[2],
            "calories_kcal": r[3],
            "vitamin_c_mg": r[4],
            "has_preservatives": r[5],
        }
        for r in results
    ]


import base64

import re

def extract_json_string(text):
    try:
        # Try strict parsing first
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract the first JSON-looking object using regex
        match = re.search(r"\{.*?\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None
@app.post("/analyze")
async def analyze_juice(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        encoded_image = base64.b64encode(image_bytes).decode("utf-8")

        vision_model = genai.GenerativeModel("gemini-2.0-flash")
        prompt_text = (
            "Extract the nutritional information from the juice image and return only a valid JSON object "
            "with the keys: 'sugar_g', 'calories_kcal', 'vitamin_c_mg', and 'has_preservatives'. "
            "The values must be numeric except 'has_preservatives' which should be true or false. "
            "Do not include any explanation or formatting. Return only the JSON. Example:\n"
            "{\"sugar_g\": 12, \"calories_kcal\": 80, \"vitamin_c_mg\": 30, \"has_preservatives\": false}"
        )

        vision_response = vision_model.generate_content({
            "parts": [
                {"text": prompt_text},
                {"mime_type": file.content_type, "data": encoded_image}
            ]
        })

        raw_output = vision_response.text.strip()
        nutrition = extract_json_string(raw_output)

        if not nutrition:
            raise HTTPException(status_code=400, detail="Could not parse Gemini output to JSON.")

        # Ensure all required fields are present
        required_fields = ["sugar_g", "calories_kcal", "vitamin_c_mg", "has_preservatives"]
        for field in required_fields:
            if field not in nutrition:
                raise HTTPException(status_code=400, detail=f"Missing field: {field}")

        alternatives = fetch_alternatives(nutrition)

        summary_model = genai.GenerativeModel("gemini-2.0-flash")
        summary_prompt = (
            f"User uploaded juice nutrition: {nutrition}\n"
            f"Here are healthier juice alternatives: {alternatives}\n"
            "Suggest the healthiest alternative and explain why in simple terms."
        )
        summary_response = summary_model.generate_content(summary_prompt)

        return {
            "extracted_nutrition": nutrition,
            "suggested_healthier_juices": alternatives,
            "suggestion_summary": summary_response.text,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Nutrition analysis failed: {str(e)}")
    

    if __name__ == "__main__":
        port = int(os.environ.get("PORT", 8000))  # Render sets this
        uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)