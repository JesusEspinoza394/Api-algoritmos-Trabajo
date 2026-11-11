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
    "alimentos": 1,
    "ropa y calzado": 1,
    "higiene personal": 2,
    "juguetes": 3,
    "utiles escolares": 3,
    "otro": 4,
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
class Node:
    def __init__(self, donation_data):
        self.data = donation_data
        self.priority = donation_data.get("priority", 4)
        self.donation_id = donation_data.get("id")
        self.prev = None
        self.next = None


class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None

    def is_empty(self):
        return self.head is None

    def insert_sorted(self, donation_data):
        """Inserta ordenado por Prioridad (ascendente) y luego por ID (ascendente)."""
        new_node = Node(donation_data)
        
        if self.is_empty():
            self.head = self.tail = new_node
            return

        current = self.head
        while current is not None:
            if (new_node.priority < current.priority) or \
               (new_node.priority == current.priority and new_node.donation_id < current.donation_id):
                new_node.next = current
                new_node.prev = current.prev
                if current.prev is not None:
                    current.prev.next = new_node
                else:
                    self.head = new_node
                current.prev = new_node
                return
            current = current.next

        self.tail.next = new_node
        new_node.prev = self.tail
        self.tail = new_node

    def to_list(self):
        elements = []
        current = self.head
        while current is not None:
            elements.append(current.data)
            current = current.next
        return elements


def binary_search_by_priority_and_id(donations_list, target_priority, target_id):
    """Búsqueda binaria eficiente sobre una lista ordenada por (prioridad, id)."""
    left = 0
    right = len(donations_list) - 1

    while left <= right:
        mid = (left + right) // 2
        item = donations_list[mid]
        
        curr_priority = item.get("priority") if isinstance(item, dict) else item.priority
        curr_id = item.get("id") if isinstance(item, dict) else item.id

        current_tuple = (curr_priority, curr_id)
        target_tuple = (target_priority, target_id)

        if current_tuple == target_tuple:
            return item
        elif current_tuple < target_tuple:
            left = mid + 1
        else:
            right = mid - 1
            
    return None


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
            
            # Construimos la cola de prioridad usando la Lista Doblemente Enlazada
            priority_list = DoublyLinkedList()
            for donation in pending_donations:
                item_dict = donation.to_dict(include_priority=True)
                node_payload = {
                    "priority": donation.priority,
                    "timestamp": donation.created_at.timestamp(),
                    "id": donation.id,
                    "data": item_dict
                }
                priority_list.insert_sorted(node_payload)
            
            raw_nodes = priority_list.to_list()
            donations = [node["data"] for node in raw_nodes]
        else:
            sent_donations = db.session.scalars(
                db.select(Donation)
                .where(Donation.status == "sent")
                .order_by(Donation.sent_at.desc(), Donation.id.desc())
            ).all()
            donations = [donation.to_dict(include_priority=True) for donation in sent_donations]

        supported_shelter_count = db.session.scalar(
            db.select(db.func.count(Donation.id)).where(Donation.status == "sent")
        )
        donation_counts = db.session.execute(
            db.select(Donation.user_id, db.func.count(Donation.id))
            .group_by(Donation.user_id)
        ).all()
        return jsonify()
            donations=donations,
            supported_shelter_count=supported_shelter_count,
            donation_counts_by_user=dict(donation_counts),
    @app.get("/api/admin/donations/search")
    @jwt_required()
    def search_donation_binary_endpoint():
        if get_jwt().get("role") != "admin":
            return jsonify(error="No tienes permisos para realizar esta búsqueda."), 403

        try:
            target_priority = int(request.args.get("priority"))
            target_id = int(request.args.get("id"))
        except (TypeError, ValueError):
            return jsonify(error="Debes proporcionar parámetros válidos 'priority' e 'id' como enteros."), 400

        pending_donations = db.session.scalars(
            db.select(Donation).where(Donation.status == "pending")
        ).all()

        priority_list = DoublyLinkedList()
        for donation in pending_donations:
            priority_list.insert_sorted({
                "priority": donation.priority,
                "timestamp": donation.created_at.timestamp(),
                "id": donation.id,
                "data": donation.to_dict(include_priority=True)
            })

        raw_items = priority_list.to_list()
        sorted_items = sorted(raw_items, key=lambda x: (x["priority"], x["id"]))
        donations_array = [item["data"] for item in sorted_items]

        result = binary_search_by_priority_and_id(donations_array, target_priority, target_id)

        if result:
            return jsonify(found=True, donation=result), 200
        else:
            return jsonify(found=False, message="Donación no encontrada con esos criterios en la cola activa."), 404
