import hmac
import os
from datetime import timedelta

from dotenv import load_dotenv
from email_validator import EmailNotValidError, validate_email
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, get_jwt, get_jwt_identity, jwt_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
jwt = JWTManager()


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

        return jsonify(message="Usuario registrado correctamente.", user=user.to_dict()), 201

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

    @app.cli.command("init-db")
    def init_db():
        """Create the database tables."""
        with app.app_context():
            db.create_all()
        print("Tablas creadas correctamente.")

    return app
