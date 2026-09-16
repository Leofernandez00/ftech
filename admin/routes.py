from flask import Flask
from config import Config
from models import db, Product
from admin.routes import admin_bp

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Registre o Blueprint para o painel administrativo
app.register_blueprint(admin_bp, url_prefix='/admin')

@app.route('/')
def home():
    products = Product.query.all()
    return render_template('home.html', products=products)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
