from flask import Blueprint, render_template, redirect, url_for, request, session
from models import db, User, Product

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Implementação do login aqui

@admin_bp.route('/add_product', methods=['GET', 'POST'])
def add_product():
    # Implementação de cadastro de produto aqui
