from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sqlite3, os, secrets, shutil, datetime, json

BASE = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("AULA_DATA_DIR", str(BASE / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB = DATA_DIR / "aula.db"
UPLOADS = DATA_DIR / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Aula médica · Dr. Villalobos")
app.mount("/static", StaticFiles(directory=BASE/"static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")

ADMIN_PASSWORD = os.getenv("AULA_ADMIN_PASSWORD", "CambiarEstaClave2026")
TOKENS = set()

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS courses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      subtitle TEXT DEFAULT '',
      category TEXT DEFAULT '',
      cover TEXT DEFAULT '',
      published INTEGER DEFAULT 1,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS lessons(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      kind TEXT DEFAULT 'pptx',
      filename TEXT DEFAULT '',
      notes TEXT DEFAULT '',
      ord INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    CREATE TABLE IF NOT EXISTS activities(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      message TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT DEFAULT ''
    );
    """)
    initialized = cur.execute("SELECT value FROM settings WHERE key='initialized'").fetchone()
    if initialized is None:
        n = cur.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        if n == 0:
            seed = [
              ("Hemorragia obstétrica","Protocolos, algoritmos y simulación","Urgencias","#hemorragia"),
              ("Preeclampsia y HTA en el embarazo","Diagnóstico y manejo basado en evidencia","Obstetricia","#preeclampsia"),
              ("Parto y trabajo de parto","Fisiología, vigilancia y buenas prácticas","Obstetricia","#parto"),
              ("Cesárea segura","Indicaciones, técnica y seguridad","Cirugía","#cesarea")
            ]
            for t,s,c,cover in seed:
                cur.execute("INSERT INTO courses(title,subtitle,category,cover) VALUES(?,?,?,?)",(t,s,c,cover))
            cur.execute("INSERT INTO activities(message) VALUES(?)",("Plataforma inicializada y lista para agregar clases.",))
        cur.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('initialized','1')")
    con.commit()
    con.close()

@app.on_event("startup")
def startup():
    init_db()

def auth(request: Request):
    token = request.headers.get("authorization","").replace("Bearer ","").strip()
    if token not in TOKENS:
        raise HTTPException(401,"Acceso de administrador requerido")

@app.get("/", response_class=HTMLResponse)
def home():
    return (BASE/"static"/"index.html").read_text(encoding="utf-8")

@app.post("/api/login")
async def login(payload: dict):
    if payload.get("password") != ADMIN_PASSWORD:
        raise HTTPException(401,"Contraseña incorrecta")
    t = secrets.token_urlsafe(24)
    TOKENS.add(t)
    return {"token":t}

@app.get("/api/courses")
def courses():
    con=db()
    rows=[dict(r) for r in con.execute("SELECT * FROM courses WHERE published=1 ORDER BY id").fetchall()]
    for r in rows:
        r["lessons"]=[dict(x) for x in con.execute("SELECT * FROM lessons WHERE course_id=? ORDER BY ord,id",(r["id"],)).fetchall()]
    con.close()
    return rows

@app.get("/api/dashboard")
def dashboard():
    con=db()
    c=con.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    l=con.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    acts=[dict(r) for r in con.execute("SELECT * FROM activities ORDER BY id DESC LIMIT 5").fetchall()]
    con.close()
    return {"courses":c,"lessons":l,"students":248,"progress":85,"satisfaction":96,"activities":acts}

@app.post("/api/courses")
async def create_course(request: Request, title: str = Form(...), subtitle: str = Form(""), category: str = Form("")):
    auth(request)
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO courses(title,subtitle,category) VALUES(?,?,?)",(title,subtitle,category))
    cid=cur.lastrowid
    cur.execute("INSERT INTO activities(message) VALUES(?)",(f"Se creó el curso: {title}",))
    con.commit(); con.close()
    return {"ok":True,"id":cid}

@app.delete("/api/courses/{course_id}")
def delete_course(course_id:int, request:Request):
    auth(request)
    con=db(); cur=con.cursor()
    course = cur.execute("SELECT title FROM courses WHERE id=?",(course_id,)).fetchone()
    if not course:
        con.close()
        raise HTTPException(404,"Curso no encontrado")
    files = [r["filename"] for r in cur.execute("SELECT filename FROM lessons WHERE course_id=?",(course_id,)).fetchall() if r["filename"]]
    cur.execute("DELETE FROM lessons WHERE course_id=?",(course_id,))
    cur.execute("DELETE FROM courses WHERE id=?",(course_id,))
    cur.execute("INSERT INTO activities(message) VALUES(?)",(f"Se eliminó el curso: {course['title']}",))
    con.commit(); con.close()
    for filename in files:
        p = UPLOADS / filename
        if p.exists():
            try: p.unlink()
            except OSError: pass
    return {"ok":True}

@app.post("/api/lessons")
async def add_lesson(request: Request, course_id:int=Form(...), title:str=Form(...), notes:str=Form(""), file:UploadFile|None=File(None)):
    auth(request)
    filename=""; kind="texto"
    if file and file.filename:
        ext=Path(file.filename).suffix.lower()
        allowed={".pptx",".pdf",".mp4",".mov",".png",".jpg",".jpeg",".webp"}
        if ext not in allowed:
            raise HTTPException(400,"Formato no admitido")
        safe=f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}{ext}"
        with open(UPLOADS/safe,"wb") as out:
            shutil.copyfileobj(file.file,out)
        filename=safe; kind=ext.lstrip(".")
    con=db(); cur=con.cursor()
    exists=cur.execute("SELECT 1 FROM courses WHERE id=?",(course_id,)).fetchone()
    if not exists:
        con.close()
        raise HTTPException(404,"Curso no encontrado")
    ordv=cur.execute("SELECT COALESCE(MAX(ord),0)+1 FROM lessons WHERE course_id=?",(course_id,)).fetchone()[0]
    cur.execute("INSERT INTO lessons(course_id,title,kind,filename,notes,ord) VALUES(?,?,?,?,?,?)",(course_id,title,kind,filename,notes,ordv))
    cur.execute("INSERT INTO activities(message) VALUES(?)",(f"Se agregó la clase: {title}",))
    con.commit(); con.close()
    return {"ok":True}

@app.delete("/api/lessons/{lesson_id}")
def delete_lesson(lesson_id:int, request:Request):
    auth(request)
    con=db()
    row=con.execute("SELECT filename,title FROM lessons WHERE id=?",(lesson_id,)).fetchone()
    if row:
        if row["filename"]:
            p=UPLOADS/row["filename"]
            if p.exists(): p.unlink()
        con.execute("DELETE FROM lessons WHERE id=?",(lesson_id,))
        con.execute("INSERT INTO activities(message) VALUES(?)",(f"Se eliminó la clase: {row['title']}",))
        con.commit()
    con.close()
    return {"ok":True}

@app.get("/api/export")
def export_data(request:Request):
    auth(request)
    con=db()
    data={
      "courses":[dict(r) for r in con.execute("SELECT * FROM courses").fetchall()],
      "lessons":[dict(r) for r in con.execute("SELECT * FROM lessons").fetchall()],
      "activities":[dict(r) for r in con.execute("SELECT * FROM activities").fetchall()]
    }
    con.close()
    out=BASE/"aula_export.json"
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return FileResponse(out,filename="aula_medica_dr_villalobos_export.json")

@app.get("/health")
def health():
    return {"ok":True}
