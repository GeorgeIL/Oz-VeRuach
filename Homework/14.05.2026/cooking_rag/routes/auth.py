import re
from datetime import datetime, timezone

from bson import ObjectId
from flask import (
    Blueprint,
    make_response,
    redirect,
    render_template,
    request,
    jsonify,
    url_for,
)

from auth_utils import check_password, create_token, get_current_user, hash_password
from db import get_db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── Login ─────────────────────────────────────────────────────────────────────


@auth_bp.route("/login")
def login_page():
    if get_current_user():
        return redirect(url_for("home"))
    return render_template("auth/login.html")


@auth_bp.route("/login", methods=["POST"])
def login_post():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = get_db()
    user = db.users.find_one({"email": email})

    if not user or not check_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401

    token = create_token(str(user["_id"]), user["username"])
    resp = make_response(
        jsonify(
            {
                "message": "Login successful",
                "username": user["username"],
                "redirect": url_for("home"),
            }
        )
    )
    resp.set_cookie(
        "token",
        token,
        httponly=True,
        samesite="Lax",
        max_age=86400,
    )
    return resp


# ── Sign-up ───────────────────────────────────────────────────────────────────


@auth_bp.route("/signup")
def signup_page():
    if get_current_user():
        return redirect(url_for("home"))
    return render_template("auth/signup.html")


@auth_bp.route("/signup", methods=["POST"])
def signup_post():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    # --- Input validation ---
    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if not (3 <= len(username) <= 30):
        return jsonify({"error": "Username must be 3–30 characters"}), 400
    if not re.fullmatch(r"[a-zA-Z0-9_]+", username):
        return (
            jsonify(
                {"error": "Username may only contain letters, numbers and underscores"}
            ),
            400,
        )
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if not re.fullmatch(r"[\w.\-+]+@[\w.\-]+\.\w{2,}", email):
        return jsonify({"error": "Invalid email address"}), 400

    db = get_db()
    if db.users.find_one({"email": email}):
        return jsonify({"error": "Email already registered"}), 409
    if db.users.find_one({"username": username}):
        return jsonify({"error": "Username already taken"}), 409

    user_doc = {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "pantry": [],
        "created_at": datetime.now(timezone.utc),
    }
    result = db.users.insert_one(user_doc)
    token = create_token(str(result.inserted_id), username)

    resp = make_response(
        jsonify(
            {
                "message": "Account created successfully",
                "username": username,
                "redirect": url_for("home"),
            }
        ),
        201,
    )
    resp.set_cookie("token", token, httponly=True, samesite="Lax", max_age=86400)
    return resp


# ── Logout ────────────────────────────────────────────────────────────────────


@auth_bp.route("/logout", methods=["POST"])
def logout():
    resp = make_response(redirect(url_for("auth.login_page")))
    resp.delete_cookie("token")
    return resp


# ── Current user (API) ────────────────────────────────────────────────────────


@auth_bp.route("/me")
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify({"user_id": user["sub"], "username": user["username"]})
