# MedicalWeb.py
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import datetime
from typing import Dict, List, Any

# DB imports
from database import SessionLocal, engine
import models
from models import Patient, Doctor, History, Log, HomecareRequest, EmergencyEvent
from database import Base

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----- keep original users dict for login/session -----
users = {
    "Patient": {"password": "AAAAAAAA", "role": "patient", "name": "Liao"},
    "DoctorWu": {"password": "DDDDDDDD", "role": "doctor", "name": "Doctor Wu"},
    "Manager": {"password": "XXXXXXXX", "role": "manager", "name": "Manager"}
}

# keep patient_modules in-memory for display (preserve existing content)
patient_modules = {
    "Liao": ["Heart Monitoring Model"]
}

# Helper: DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper parser (similar to original)
def parse_latest_metrics_from_logs(logs: List[Log]) -> Dict[str, Any]:
    if not logs:
        return {}
    last = logs[-1].content if isinstance(logs[-1], Log) else str(logs[-1])
    metrics = {}
    parts = str(last).split(": ", 1)
    if len(parts) == 2:
        body = parts[1]
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
                num = ''.join(ch for ch in body if (ch.isdigit() or ch == '.'))
                metrics["temp"] = float(num)
            except:
                pass
    return metrics

# ---------- Initialize DB and seed fake data ----------
def init_db_and_seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # If patients empty, seed sample patients and data
        if db.query(Patient).count() == 0:
            # Seed patients matching your original names
            names = ["Liao"]
            for n in names:
                p = Patient(name=n)
                db.add(p)
            db.commit()

            # Add histories
            p_liao = db.query(Patient).filter_by(name="Liao").first()

            if p_liao:
                db.add_all([
                    History(content="2025-08-01: Diagnosis - Heart check normal", patient=p_liao),
                    History(content="2025-08-15: ECG - Minor arrhythmia", patient=p_liao)
                ])
                db.add_all([
                    Log(content="2025-09-01: Heart rate 72", patient=p_liao),
                    Log(content="2025-09-02: Heart rate 75", patient=p_liao),
                    Log(content="2025-09-03: Heart rate 80", patient=p_liao),
                    Log(content="2025-10-29: Heart rate 76", patient=p_liao)
                ])

            # seed doctor
            if db.query(Doctor).count() == 0:
                db.add(Doctor(name="Doctor Wu"))
            db.commit()

        # seed homecare requests/emergency none by default (empty)
    finally:
        db.close()

# run seed at import
init_db_and_seed()

# ---------- Routes (preserve original behavior, but use DB) ----------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    # 🚀 未登入者直接導向登入畫面
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "user": None})

    if user["role"] == "doctor":
        pending = []
        reqs = db.query(HomecareRequest).filter(HomecareRequest.status == "pending").all()
        for r in reqs:
            pending.append({"name": r.patient.name, "requested_at": r.requested_at.strftime("%Y-%m-%d %H:%M:%S")})

        latest_data = {}
        patients = db.query(Patient).all()
        for p in patients:
            logs = db.query(Log).filter(Log.patient_id == p.id).order_by(Log.timestamp).all()
            metrics = parse_latest_metrics_from_logs(logs)
            latest_data[p.name] = {"metrics": metrics, "last_log": logs[-1].content if logs else None}

        return templates.TemplateResponse("home.html", {
            "request": request,
            "user": user,
            "pending_homecare": pending,
            "latest_data": latest_data
        })

    elif user["role"] == "patient":
        name = user["name"]
        patient = db.query(Patient).filter_by(name=name).first()
        logs = db.query(Log).filter(Log.patient_id == patient.id).order_by(Log.timestamp).all() if patient else []
        metrics = parse_latest_metrics_from_logs(logs)
        latest_data = {"metrics": metrics, "last_log": logs[-1].content if logs else None}

        req = None
        if patient:
            r = db.query(HomecareRequest).filter(HomecareRequest.patient_id == patient.id).order_by(HomecareRequest.requested_at.desc()).first()
            if r:
                req = {"requested_at": r.requested_at.strftime("%Y-%m-%d %H:%M:%S"), "status": r.status, "reason": r.reason}

        return templates.TemplateResponse("home.html", {
            "request": request,
            "user": user,
            "latest_data": latest_data,
            "homecare_request": req
        })

    else:
        return templates.TemplateResponse("home.html", {"request": request, "user": user})


