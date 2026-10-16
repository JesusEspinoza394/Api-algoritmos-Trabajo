import unittest

from app import create_app, db


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "JWT_SECRET_KEY": "test-secret-that-is-at-least-32-bytes",
                "ADMIN_USERNAME": "admin",
                "ADMIN_PASSWORD": "admin-password",
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def register_user(self, email="persona@example.com"):
        return self.client.post(
            "/api/auth/register",
            json={
                "name": "Persona",
                "email": email,
                "age": 25,
                "password": "password-segura",
            },
        )

    def test_root_reports_api_is_active(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        self.assertIn("/api/auth/register", response.get_json()["endpoints"].values())

    def test_register_and_get_user_profile(self):
        response = self.register_user()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.get_json()["user"])

        login = self.client.post(
            "/api/auth/login",
            json={"email": "PERSONA@example.com", "password": "password-segura"},
        )
        self.assertEqual(login.status_code, 200)
        token = login.get_json()["access_token"]

        profile = self.client.get(
            "/api/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.get_json()["user"]["email"], "persona@example.com")

    def test_registration_rejects_invalid_age_and_duplicate_email(self):
        invalid_age = self.client.post(
            "/api/auth/register",
            json={
                "name": "Persona",
                "email": "persona@example.com",
                "age": True,
                "password": "password-segura",
            },
        )
        self.assertEqual(invalid_age.status_code, 400)
        self.assertEqual(self.register_user().status_code, 201)
        self.assertEqual(self.register_user().status_code, 409)

    def test_admin_login_returns_admin_token_and_rejects_user_token(self):
        admin_login = self.client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "admin-password"},
        )
        self.assertEqual(admin_login.status_code, 200)
        admin_token = admin_login.get_json()["access_token"]
        self.assertEqual(
            self.client.get(
                "/api/admin/me",
                headers={"Authorization": f"Bearer {admin_token}"},
            ).status_code,
            200,
        )

        self.register_user()
        user_token = self.client.post(
            "/api/auth/login",
            json={"email": "persona@example.com", "password": "password-segura"},
        ).get_json()["access_token"]
        self.assertEqual(
            self.client.get(
                "/api/admin/me",
                headers={"Authorization": f"Bearer {user_token}"},
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main()
