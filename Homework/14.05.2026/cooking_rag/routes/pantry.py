from bson import ObjectId
from flask import Blueprint, render_template, request, jsonify

from auth_utils import get_current_user, login_required
from db import get_db

pantry_bp = Blueprint("pantry", __name__, url_prefix="/pantry")


@pantry_bp.route("/")
@login_required
def pantry_page():
    user = get_current_user()
    db = get_db()
    user_doc = db.users.find_one({"_id": ObjectId(user["sub"])}, {"pantry": 1})
    pantry = sorted(user_doc.get("pantry", [])) if user_doc else []
    return render_template("pantry/index.html", pantry=pantry)


@pantry_bp.route("/ingredients", methods=["GET"])
@login_required
def get_ingredients():
    user = get_current_user()
    db = get_db()
    user_doc = db.users.find_one({"_id": ObjectId(user["sub"])}, {"pantry": 1})
    pantry = sorted(user_doc.get("pantry", [])) if user_doc else []
    return jsonify({"ingredients": pantry})


@pantry_bp.route("/ingredients", methods=["POST"])
@login_required
def add_ingredient():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    ingredient = (data.get("ingredient") or "").strip().lower()

    if not ingredient:
        return jsonify({"error": "Ingredient name is required"}), 400
    if len(ingredient) > 100:
        return jsonify({"error": "Ingredient name is too long"}), 400

    db = get_db()
    db.users.update_one(
        {"_id": ObjectId(user["sub"])},
        {"$addToSet": {"pantry": ingredient}},
    )
    return jsonify({"message": f"Added '{ingredient}' to your pantry"})


@pantry_bp.route("/ingredients/<path:ingredient>", methods=["DELETE"])
@login_required
def remove_ingredient(ingredient: str):
    user = get_current_user()
    ingredient = ingredient.strip().lower()
    db = get_db()
    db.users.update_one(
        {"_id": ObjectId(user["sub"])},
        {"$pull": {"pantry": ingredient}},
    )
    return jsonify({"message": f"Removed '{ingredient}' from your pantry"})


@pantry_bp.route("/clear", methods=["POST"])
@login_required
def clear_pantry():
    user = get_current_user()
    db = get_db()
    db.users.update_one(
        {"_id": ObjectId(user["sub"])},
        {"$set": {"pantry": []}},
    )
    return jsonify({"message": "Pantry cleared"})
