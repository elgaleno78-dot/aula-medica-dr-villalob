"""Sincronización idempotente de MP4 de Drive al Aula AVICO Educación.
No toca cursos de Hemorragia ni elimina lecciones.
"""
import os
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

FOLDER_ID = "18jrR5TnL-Qxh5ktar2r_mg8dfIi0KYeW"
CREDENTIALS = "/etc/secrets/google-drive-service-account.json"
COURSE_TITLE = "AVICO® Educación — Ponencias"
CATEGORY = "Obstetricia clínica"

def sync(db):
    if not os.path.isfile(CREDENTIALS):
        raise RuntimeError("Falta credencial privada Google Drive")
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    session = AuthorizedSession(credentials)
    items, token = [], None
    while True:
        params = {
            "q": "'" + FOLDER_ID + "' in parents and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType,size)",
            "pageSize": 100,
        }
        if token:
            params["pageToken"] = token
        response = session.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=25)
        response.raise_for_status()
        payload = response.json()
        items.extend(payload.get("files", []))
        token = payload.get("nextPageToken")
        if not token:
            break
    videos = sorted(
        [item for item in items if item.get("mimeType") in ("video/mp4", "video/quicktime", "video/webm")],
        key=lambda item: item.get("name", "").casefold()
    )
    con = db()
    added = 0
    try:
        con.execute("BEGIN IMMEDIATE")
        course = con.execute("SELECT id FROM courses WHERE title=?", (COURSE_TITLE,)).fetchone()
        if not course and videos:
            con.execute(
                "INSERT INTO courses(title,subtitle,category,published) VALUES(?,?,?,1)",
                (COURSE_TITLE, "Ponencias audiovisuales de AVICO Educación", CATEGORY)
            )
            course = con.execute("SELECT id FROM courses WHERE title=?", (COURSE_TITLE,)).fetchone()
        if course:
            for item in videos:
                file_id = item["id"]
                exists = con.execute(
                    "SELECT id FROM lessons WHERE course_id=? AND kind='drive' AND filename=?",
                    (course["id"], file_id)
                ).fetchone()
                if exists:
                    continue
                title = item["name"].rsplit(".", 1)[0].replace("_", " ").strip()
                order = con.execute(
                    "SELECT COALESCE(MAX(ord),0)+1 FROM lessons WHERE course_id=?",
                    (course["id"],)
                ).fetchone()[0]
                con.execute(
                    "INSERT INTO lessons(course_id,title,kind,filename,notes,ord) VALUES(?,?,?,?,?,?)",
                    (course["id"], title, "drive", file_id, "Ponencia incorporada automáticamente desde Drive.", order)
                )
                added += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return {"videos_en_carpeta": len(videos), "ponencias_nuevas": added}