# Login / Logout (unchanged)
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in users and users[username]["password"] == password:
        request.session["user"] = users[username]
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=302)

# History page
@app.get("/history", response_class=HTMLResponse)
async def history(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})

    if user["role"] == "patient":
        patient = db.query(Patient).filter_by(name=user["name"]).first()
        histories = []
        if patient:
            rows = db.query(History).filter(History.patient_id == patient.id).order_by(History.created_at).all()
            histories = [h.content for h in rows]
        return templates.TemplateResponse("history.html", {"request": request, "history": histories, "user": user})

    elif user["role"] == "doctor":
        patients = [p.name for p in db.query(Patient).all()]
        history_map = {}
        for p in db.query(Patient).all():
            rows = db.query(History).filter(History.patient_id == p.id).order_by(History.created_at).all()
            history_map[p.name] = [r.content for r in rows]
        # supply modules from in-memory mapping to preserve templates
        return templates.TemplateResponse("history.html", {"request": request, "patients": patients, "history": history_map, "modules": patient_modules, "user": user})



# Add history (doctor)
@app.get("/add_history/{patient_name}", response_class=HTMLResponse)
async def add_history_page(request: Request, patient_name: str):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    return templates.TemplateResponse("add_history.html", {"request": request, "patient_name": patient_name})

@app.post("/add_history/{patient_name}", response_class=HTMLResponse)
async def add_history_submit(request: Request, patient_name: str, report: str = Form(...), db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=patient_name).first()
    if not patient:
        patient = Patient(name=patient_name)
        db.add(patient)
        db.commit()
    h = History(content=report, patient_id=patient.id)
    db.add(h)
    db.commit()
    return RedirectResponse("/history", status_code=302)

# Edit history (doctor) - inline (expects index in template)
@app.post("/edit_history/{patient_name}/{index}", response_class=HTMLResponse)
async def edit_history(request: Request, patient_name: str, index: int, new_text: str = Form(...), db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=patient_name).first()
    if not patient:
        return RedirectResponse("/history", status_code=302)
    rows = db.query(History).filter(History.patient_id == patient.id).order_by(History.created_at).all()
    if 0 <= index < len(rows):
        rows[index].content = new_text
        db.commit()
    return RedirectResponse("/history", status_code=302)

# Delete history (doctor)
@app.post("/delete_history/{patient_name}/{index}", response_class=HTMLResponse)
async def delete_history(request: Request, patient_name: str, index: int, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=patient_name).first()
    if not patient:
        return RedirectResponse("/history", status_code=302)
    rows = db.query(History).filter(History.patient_id == patient.id).order_by(History.created_at).all()
    if 0 <= index < len(rows):
        db.delete(rows[index])
        db.commit()
    return RedirectResponse("/history", status_code=302)

# Modules page
@app.get("/modules", response_class=HTMLResponse)
async def modules_page(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})
    if user["role"] == "patient":
        mods = patient_modules.get(user["name"], [])
        return templates.TemplateResponse("modules.html", {"request": request, "modules": mods, "user": user})
    elif user["role"] == "doctor":
        patients = [p.name for p in db.query(Patient).all()]
        return templates.TemplateResponse("modules.html", {"request": request, "patients": patients, "modules": patient_modules, "user": user})

# Logs page
@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})
    if user["role"] == "patient":
        patient = db.query(Patient).filter_by(name=user["name"]).first()
        logs = [l.content for l in db.query(Log).filter(Log.patient_id == patient.id).order_by(Log.timestamp).all()] if patient else []
        return templates.TemplateResponse("logs.html", {"request": request, "logs": logs, "user": user})
    elif user["role"] == "doctor":
        patients = [p.name for p in db.query(Patient).all()]
        # logs mapping name -> list
        logs_map = {}
        for p in db.query(Patient).all():
            logs_map[p.name] = [l.content for l in db.query(Log).filter(Log.patient_id == p.id).order_by(Log.timestamp).all()]
        return templates.TemplateResponse("logs.html", {"request": request, "patients": patients, "logs": logs_map, "user": user})


