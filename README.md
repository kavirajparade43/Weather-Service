# Weather Report Service

##Features
- Fetches weather data (temperature & humidity) from Open-Meteo API
- Saves to SQLite
- Exports last 48h data as Excel
- Generates PDF report with chart

## Run Locally
```bash
cd weather-service
pip install -r requirements.txt
uvicorn app:app --reload
