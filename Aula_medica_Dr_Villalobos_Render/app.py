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
      access_hours INTEGER DEFAULT 24,
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

    CREATE TABLE IF NOT EXISTS students(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      full_name TEXT NOT NULL,
      age INTEGER,
      institution TEXT DEFAULT '',
      position TEXT DEFAULT '',
      email TEXT DEFAULT '',
      course_id INTEGER,
      access_token TEXT DEFAULT '',
      access_started_at TEXT,
      access_expires_at TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(course_id) REFERENCES courses(id)
    );

    CREATE TABLE IF NOT EXISTS medical_videos(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT DEFAULT '',
      url TEXT NOT NULL,
      category TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS quizzes(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT DEFAULT '',
      course_id INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(course_id) REFERENCES courses(id)
    );
    CREATE TABLE IF NOT EXISTS quiz_questions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      quiz_id INTEGER NOT NULL,
      question TEXT NOT NULL,
      option_a TEXT NOT NULL,
      option_b TEXT NOT NULL,
      option_c TEXT NOT NULL,
      option_d TEXT NOT NULL,
      correct TEXT NOT NULL,
      explanation TEXT DEFAULT '',
      FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
    );
    CREATE TABLE IF NOT EXISTS quiz_results(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      quiz_id INTEGER NOT NULL,
      student_name TEXT NOT NULL,
      email TEXT DEFAULT '',
      score INTEGER DEFAULT 0,
      total INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
    );
    CREATE TABLE IF NOT EXISTS clinical_cases(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      summary TEXT NOT NULL,
      question TEXT DEFAULT '',
      category TEXT DEFAULT '',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS case_comments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      case_id INTEGER NOT NULL,
      author TEXT NOT NULL,
      comment TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(case_id) REFERENCES clinical_cases(id)
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
    # Safe migrations for existing databases
    course_cols={r["name"] for r in cur.execute("PRAGMA table_info(courses)").fetchall()}
    if "access_hours" not in course_cols:
        cur.execute("ALTER TABLE courses ADD COLUMN access_hours INTEGER DEFAULT 24")
    student_cols={r["name"] for r in cur.execute("PRAGMA table_info(students)").fetchall()}
    if "access_token" not in student_cols:
        cur.execute("ALTER TABLE students ADD COLUMN access_token TEXT DEFAULT ''")
    if "access_started_at" not in student_cols:
        cur.execute("ALTER TABLE students ADD COLUMN access_started_at TEXT")
    if "access_expires_at" not in student_cols:
        cur.execute("ALTER TABLE students ADD COLUMN access_expires_at TEXT")
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

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

def validate_course_access(course_id:int, access_token:str):
    if not access_token:
        raise HTTPException(401,"Inscripción requerida")
    con=db()
    row=con.execute("""
      SELECT s.id,s.full_name,s.course_id,s.access_expires_at
      FROM students s
      WHERE s.course_id=? AND s.access_token=?
      ORDER BY s.id DESC LIMIT 1
    """,(course_id,access_token)).fetchone()
    con.close()
    if not row:
        raise HTTPException(401,"Acceso no válido")
    try:
        exp=datetime.datetime.fromisoformat(row["access_expires_at"])
        if exp.tzinfo is None:
            exp=exp.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        raise HTTPException(403,"Acceso vencido")
    remaining=(exp-utcnow()).total_seconds()
    if remaining <= 0:
        raise HTTPException(403,"El periodo de acceso al curso ha terminado")
    return dict(row), remaining

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


@app.get("/api/courses/{course_id}/access")
def course_access(course_id:int, access_token:str=""):
    info, remaining = validate_course_access(course_id, access_token)
    con=db()
    course=con.execute("SELECT * FROM courses WHERE id=?",(course_id,)).fetchone()
    if not course:
        con.close()
        raise HTTPException(404,"Curso no encontrado")
    lessons=[dict(r) for r in con.execute("SELECT * FROM lessons WHERE course_id=? ORDER BY ord,id",(course_id,)).fetchall()]
    con.close()
    return {"course":dict(course),"lessons":lessons,"student":info["full_name"],"remaining_seconds":max(0,int(remaining)),"expires_at":info["access_expires_at"]}

@app.get("/course-file/{lesson_id}/{access_token}/{filename}")
def course_file(lesson_id:int, access_token:str, filename:str):
    con=db()
    row=con.execute("SELECT id,course_id,filename,kind FROM lessons WHERE id=?",(lesson_id,)).fetchone()
    con.close()
    if not row or not row["filename"]:
        raise HTTPException(404,"Archivo no encontrado")
    if filename != row["filename"]:
        raise HTTPException(404,"Archivo no encontrado")
    validate_course_access(row["course_id"],access_token)
    p=UPLOADS/row["filename"]
    if not p.exists():
        raise HTTPException(404,"Archivo no disponible")
    media={
      "pdf":"application/pdf",
      "pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "mp4":"video/mp4","mov":"video/quicktime",
      "png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg","webp":"image/webp"
    }.get(row["kind"],"application/octet-stream")
    return FileResponse(p,media_type=media,headers={"Content-Disposition":"inline","Cache-Control":"private, no-store"})

@app.get("/api/dashboard")
def dashboard():
    con=db()
    c=con.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    l=con.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
    s=con.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    acts=[dict(r) for r in con.execute("SELECT * FROM activities ORDER BY id DESC LIMIT 5").fetchall()]
    con.close()
    return {"courses":c,"lessons":l,"students":s,"progress":85,"satisfaction":96,"activities":acts}

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

@app.put("/api/courses/{course_id}/access-settings")
async def update_course_access_settings(course_id:int, request:Request):
    auth(request)
    payload=await request.json()
    try:
        hours=int(payload.get("access_hours",24))
    except Exception:
        raise HTTPException(400,"Duración inválida")
    if hours<1 or hours>8760:
        raise HTTPException(400,"La duración debe estar entre 1 y 8760 horas")
    con=db()
    con.execute("UPDATE courses SET access_hours=? WHERE id=?",(hours,course_id))
    con.commit(); con.close()
    return {"ok":True,"access_hours":hours}

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


@app.post("/api/register")
async def register_student(
    full_name: str = Form(...),
    age: int|None = Form(None),
    institution: str = Form(""),
    position: str = Form(""),
    email: str = Form(""),
    course_id: int = Form(...)
):
    full_name=full_name.strip()
    email=email.strip().lower()
    if len(full_name)<3:
        raise HTTPException(400,"Nombre inválido")
    con=db(); cur=con.cursor()
    course=cur.execute("SELECT id,COALESCE(access_hours,24) access_hours FROM courses WHERE id=?",(course_id,)).fetchone()
    if not course:
        con.close()
        raise HTTPException(404,"Curso no encontrado")
    if email:
        dup=cur.execute("SELECT id FROM students WHERE lower(email)=? AND course_id=? ORDER BY id DESC LIMIT 1",(email,course_id)).fetchone()
        if dup:
            con.close()
            raise HTTPException(409,"Este correo ya fue inscrito en este curso")
    hours=max(1,int(course["access_hours"] or 24))
    started=utcnow()
    expires=started+datetime.timedelta(hours=hours)
    access_token=secrets.token_urlsafe(32)
    cur.execute("""INSERT INTO students(full_name,age,institution,position,email,course_id,access_token,access_started_at,access_expires_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (full_name,age,institution.strip(),position.strip(),email,course_id,access_token,started.isoformat(),expires.isoformat()))
    sid=cur.lastrowid
    cur.execute("INSERT INTO activities(message) VALUES(?)",(f"Nuevo alumno inscrito: {full_name} · acceso {hours} h",))
    con.commit(); con.close()
    return {"ok":True,"id":sid,"course_id":course_id,"access_token":access_token,"access_hours":hours,"expires_at":expires.isoformat()}

@app.get("/api/students")
def list_students(request:Request):
    auth(request)
    con=db()
    rows=[dict(r) for r in con.execute("""
      SELECT s.*, c.title AS course_title
      FROM students s
      LEFT JOIN courses c ON c.id=s.course_id
      ORDER BY s.id DESC
    """).fetchall()]
    con.close()
    return rows

@app.put("/api/students/{student_id}")
async def update_student(student_id:int, request:Request):
    auth(request)
    payload=await request.json()
    allowed={"full_name","age","institution","position","email","course_id"}
    fields=[]; values=[]
    for k in allowed:
        if k in payload:
            fields.append(f"{k}=?")
            values.append(payload[k])
    if not fields:
        raise HTTPException(400,"Sin cambios")
    values.append(student_id)
    con=db()
    con.execute(f"UPDATE students SET {', '.join(fields)} WHERE id=?",values)
    con.commit(); con.close()
    return {"ok":True}

@app.delete("/api/students/{student_id}")
def delete_student(student_id:int, request:Request):
    auth(request)
    con=db(); cur=con.cursor()
    row=cur.execute("SELECT full_name FROM students WHERE id=?",(student_id,)).fetchone()
    if not row:
        con.close()
        raise HTTPException(404,"Alumno no encontrado")
    cur.execute("DELETE FROM students WHERE id=?",(student_id,))
    cur.execute("INSERT INTO activities(message) VALUES(?)",(f"Se eliminó el alumno: {row['full_name']}",))
    con.commit(); con.close()
    return {"ok":True}

@app.get("/api/students/export.csv")
def export_students_csv(request:Request):
    auth(request)
    import csv
    con=db()
    rows=con.execute("""
      SELECT s.id,s.full_name,s.age,s.institution,s.position,s.email,
             COALESCE(c.title,'') AS course,s.created_at
      FROM students s
      LEFT JOIN courses c ON c.id=s.course_id
      ORDER BY s.id
    """).fetchall()
    con.close()
    out=DATA_DIR/"alumnos_aula_medica.csv"
    with open(out,"w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f)
        w.writerow(["ID","Nombre","Edad","Institución/Adscripción","Puesto/Grado","Correo","Curso","Fecha de inscripción"])
        for r in rows:
            w.writerow([r["id"],r["full_name"],r["age"] or "",r["institution"],r["position"],r["email"],r["course"],r["created_at"]])
    return FileResponse(out,media_type="text/csv",filename="alumnos_aula_medica.csv")



# ---------- VIDEOS MÉDICOS ----------
@app.get("/api/videos")
def list_videos():
    con=db()
    rows=[dict(r) for r in con.execute("SELECT * FROM medical_videos ORDER BY id DESC").fetchall()]
    con.close()
    return rows

@app.post("/api/videos")
async def add_video(
    request:Request,
    title:str=Form(...),
    description:str=Form(""),
    url:str=Form(...),
    category:str=Form("")
):
    auth(request)
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO medical_videos(title,description,url,category) VALUES(?,?,?,?)",
                (title.strip(),description.strip(),url.strip(),category.strip()))
    cur.execute("INSERT INTO activities(message) VALUES(?)",(f"Se agregó video: {title.strip()}",))
    con.commit(); con.close()
    return {"ok":True}

@app.delete("/api/videos/{video_id}")
def delete_video(video_id:int, request:Request):
    auth(request)
    con=db()
    con.execute("DELETE FROM medical_videos WHERE id=?",(video_id,))
    con.commit(); con.close()
    return {"ok":True}

# ---------- AUTOEVALUACIONES ----------
@app.get("/api/quizzes")
def list_quizzes():
    con=db()
    quizzes=[dict(r) for r in con.execute("""
      SELECT q.*, COALESCE(c.title,'General') AS course_title
      FROM quizzes q LEFT JOIN courses c ON c.id=q.course_id
      ORDER BY q.id DESC
    """).fetchall()]
    for q in quizzes:
        q["questions"]=[dict(r) for r in con.execute("""
          SELECT id,quiz_id,question,option_a,option_b,option_c,option_d,explanation
          FROM quiz_questions WHERE quiz_id=? ORDER BY id
        """,(q["id"],)).fetchall()]
    con.close()
    return quizzes

@app.post("/api/quizzes")
async def add_quiz(
    request:Request,
    title:str=Form(...),
    description:str=Form(""),
    course_id:int|None=Form(None)
):
    auth(request)
    con=db(); cur=con.cursor()
    cur.execute("INSERT INTO quizzes(title,description,course_id) VALUES(?,?,?)",
                (title.strip(),description.strip(),course_id))
    qid=cur.lastrowid
    con.commit(); con.close()
    return {"ok":True,"id":qid}

@app.post("/api/quizzes/{quiz_id}/questions")
async def add_quiz_question(
    quiz_id:int,
    request:Request,
    question:str=Form(...),
    option_a:str=Form(...),
    option_b:str=Form(...),
    option_c:str=Form(...),
    option_d:str=Form(...),
    correct:str=Form(...),
    explanation:str=Form("")
):
    auth(request)
    correct=correct.upper().strip()
    if correct not in {"A","B","C","D"}:
        raise HTTPException(400,"Respuesta correcta inválida")
    con=db()
    con.execute("""
      INSERT INTO quiz_questions(quiz_id,question,option_a,option_b,option_c,option_d,correct,explanation)
      VALUES(?,?,?,?,?,?,?,?)
    """,(quiz_id,question.strip(),option_a.strip(),option_b.strip(),option_c.strip(),option_d.strip(),correct,explanation.strip()))
    con.commit(); con.close()
    return {"ok":True}

@app.post("/api/quizzes/{quiz_id}/submit")
async def submit_quiz(quiz_id:int, payload:dict):
    student_name=(payload.get("student_name") or "").strip()
    email=(payload.get("email") or "").strip().lower()
    answers=payload.get("answers") or {}
    if len(student_name)<2:
        raise HTTPException(400,"Nombre requerido")
    con=db()
    qs=con.execute("SELECT id,correct,explanation FROM quiz_questions WHERE quiz_id=? ORDER BY id",(quiz_id,)).fetchall()
    score=0; review=[]
    for q in qs:
        selected=str(answers.get(str(q["id"]),"")).upper()
        ok=selected==q["correct"]
        if ok: score+=1
        review.append({"question_id":q["id"],"selected":selected,"correct":q["correct"],"ok":ok,"explanation":q["explanation"]})
    con.execute("INSERT INTO quiz_results(quiz_id,student_name,email,score,total) VALUES(?,?,?,?,?)",
                (quiz_id,student_name,email,score,len(qs)))
    con.commit(); con.close()
    return {"ok":True,"score":score,"total":len(qs),"review":review}

@app.get("/api/quiz-results")
def quiz_results(request:Request):
    auth(request)
    con=db()
    rows=[dict(r) for r in con.execute("""
      SELECT r.*, q.title AS quiz_title
      FROM quiz_results r JOIN quizzes q ON q.id=r.quiz_id
      ORDER BY r.id DESC
    """).fetchall()]
    con.close()
    return rows

@app.delete("/api/quizzes/{quiz_id}")
def delete_quiz(quiz_id:int, request:Request):
    auth(request)
    con=db()
    con.execute("DELETE FROM quiz_results WHERE quiz_id=?",(quiz_id,))
    con.execute("DELETE FROM quiz_questions WHERE quiz_id=?",(quiz_id,))
    con.execute("DELETE FROM quizzes WHERE id=?",(quiz_id,))
    con.commit(); con.close()
    return {"ok":True}

# ---------- CASOS CLÍNICOS Y DISCUSIÓN ----------
@app.get("/api/cases")
def list_cases():
    con=db()
    cases=[dict(r) for r in con.execute("SELECT * FROM clinical_cases ORDER BY id DESC").fetchall()]
    for c in cases:
        c["comments"]=[dict(r) for r in con.execute(
            "SELECT * FROM case_comments WHERE case_id=? ORDER BY id",(c["id"],)
        ).fetchall()]
    con.close()
    return cases

@app.post("/api/cases")
async def add_case(
    request:Request,
    title:str=Form(...),
    summary:str=Form(...),
    question:str=Form(""),
    category:str=Form("")
):
    auth(request)
    con=db()
    con.execute("INSERT INTO clinical_cases(title,summary,question,category) VALUES(?,?,?,?)",
                (title.strip(),summary.strip(),question.strip(),category.strip()))
    con.commit(); con.close()
    return {"ok":True}

@app.post("/api/cases/{case_id}/comments")
async def add_case_comment(case_id:int, author:str=Form(...), comment:str=Form(...)):
    author=author.strip(); comment=comment.strip()
    if len(author)<2 or len(comment)<3:
        raise HTTPException(400,"Comentario incompleto")
    con=db()
    exists=con.execute("SELECT 1 FROM clinical_cases WHERE id=?",(case_id,)).fetchone()
    if not exists:
        con.close(); raise HTTPException(404,"Caso no encontrado")
    con.execute("INSERT INTO case_comments(case_id,author,comment) VALUES(?,?,?)",(case_id,author,comment))
    con.commit(); con.close()
    return {"ok":True}

@app.delete("/api/cases/{case_id}")
def delete_case(case_id:int, request:Request):
    auth(request)
    con=db()
    con.execute("DELETE FROM case_comments WHERE case_id=?",(case_id,))
    con.execute("DELETE FROM clinical_cases WHERE id=?",(case_id,))
    con.commit(); con.close()
    return {"ok":True}


@app.get("/api/export")
def export_data(request:Request):
    auth(request)
    con=db()
    data={
      "courses":[dict(r) for r in con.execute("SELECT * FROM courses").fetchall()],
      "lessons":[dict(r) for r in con.execute("SELECT * FROM lessons").fetchall()],
      "students":[dict(r) for r in con.execute("SELECT * FROM students").fetchall()],
      "videos":[dict(r) for r in con.execute("SELECT * FROM medical_videos").fetchall()],
      "quizzes":[dict(r) for r in con.execute("SELECT * FROM quizzes").fetchall()],
      "quiz_results":[dict(r) for r in con.execute("SELECT * FROM quiz_results").fetchall()],
      "clinical_cases":[dict(r) for r in con.execute("SELECT * FROM clinical_cases").fetchall()],
      "case_comments":[dict(r) for r in con.execute("SELECT * FROM case_comments").fetchall()],
      "activities":[dict(r) for r in con.execute("SELECT * FROM activities").fetchall()]
    }
    con.close()
    out=BASE/"aula_export.json"
    out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    return FileResponse(out,filename="aula_medica_dr_villalobos_export.json")

@app.get("/health")
def health():
    return {"ok":True}
