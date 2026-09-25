import os, tempfile, importlib, unittest
from unittest.mock import patch
from pathlib import Path

tmp=tempfile.TemporaryDirectory()
os.environ["AULA_DATA_DIR"]=tmp.name
os.environ["AULA_ADMIN_PASSWORD"]="test-admin-password"
appmod=importlib.import_module("app")
from fastapi.testclient import TestClient

class StudentAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(appmod.app)
        cls.client.__enter__()
    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None,None,None)
        tmp.cleanup()
    def test_account_enrollment_and_file_protection(self):
        client=self.client
        user={"full_name":"Alumno Prueba","email":"alumno@example.org","password":"UnaClaveDePruebaSegura2026!"}
        with patch.dict(os.environ,{"AULA_PUBLIC_URL":"https://example.org"}), patch.object(appmod,"mail_configured",return_value=True), patch.object(appmod,"send_student_email") as sender:
            signup=client.post("/api/student-auth/register",json=user)
            self.assertEqual(sender.call_count,1)
        self.assertEqual(signup.status_code,200,signup.text)
        token=signup.json()["token"]
        with patch.object(appmod,"mail_configured",return_value=True):
            self.assertEqual(client.post("/api/student-auth/register",json=user).status_code,409)
        self.assertEqual(client.post("/api/student-auth/login",json={"email":user["email"],"password":"incorrecta"}).status_code,401)
        self.assertEqual(client.get("/api/student-auth/me",headers={"Authorization":"Bearer "+token}).status_code,200)
        self.assertEqual(client.get("/uploads/no-such-file.pdf").status_code,401)
        self.assertEqual(client.post("/api/register",data={"full_name":user["full_name"],"email":user["email"],"course_id":1}).status_code,401)
        with patch.object(appmod,"mail_configured",return_value=False):
            enrolled=client.post("/api/register",data={"full_name":user["full_name"],"email":user["email"],"course_id":1},headers={"Authorization":"Bearer "+token})
        self.assertEqual(enrolled.status_code,200,enrolled.text)
        me=client.get("/api/student-auth/me",headers={"Authorization":"Bearer "+token}).json()
        self.assertEqual(len(me["enrollments"]),1)
        self.assertEqual(me["enrollments"][0]["access_token"],enrolled.json()["access_token"])
        self.assertEqual(client.post("/api/student-auth/logout",headers={"Authorization":"Bearer "+token}).status_code,200)
        self.assertEqual(client.get("/api/student-auth/me",headers={"Authorization":"Bearer "+token}).status_code,401)
    def test_password_recovery_invalidates_sessions(self):
        client=self.client
        user={"full_name":"Alumno Recuperacion","email":"recuperacion@example.org","password":"ClaveAnteriorSegura2026!"}
        captured=[]
        def capture_email(to_email,subject,message):
            captured.append(message)
        with patch.dict(os.environ,{"AULA_PUBLIC_URL":"https://example.org"}), patch.object(appmod,"mail_configured",return_value=True), patch.object(appmod,"send_student_email",side_effect=capture_email):
            created=client.post("/api/student-auth/register",json=user)
            self.assertEqual(created.status_code,200,created.text)
            old_session=created.json()["token"]
            requested=client.post("/api/student-auth/request-reset",json={"email":user["email"]})
            self.assertEqual(requested.status_code,200,requested.text)
        from urllib.parse import urlsplit,parse_qs
        link=[line for line in captured[-1].splitlines() if line.startswith("https://")][0]
        reset_token=parse_qs(urlsplit(link).query)["token"][0]
        updated=client.post("/api/student-auth/reset-password",json={"token":reset_token,"password":"ClaveNuevaSegura2026!"})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(client.post("/api/student-auth/reset-password",json={"token":reset_token,"password":"OtraClaveSegura2026!"}).status_code,400)
        self.assertEqual(client.get("/api/student-auth/me",headers={"Authorization":"Bearer "+old_session}).status_code,401)
        self.assertEqual(client.post("/api/student-auth/login",json={"email":user["email"],"password":user["password"]}).status_code,401)
        self.assertEqual(client.post("/api/student-auth/login",json={"email":user["email"],"password":"ClaveNuevaSegura2026!"}).status_code,200)
    def test_existing_database_migration(self):
        con=appmod.db()
        columns={r["name"] for r in con.execute("PRAGMA table_info(students)")}
        self.assertIn("account_id",columns)
        con.close()

if __name__=="__main__":unittest.main()
