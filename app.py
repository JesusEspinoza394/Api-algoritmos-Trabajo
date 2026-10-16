import heapq
import hmac
import os
import unicodedata
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, get_jwt_identity, jwt_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
jwt = JWTManager()

DONATION_PRIORITIES = {
    "juguetes": 1,
    "utiles escolares": 1,
    "higiene personal": 2,
    "ropa y calzado": 3,
    "alimentos": 4,
    "otro": 1,
}


def normalize_donation_type(value):
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    ).strip()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    age = db.Column(db.Integer, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "age": self.age,
        }


class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    object_type = db.Column(db.String(120), nullable=False)
    priority = db.Column(db.Integer, nullable=False, index=True)
    shelter_name = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(2000), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    user = db.relationship("User", backref=db.backref("donations", lazy=True))

    def to_dict(self, include_priority=False):
        donation_data = {
            "id": self.id,
            "object_type": self.object_type,
            "shelter_name": self.shelter_name,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "user": {
                "id": self.user.id,
                "name": self.user.name,
                "email": self.user.email,
            },
        }
        if include_priority:
            donation_data["priority"] = self.priority
            donation_data["status"] = self.status
            donation_data["sent_at"] = self.sent_at.isoformat() if self.sent_at else None
        return donation_data


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
        ADMIN_USERNAME=os.getenv("ADMIN_USERNAME"),
        ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD"),
        FRONTEND_ORIGINS=os.getenv(
            "FRONTEND_ORIGINS",
            "http://127.0.0.1:8000,http://localhost:8000",
        ),
    )
    if test_config:
        app.config.update(test_config)

    required_settings = (
        "SQLALCHEMY_DATABASE_URI",
        "JWT_SECRET_KEY",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
    )
    missing_settings = [key for key in required_settings if not app.config.get(key)]
    if missing_settings:
        raise RuntimeError(
            "Faltan variables de configuración requeridas: "
            + ", ".join(missing_settings)
        )

    db.init_app(app)
    jwt.init_app(app)

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        allowed_origins = app.config["FRONTEND_ORIGINS"]
        if isinstance(allowed_origins, str):
            allowed_origins = {
                item.strip() for item in allowed_origins.split(",") if item.strip()
            }
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.vary.add("Origin")
        return response

    @app.get("/")
    def index():
        return jsonify(
            status="ok",
            message="API de donaciones activa.",
            endpoints={
                "register": "/api/auth/register",
                "user_login": "/api/auth/login",
                "admin_login": "/api/admin/login",
                "create_donation": "/api/donations",
                "admin_donations": "/api/admin/donations",
                "send_donation": "/api/admin/donations/<id>/send",
            },
        ), 200

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Se requiere un objeto JSON válido."), 400

        name = data.get("name")
        email = data.get("email")
        age = data.get("age")
        password = data.get("password")

        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            return jsonify(error="El nombre es obligatorio y debe tener máximo 120 caracteres."), 400
        if not isinstance(email, str) or len(email) > 254:
            return jsonify(error="Ingresa un correo electrónico válido."), 400
        try:
            normalized_email = validate_email(
                email.strip(), check_deliverability=False
            ).normalized.lower()
        except EmailNotValidError:
            return jsonify(error="Ingresa un correo electrónico válido."), 400
        if isinstance(age, bool) or not isinstance(age, int) or not 0 <= age <= 120:
            return jsonify(error="La edad debe ser un número entero entre 0 y 120."), 400
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            return jsonify(error="La contraseña debe tener entre 8 y 128 caracteres."), 400
        if db.session.scalar(
            db.select(User).where(User.email == normalized_email)
        ):
            return jsonify(error="Ya existe una cuenta con ese correo electrónico."), 409

        user = User(
            name=name.strip(),
            email=normalized_email,
            age=age,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify(error="Ya existe una cuenta con ese correo electrónico."), 409

        access_token = create_access_token(
            identity=str(user.id), additional_claims={"role": "user"}
        )
        return jsonify(
            message="Usuario registrado correctamente.",
            access_token=access_token,
            user=user.to_dict(),
        ), 201

    @app.post("/api/auth/login")
    def user_login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Se requiere un objeto JSON válido."), 400

        email = data.get("email")
        password = data.get("password")
        if not isinstance(email, str) or not isinstance(password, str):
            return jsonify(error="Correo electrónico y contraseña son obligatorios."), 400

        user = db.session.scalar(
            db.select(User).where(User.email == email.strip().lower())
        )
        if user is None or not check_password_hash(user.password_hash, password):
            return jsonify(error="Correo electrónico o contraseña incorrectos."), 401

        access_token = create_access_token(
            identity=str(user.id), additional_claims={"role": "user"}
        )
        return jsonify(access_token=access_token, user=user.to_dict()), 200

    @app.post("/api/admin/login")
    def admin_login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Se requiere un objeto JSON válido."), 400

        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify(error="Usuario y contraseña son obligatorios."), 400
        if (
            username != app.config["ADMIN_USERNAME"]
            or not hmac.compare_digest(password, app.config["ADMIN_PASSWORD"])
        ):
            return jsonify(error="Credenciales de administrador incorrectas."), 401

        access_token = create_access_token(
            identity=username, additional_claims={"role": "admin"}
        )
        return jsonify(access_token=access_token), 200

    @app.get("/api/users/me")
    @jwt_required()
    def user_profile():
        if get_jwt().get("role") != "user":
            return jsonify(error="No tienes permisos para consultar este recurso."), 403
        try:
            user_id = int(get_jwt_identity())
        except (TypeError, ValueError):
            return jsonify(error="Token de usuario no válido."), 401
        user = db.session.get(User, user_id)
        if user is None:
            return jsonify(error="Usuario no encontrado."), 404
        return jsonify(user=user.to_dict()), 200

    @app.get("/api/admin/me")
    @jwt_required()
    def admin_profile():
        if get_jwt().get("role") != "admin":
            return jsonify(error="No tienes permisos para consultar este recurso."), 403
        return jsonify(username=get_jwt_identity(), role="admin"), 200

    @app.post("/api/donations")
    @jwt_required()
    def create_donation():
        if get_jwt().get("role") != "user":
            return jsonify(error="Solo los usuarios pueden registrar donaciones."), 403
        try:
            user_id = int(get_jwt_identity())
        except (TypeError, ValueError):
            return jsonify(error="Token de usuario no válido."), 401

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Se requiere un objeto JSON válido."), 400

        object_type = data.get("object_type")
        shelter_name = data.get("shelter_name")
        message = data.get("message")
        if not isinstance(object_type, str) or not object_type.strip() or len(object_type.strip()) > 120:
            return jsonify(error="Indica el tipo de objeto (máximo 120 caracteres)."), 400
        priority = DONATION_PRIORITIES.get(normalize_donation_type(object_type))
        if priority is None:
            return jsonify(error="El tipo de objeto seleccionado no es válido."), 400
        if not isinstance(shelter_name, str) or not shelter_name.strip() or len(shelter_name.strip()) > 160:
            return jsonify(error="Indica el nombre del albergue (máximo 160 caracteres)."), 400
        if not isinstance(message, str) or not message.strip() or len(message.strip()) > 2000:
            return jsonify(error="Escribe un mensaje de hasta 2000 caracteres."), 400

        donation = Donation(
            user_id=user_id,
            object_type=object_type.strip(),
            priority=priority,
            shelter_name=shelter_name.strip(),
            message=message.strip(),
        )
        db.session.add(donation)
        db.session.commit()
        return jsonify(
            message="Gracias por tu generosidad.",
            donation=donation.to_dict(),
        ), 201

    @app.get("/api/admin/donations")
    @jwt_required()
    def list_donations():
        if get_jwt().get("role") != "admin":
            return jsonify(error="No tienes permisos para consultar las donaciones."), 403
        status = request.args.get("status", "pending")
        if status not in {"pending", "sent"}:
            return jsonify(error="El estado debe ser 'pending' o 'sent'."), 400

        if status == "pending":
            pending_donations = db.session.scalars(
                db.select(Donation).where(Donation.status == "pending")
            ).all()
            priority_queue = []
            for donation in pending_donations:
                heapq.heappush(
                    priority_queue,
                    (
                        donation.priority,
                        donation.created_at.timestamp(),
                        donation.id,
                        donation,
                    ),
                )
            donations = [
                heapq.heappop(priority_queue)[-1]
                for _ in range(len(priority_queue))
            ]
        else:
            donations = db.session.scalars(
                db.select(Donation)
                .where(Donation.status == "sent")
                .order_by(Donation.sent_at.desc(), Donation.id.desc())
            ).all()
        return jsonify(
            donations=[
                donation.to_dict(include_priority=True) for donation in donations
            ]
        ), 200

    @app.post("/api/admin/donations/<int:donation_id>/send")
    @jwt_required()
    def send_donation(donation_id):
        if get_jwt().get("role") != "admin":
            return jsonify(error="No tienes permisos para enviar donaciones."), 403

        sent_at = datetime.now(timezone.utc)
        result = db.session.execute(
            db.update(Donation)
            .where(
                Donation.id == donation_id,
                Donation.status == "pending",
            )
            .values(status="sent", sent_at=sent_at)
        )
        if result.rowcount != 1:
            db.session.rollback()
            donation = db.session.get(Donation, donation_id)
            if donation is None:
                return jsonify(error="Donación no encontrada."), 404
            return jsonify(error="Esta donación ya fue enviada."), 409

        db.session.commit()
        donation = db.session.get(Donation, donation_id)
        if donation is None:
            return jsonify(error="Donación no encontrada."), 404
        return jsonify(
            message="Donación marcada como enviada.",
            donation=donation.to_dict(include_priority=True),
        ), 200

    @app.cli.command("init-db")
    def init_db():
        """Create the database tables."""
        with app.app_context():
            db.create_all()
        print("Tablas creadas correctamente.")

    return app