# Add / Edit / Delete logs (doctor)
@app.post("/add_log/{patient_name}", response_class=HTMLResponse)
async def add_log(request: Request, patient_name: str, log_text: str = Form(...), db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=patient_name).first()
    if not patient:
        patient = Patient(name=patient_name)
        db.add(patient)
        db.commit()
    new_log = Log(content=log_text, patient_id=patient.id)
    db.add(new_log)
    db.commit()
    return RedirectResponse("/logs", status_code=302)

@app.post("/edit_log/{patient_name}/{index}", response_class=HTMLResponse)
async def edit_log(request: Request, patient_name: str, index: int, new_text: str = Form(...), db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=patient_name).first()
    if not patient:
        return RedirectResponse("/logs", status_code=302)
    rows = db.query(Log).filter(Log.patient_id == patient.id).order_by(Log.timestamp).all()
    if 0 <= index < len(rows):
        rows[index].content = new_text
        db.commit()
    return RedirectResponse("/logs", status_code=302)

@app.post("/delete_log/{patient_name}/{index}", response_class=HTMLResponse)
async def delete_log(request: Request, patient_name: str, index: int, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=patient_name).first()
    if not patient:
        return RedirectResponse("/logs", status_code=302)
    rows = db.query(Log).filter(Log.patient_id == patient.id).order_by(Log.timestamp).all()
    if 0 <= index < len(rows):
        db.delete(rows[index])
        db.commit()
    return RedirectResponse("/logs", status_code=302)

# Apply homecare (patient) and admin view (doctor)
@app.get("/apply_homecare", response_class=HTMLResponse)
async def apply_homecare_page(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})
    if user["role"] == "patient":
        patient = db.query(Patient).filter_by(name=user["name"]).first()
        req = None
        if patient:
            r = db.query(HomecareRequest).filter(HomecareRequest.patient_id == patient.id).order_by(HomecareRequest.requested_at.desc()).first()
            if r:
                req = {"requested_at": r.requested_at.strftime("%Y-%m-%d %H:%M:%S"), "status": r.status, "reason": r.reason}
        return templates.TemplateResponse("apply_homecare.html", {"request": request, "user": user, "request_info": req})
    elif user["role"] == "doctor":
        # doctor sees all requests
        reqs = db.query(HomecareRequest).all()
        mapping = {}
        for r in reqs:
            mapping[r.patient.name] = {"requested_at": r.requested_at.strftime("%Y-%m-%d %H:%M:%S"), "status": r.status, "reason": r.reason}
        return templates.TemplateResponse("apply_homecare_admin.html", {"request": request, "user": user, "requests": mapping})
    else:
        return templates.TemplateResponse("restricted.html", {"request": request, "user": user})

