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
                "FRONTEND_ORIGINS": "http://localhost:8000",
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

    def test_cors_allows_configured_frontend_origin_and_preflight(self):
        headers = {
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        response = self.client.options("/api/auth/login", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"], "http://localhost:8000"
        )
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])

    def test_cors_does_not_allow_unconfigured_origin(self):
        response = self.client.get("/", headers={"Origin": "https://unknown.example"})
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_register_and_get_user_profile(self):
        response = self.register_user()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.get_json()["user"])
        self.assertIn("access_token", response.get_json())

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

    def test_user_can_submit_donation_and_admin_can_list_it(self):
        registration = self.register_user().get_json()
        user_token = registration["access_token"]
        donation_response = self.client.post(
            "/api/donations",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "object_type": "Ropa",
                "shelter_name": "Albergue Esperanza",
                "message": "Donaré ropa en buen estado.",
            },
        )
        self.assertEqual(donation_response.status_code, 201)
        donation = donation_response.get_json()["donation"]
        self.assertEqual(donation["object_type"], "Ropa")
        self.assertEqual(donation["user"]["email"], "persona@example.com")

        admin_login = self.client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "admin-password"},
        ).get_json()
        admin_response = self.client.get(
            "/api/admin/donations",
            headers={"Authorization": f"Bearer {admin_login['access_token']}"},
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(len(admin_response.get_json()["donations"]), 1)

    def test_donation_routes_enforce_roles_and_validate_fields(self):
        user_token = self.register_user().get_json()["access_token"]
        invalid_donation = self.client.post(
            "/api/donations",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"object_type": "", "shelter_name": "Albergue", "message": "Mensaje"},
        )
        self.assertEqual(invalid_donation.status_code, 400)
        self.assertEqual(
            self.client.get(
                "/api/admin/donations",
                headers={"Authorization": f"Bearer {user_token}"},
            ).status_code,
            403,
        )

        admin_token = self.client.post(
            "/api/admin/login",
            json={"username": "admin", "password": "admin-password"},
        ).get_json()["access_token"]
        self.assertEqual(
            self.client.post(
                "/api/donations",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "object_type": "Ropa",
                    "shelter_name": "Albergue",
                    "message": "Mensaje",
                },
            ).status_code,
            403,
        )

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
