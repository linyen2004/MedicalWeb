# MedicalWeb.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from typing import Dict, List, Any
import datetime

app = FastAPI()

# Session middleware
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")

# Templates & Static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----- Fake Users (restored to original) -----
users = {
    "Patient": {"password": "AAAAAAAA", "role": "patient", "name": "Liao"},
    "DoctorWu": {"password": "DDDDDDDD", "role": "doctor", "name": "Doctor Wu"},
    "Manager": {"password": "XXXXXXXX", "role": "manager", "name": "Manager"}
}

# ----- Fake Data (restored original structures) -----
patient_history = {
    "Liao": ["2024-08-01: Diagnosis - Heart check normal",
             "2024-08-15: ECG - Minor arrhythmia"],
    "Patient B": ["2024-08-05: Diagnosis - Blood pressure high"],
    "Patient C": ["2024-08-10: Diagnosis - Normal"]
}

patient_modules = {
    "Liao": ["Heart Monitoring Model"],
    "Patient B": ["Blood Pressure Model"],
    "Patient C": ["Basic Health Model"]
}

patient_logs = {
    "Liao": ["2024-09-01: Heart rate 72", "2024-09-02: Heart rate 75", "2024-09-03: Heart rate 80"],
    "Patient B": ["2024-09-01: BP 140/90", "2024-09-02: BP 138/88"],
    "Patient C": ["2024-09-01: Heart rate 70", "2024-09-02: Heart rate 68"]
}

doctor_patients = ["Liao", "Patient B", "Patient C"]

# ----- In-memory requests/events storage -----
homecare_requests: Dict[str, Dict[str, Any]] = {
    # example: "Liao": {"requested_at": "2025-10-01 12:00", "status": "pending"}
}

emergency_events: List[Dict[str, Any]] = [
    # example: {"patient": "Liao", "time": "2025-10-16 09:20", "event": "血壓急升", "status": "處理中"}
]


# ---- helpers ----
def parse_latest_metrics_from_logs(logs: List[str]) -> Dict[str, Any]:
    """
    Try to extract simple metrics from the last log entry.
    This is naive parsing for demo/fake-data purposes.
    """
    if not logs:
        return {}
    last = logs[-1]
    metrics = {}
    # common patterns used in our fake logs:
    # "YYYY-MM-DD: Heart rate 72"
    # "YYYY-MM-DD: BP 140/90"
    # "YYYY-MM-DD: Temp 36.8" (if present)
    parts = last.split(": ", 1)
    if len(parts) == 2:
        body = parts[1]
        # heart rate
        if "Heart rate" in body:
            try:
                metrics["heart_rate"] = int(body.split("Heart rate")[1].strip())
            except:
                pass
        if "BP" in body:
            try:
                bp = body.split("BP")[1].strip()
                metrics["bp"] = bp
            except:
                pass
        if "Temp" in body or "Temperature" in body:
            try:
                # extract numeric
                num = ''.join(ch for ch in body if (ch.isdigit() or ch == '.'))
                metrics["temp"] = float(num)
            except:
                pass
    return metrics


# ----- Routes -----

# Home Page (enhanced)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = request.session.get("user")
    # not logged in -> show generic home
    if not user:
        return templates.TemplateResponse("home.html", {"request": request, "user": None})

    # doctor view -> show pending homecare + latest metrics for all patients
    if user["role"] == "doctor":
        # pending homecare list (as list of dicts)
        pending = []
        for pname, req in homecare_requests.items():
            if req.get("status") == "pending":
                pending.append({"name": pname, "requested_at": req.get("requested_at")})

        # build latest_data mapping from patient_logs
        latest_data = {}
        for p in doctor_patients:
            logs = patient_logs.get(p, [])
            metrics = parse_latest_metrics_from_logs(logs)
            # include last raw log for display convenience
            latest_data[p] = {
                "metrics": metrics,
                "last_log": logs[-1] if logs else None
            }

        return templates.TemplateResponse("home.html", {
            "request": request,
            "user": user,
            "pending_homecare": pending,
            "latest_data": latest_data
        })

    # patient view -> show personal latest metrics and link to apply_homecare (template shows link)
    elif user["role"] == "patient":
        name = user["name"]
        logs = patient_logs.get(name, [])
        metrics = parse_latest_metrics_from_logs(logs)
        latest_data = {"metrics": metrics, "last_log": logs[-1] if logs else None}

        # Also include the patient's own request status if exists
        request_info = homecare_requests.get(name)

        return templates.TemplateResponse("home.html", {
            "request": request,
            "user": user,
            "latest_data": latest_data,
            "homecare_request": request_info
        })

    # manager or other -> generic
    else:
        return templates.TemplateResponse("home.html", {"request": request, "user": user})


# Login Page (preserve original behavior)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in users and users[username]["password"] == password:
        # match original: store the user dict itself (as in your first version)
        request.session["user"] = users[username]
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})


# Logout
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)


# History Page (keeps original behavior)
@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})

    if user["role"] == "patient":
        data = patient_history.get(user["name"], [])
        return templates.TemplateResponse("history.html", {"request": request, "history": data, "user": user})

    elif user["role"] == "doctor":
        return templates.TemplateResponse("history.html", {"request": request, "patients": doctor_patients, "history": patient_history, "modules": patient_modules, "user": user})


