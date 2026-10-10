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
    pending = 0
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS education_drive_reviews(
            file_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        for item in videos:
            file_id = item["id"]
            title = item["name"].rsplit(".", 1)[0].replace("_", " ").strip()
            exists = con.execute("SELECT 1 FROM lessons WHERE kind='drive' AND filename=?", (file_id,)).fetchone()
            if exists:
                continue
            con.execute(
                "INSERT OR IGNORE INTO education_drive_reviews(file_id,title,status) VALUES(?,?,'pending')",
                (file_id, title)
            )
        pending = con.execute("SELECT COUNT(*) FROM education_drive_reviews WHERE status='pending'").fetchone()[0]
        con.commit()
    finally:
        con.close()
    return {"videos_en_carpeta": len(videos), "pendientes": pending}