@app.post("/apply_homecare", response_class=HTMLResponse)
async def apply_homecare_submit(request: Request, reason: str = Form(...), db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user or user["role"] != "patient":
        return templates.TemplateResponse("restricted.html", {"request": request})
    patient = db.query(Patient).filter_by(name=user["name"]).first()
    if not patient:
        patient = Patient(name=user["name"])
        db.add(patient)
        db.commit()
    # create a new request
    req = HomecareRequest(reason=reason, status="pending", patient_id=patient.id)
    db.add(req)
    db.commit()
    return RedirectResponse("/", status_code=302)

# Emergency mode (doctor) - 顯示急救事件頁面
@app.get("/emergency", response_class=HTMLResponse)
async def emergency(request: Request, db: Session = Depends(get_db)):
    # 取得 session 中的使用者資訊
    user = request.session.get("user")
    
    # 權限檢查：只有 doctor 才能進入此頁面
    if not user or user["role"] != "doctor":
        # 非醫生或未登入使用者會看到限制頁面
        return templates.TemplateResponse("restricted.html", {"request": request, "user": user})

    # 初始化事件列表
    events = []

    # 從資料庫讀取所有急救事件，依時間排序 (最新在前)
    rows = db.query(EmergencyEvent).order_by(EmergencyEvent.time.desc()).all()

    # 將每個事件轉成前端可用的字典格式
    for e in rows:
        events.append({
            "patient": e.patient.name if e.patient else None,  # 病患名稱
            "time": e.time.strftime("%Y-%m-%d %H:%M:%S"),      # 事件時間
            "event": e.event,                                   # 事件描述
            "status": e.status                                  # 事件狀態
        })

    # 將事件列表傳給前端模板呈現
    return templates.TemplateResponse("emergency.html", {"request": request, "user": user, "events": events})


# Emergency mode (doctor) - 新增急救事件
@app.post("/emergency/add", response_class=HTMLResponse)
async def emergency_add(
    request: Request, 
    patient: str = Form(...),   # 從表單取得病患名稱
    event: str = Form(...),     # 從表單取得事件描述
    db: Session = Depends(get_db)
):
    # 取得 session 中的使用者資訊
    user = request.session.get("user")

    # 權限檢查：只有 doctor 才能新增事件
    if not user or user["role"] != "doctor":
        return templates.TemplateResponse("restricted.html", {"request": request, "user": user})

    # 查詢資料庫中是否已有這位病患
    patient_obj = db.query(Patient).filter_by(name=patient).first()

    # 若病患不存在，新增病患
    if not patient_obj:
        patient_obj = Patient(name=patient)
        db.add(patient_obj)
        db.commit()  # 提交新增病患

    # 建立新的急救事件 (預設狀態為 "處理中")
    ev = EmergencyEvent(event=event, status="處理中", patient_id=patient_obj.id)
    db.add(ev)
    db.commit()  # 提交新增事件

    # 新增完成後重新導向回 /emergency 頁面
    return RedirectResponse("/emergency", status_code=302)


# Reports page
@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db)):
    user = request.session.get("user")
    if not user:
        return templates.TemplateResponse("restricted.html", {"request": request})

    role = user.get("role")
    username = user.get("name")
    is_doctor = role == "doctor"

    reports = {}

    if is_doctor:
        # 醫師模式：整合所有病患資料
        for p in db.query(Patient).all():
            logs = db.query(Log).filter(Log.patient_id == p.id).order_by(Log.timestamp).all()
            history = db.query(History).filter(History.patient_id == p.id).order_by(History.created_at).all()

            reports[p.name] = {
                "metrics": parse_latest_metrics_from_logs(logs),
                "last_log": logs[-1].content if logs else None,
                "modules": patient_modules.get(p.name, []),
                "logs": [l.content for l in logs],
                "history": [{"timestamp": h.created_at.strftime("%Y-%m-%d %H:%M:%S"), "summary": h.content} for h in history]
            }

        return templates.TemplateResponse("reports.html", {
            "request": request,
            "is_doctor": True,
            "reports": reports,
            "username": username,
            "user": user
        })

    else:
        # 病患模式：僅顯示自己的資料
        patient = db.query(Patient).filter_by(name=username).first()
        if not patient:
            return templates.TemplateResponse("reports.html", {
                "request": request,
                "is_doctor": False,
                "reports": {},
                "username": username,
                "user": user
            })

        logs = db.query(Log).filter(Log.patient_id == patient.id).order_by(Log.timestamp).all()
        history = db.query(History).filter(History.patient_id == patient.id).order_by(History.created_at).all()

        reports[username] = {
    "metrics": parse_latest_metrics_from_logs(logs),
    "last_log": logs[-1].content if logs else None,
    "modules": patient_modules.get(username, []),
    "logs": [l.content for l in logs],
    "history": [{"timestamp": h.created_at.strftime("%Y-%m-%d %H:%M:%S"), "summary": h.content} for h in history]
}


        return templates.TemplateResponse("reports.html", {
            "request": request,
            "is_doctor": False,
            "reports": reports,
            "username": username,
            "user": user
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