# Modules Page (keeps original behavior)
@app.get("/modules", response_class=HTMLResponse)
async def modules(request: Request):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})

    if user["role"] == "patient":
        data = patient_modules.get(user["name"], [])
        return templates.TemplateResponse("modules.html", {"request": request, "modules": data, "user": user})
    elif user["role"] == "doctor":
        return templates.TemplateResponse("modules.html", {"request": request, "patients": doctor_patients, "modules": patient_modules, "user": user})


# Logs Page (keeps original behavior)
@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})

    if user["role"] == "patient":
        data = patient_logs.get(user["name"], [])
        return templates.TemplateResponse("logs.html", {"request": request, "logs": data, "user": user})
    elif user["role"] == "doctor":
        return templates.TemplateResponse("logs.html", {"request": request, "patients": doctor_patients, "logs": patient_logs, "user": user})


# Add History (Doctor) (keeps original behavior)
@app.get("/add_history/{patient_name}", response_class=HTMLResponse)
async def add_history_page(request: Request, patient_name: str):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    return templates.TemplateResponse("add_history.html", {"request": request, "patient_name": patient_name})


@app.post("/add_history/{patient_name}", response_class=HTMLResponse)
async def add_history_submit(request: Request, patient_name: str, report: str = Form(...)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    if patient_name in patient_history:
        patient_history[patient_name].append(report)
    else:
        patient_history[patient_name] = [report]
    return RedirectResponse("/history", status_code=302)


# Manager - Model Editor (keeps original behavior)
@app.get("/model_editor", response_class=HTMLResponse)
async def model_editor(request: Request):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})
    if user["role"] != "manager":
        return templates.TemplateResponse("restricted.html", {"request": request})
    return templates.TemplateResponse("model_editor.html", {"request": request})


# ==== Apply Homecare (patient) ====
@app.get("/apply_homecare", response_class=HTMLResponse)
async def apply_homecare_page(request: Request):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})
    # Only patients can submit; doctors/managers can view all requests (optional)
    if user["role"] == "patient":
        # show existing request if any
        req = homecare_requests.get(user["name"])
        return templates.TemplateResponse("apply_homecare.html", {"request": request, "user": user, "request_info": req})
    elif user["role"] == "doctor":
        # doctor can view all requests
        return templates.TemplateResponse("apply_homecare_admin.html", {"request": request, "user": user, "requests": homecare_requests})
    else:
        return templates.TemplateResponse("restricted.html", {"request": request, "user": user})


@app.post("/apply_homecare", response_class=HTMLResponse)
async def apply_homecare_submit(request: Request, reason: str = Form(...)):
    user = request.session.get("user")
    if not user or user["role"] != "patient":
        return templates.TemplateResponse("restricted.html", {"request": request})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    homecare_requests[user["name"]] = {"requested_at": now, "status": "pending", "reason": reason}
    return RedirectResponse("/", status_code=302)


# ==== Emergency Mode (doctor only) ====
@app.get("/emergency", response_class=HTMLResponse)
async def emergency(request: Request):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request, "user": user})

    return templates.TemplateResponse("emergency.html", {"request": request, "user": user, "events": emergency_events})


# Optional: endpoint for doctors to add an emergency event (could be used by monitoring system)
@app.post("/emergency/add", response_class=HTMLResponse)
async def emergency_add(request: Request, patient: str = Form(...), event: str = Form(...)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request, "user": user})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emergency_events.append({"patient": patient, "time": now, "event": event, "status": "處理中"})
    return RedirectResponse("/emergency", status_code=302)

@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})

    role = user.get("role")
    username = user.get("name")

    is_doctor = role == "doctor"

    # 醫師模式
    if is_doctor:
        report_data = {
            patient: {
                "modules": patient_modules.get(patient, []),
                "logs": patient_logs.get(patient, []),
                "history": patient_history.get(patient, [])
            }
            for patient in doctor_patients
        }
        # latest_data for template
        latest_data = {}
        for patient, logs in patient_logs.items():
            metrics = parse_latest_metrics_from_logs(logs)
            latest_data[patient] = {"metrics": metrics, "last_log": logs[-1] if logs else None}

        return templates.TemplateResponse("reports.html", {
            "request": request,
            "is_doctor": True,
            "report_data": report_data,
            "latest_data": latest_data,
            "username": username,
            "user": user   # ✅ 加上 user
        })

    # 病患模式
    else:
        logs = patient_logs.get(username, [])
        metrics = parse_latest_metrics_from_logs(logs)
        latest_data = {"metrics": metrics, "last_log": logs[-1] if logs else None}
        report_data = {
            username: {
                "modules": patient_modules.get(username, []),
                "logs": logs,
                "history": patient_history.get(username, [])
            }
        }
        return templates.TemplateResponse("reports.html", {
            "request": request,
            "is_doctor": False,
            "report_data": report_data,
            "latest_data": latest_data,
            "username": username,
            "user": user   # ✅ 加上 user
        })





# ==== Run ====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
