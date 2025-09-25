from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
import requests
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

DB_NAME = "weather.db"
app = FastAPI(title="Weather Report Service")


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weather_data (
                    timestamp TEXT PRIMARY KEY,
                    temperature REAL,
                    humidity REAL
                )''')
    conn.commit()
    conn.close()

init_db()

def insert_data(data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for row in data:
        try:
            c.execute("INSERT OR REPLACE INTO weather_data VALUES (?, ?, ?)",
                      (row["timestamp"], row["temperature"], row["humidity"]))
        except Exception as e:
            print("DB Insert Error:", e)
    conn.commit()
    conn.close()

def get_last_48h():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    c.execute("SELECT * FROM weather_data WHERE timestamp >= ? ORDER BY timestamp", (cutoff,))
    rows = c.fetchall()
    conn.close()
    return rows


@app.get("/weather-report")
def fetch_weather(lat: float = Query(...), lon: float = Query(...)):
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=2)

       
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m",
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "timezone": "UTC"
        }

        r = requests.get(url, params=params)
        data = r.json()

        
        if "hourly" not in data:
            return JSONResponse(content={"error": "Invalid API response", "details": data}, status_code=500)

        timestamps = data["hourly"]["time"]
        temps = data["hourly"]["temperature_2m"]
        hums = data["hourly"]["relative_humidity_2m"]

        processed = []
        for t, temp, hum in zip(timestamps, temps, hums):
            processed.append({"timestamp": t, "temperature": temp, "humidity": hum})

        insert_data(processed)
        return JSONResponse(content={"message": "Data fetched & stored", "count": len(processed)})

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/export/excel")
def export_excel():
    try:
        rows = get_last_48h()
        df = pd.DataFrame(rows, columns=["timestamp", "temperature_2m", "relative_humidity_2m"])
        file_path = "weather_data.xlsx"
        df.to_excel(file_path, index=False)
        return FileResponse(file_path, filename=file_path,
                            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/export/pdf")
def export_pdf():
    try:
        rows = get_last_48h()
        df = pd.DataFrame(rows, columns=["timestamp", "temperature_2m", "relative_humidity_2m"])
        if df.empty:
            return JSONResponse(content={"error": "No data available"}, status_code=404)

        plt.figure(figsize=(8, 4))
        plt.plot(df["timestamp"], df["temperature_2m"], label="Temperature (°C)", color="red")
        plt.plot(df["timestamp"], df["relative_humidity_2m"], label="Humidity (%)", color="blue")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.savefig("chart.png")
        plt.close()

        
        pdf_path = "weather_report.pdf"
        c = canvas.Canvas(pdf_path, pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, 800, "Weather Report")

        c.setFont("Helvetica", 12)
        c.drawString(50, 770, f"Location: lat={rows[0][1]}, lon={rows[0][2]}")
        c.drawString(50, 750, f"Date Range: Last 48 Hours")

        c.drawImage("chart.png", 50, 400, width=500, height=300)
        c.save()

        return FileResponse(pdf_path, filename=pdf_path, media_type="application/pdf")

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
