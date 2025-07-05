# app.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime

# --- Configuración de la Aplicación ---
app = Flask(__name__)

# Configuración de la base de datos SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'una_clave_secreta_muy_segura' # Necesario para flash messages

db = SQLAlchemy(app)

@app.context_processor
def inject_now():
    """Inyecta la fecha y hora actual ('now') en todas las plantillas."""
    return {'now': datetime.utcnow()} # Usa datetime.utcnow() para UTC o datetime.now() para la hora local

# --- Modelos de Base de Datos ---

class Sabor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    precio = db.Column(db.Float, nullable=False)
    disponible = db.Column(db.Boolean, default=True) # Si está en stock o no
    # CAMBIO IMPORTANTE AQUÍ: default sin 'static/'
    imagen_url = db.Column(db.String(200), nullable=True, default='img/default_sabor.png') # Ruta de imagen

    def __repr__(self):
        return f'<Sabor {self.nombre}>'

    def serialize(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'precio': self.precio,
            'disponible': self.disponible,
            'imagen_url': self.imagen_url
        }

# --- Creación de la Base de Datos y Carga de Datos Iniciales (SOLO EN EL MAIN BLOCK) ---
# Hemos quitado el @app.before_request create_tables de aquí, ya que causaba el error de contexto.
# Toda la lógica de inicialización se mueve al if __name__ == "__main__":

# --- Rutas de la API (JSON) ---

@app.route('/api/sabores', methods=['GET', 'POST'])
def api_sabores():
    if request.method == 'GET':
        sabores = Sabor.query.all()
        return jsonify([sabor.serialize() for sabor in sabores]), 200
    elif request.method == 'POST':
        data = request.get_json()
        if not data or not all(key in data for key in ['nombre', 'precio']):
            return jsonify({"error": "Faltan campos obligatorios: nombre, precio"}), 400

        if not isinstance(data['precio'], (int, float)) or data['precio'] <= 0:
            return jsonify({"error": "El precio debe ser un número positivo."}), 400

        if Sabor.query.filter_by(nombre=data['nombre']).first():
            return jsonify({"error": "Ya existe un sabor con ese nombre."}), 409

        try:
            nuevo_sabor = Sabor(
                nombre=data['nombre'],
                descripcion=data.get('descripcion'),
                precio=data['precio'],
                disponible=data.get('disponible', True),
                # CAMBIO AQUÍ: default para la API POST
                imagen_url=data.get('imagen_url', 'img/default_sabor.png')
            )
            db.session.add(nuevo_sabor)
            db.session.commit()
            return jsonify({"message": "Sabor creado exitosamente", "sabor": nuevo_sabor.serialize()}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al crear el sabor: {str(e)}"}), 500

@app.route('/api/sabores/<int:sabor_id>', methods=['GET', 'PUT', 'DELETE'])
def api_sabor_detalle(sabor_id):
    sabor = Sabor.query.get_or_404(sabor_id)

    if request.method == 'GET':
        return jsonify(sabor.serialize()), 200
    elif request.method == 'PUT':
        data = request.get_json()
        if not data:
            return jsonify({"error": "No se proporcionaron datos para actualizar"}), 400

        try:
            if 'nombre' in data:
                sabor.nombre = data['nombre']
            if 'descripcion' in data:
                sabor.descripcion = data['descripcion']
            if 'precio' in data:
                if not isinstance(data['precio'], (int, float)) or data['precio'] <= 0:
                    return jsonify({"error": "El precio debe ser un número positivo."}), 400
                sabor.precio = data['precio']
            if 'disponible' in data:
                sabor.disponible = data['disponible']
            if 'imagen_url' in data:
                # CAMBIO AQUÍ: actualiza la URL si viene en el JSON
                sabor.imagen_url = data['imagen_url']

            db.session.commit()
            return jsonify({"message": "Sabor actualizado exitosamente", "sabor": sabor.serialize()}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al actualizar el sabor: {str(e)}"}), 500
    elif request.method == 'DELETE':
        try:
            db.session.delete(sabor)
            db.session.commit()
            return jsonify({"message": "Sabor eliminado exitosamente"}), 204
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Error al eliminar el sabor: {str(e)}"}), 500

# --- Rutas del Frontend (Páginas HTML) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/catalogo')
def catalogo():
    sabores = Sabor.query.filter_by(disponible=True).order_by(Sabor.nombre).all()
    return render_template('catalogo.html', sabores=sabores)

@app.route('/catalogo/<int:sabor_id>')
def sabor_detalle(sabor_id):
    sabor = Sabor.query.get_or_404(sabor_id)
    return render_template('sabor_detalle.html', sabor=sabor)

@app.route('/admin/sabores')
def admin_sabores():
    sabores = Sabor.query.all()
    return render_template('admin_sabores.html', sabores=sabores)

@app.route('/admin/sabores/agregar', methods=['GET', 'POST'])
def admin_agregar_sabor():
    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion')
        precio = float(request.form['precio'])
        disponible = 'disponible' in request.form
        # CAMBIO AQUÍ: default para el formulario de agregar
        imagen_url = request.form.get('imagen_url', 'img/default_sabor.png')

        if not nombre or not precio or precio <= 0:
            flash('Error: Nombre y Precio son obligatorios, y el precio debe ser positivo.', 'danger')
            return render_template('sabor_form.html', sabor={'nombre': nombre, 'descripcion': descripcion, 'precio': precio, 'disponible': disponible, 'imagen_url': imagen_url})

        if Sabor.query.filter_by(nombre=nombre).first():
            flash('Error: Ya existe un sabor con ese nombre.', 'danger')
            return render_template('sabor_form.html', sabor={'nombre': nombre, 'descripcion': descripcion, 'precio': precio, 'disponible': disponible, 'imagen_url': imagen_url})

        try:
            nuevo_sabor = Sabor(nombre=nombre, descripcion=descripcion,
                                 precio=precio, disponible=disponible, imagen_url=imagen_url)
            db.session.add(nuevo_sabor)
            db.session.commit()
            flash(f'Sabor "{nombre}" agregado exitosamente.', 'success')
            return redirect(url_for('admin_sabores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al agregar el sabor: {str(e)}', 'danger')

    return render_template('sabor_form.html', sabor=None)

@app.route('/admin/sabores/editar/<int:sabor_id>', methods=['GET', 'POST'])
def admin_editar_sabor(sabor_id):
    sabor = Sabor.query.get_or_404(sabor_id)

    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion')
        precio = float(request.form['precio'])
        disponible = 'disponible' in request.form
        # CAMBIO AQUÍ: default para el formulario de editar
        imagen_url = request.form.get('imagen_url', 'img/default_sabor.png')

        if not nombre or not precio or precio <= 0:
            flash('Error: Nombre y Precio son obligatorios, y el precio debe ser positivo.', 'danger')
            # Pasa el objeto sabor actualizado para no perder los cambios en el formulario
            sabor.nombre = nombre
            sabor.descripcion = descripcion
            sabor.precio = precio
            sabor.disponible = disponible
            sabor.imagen_url = imagen_url
            return render_template('sabor_form.html', sabor=sabor)

        sabor_existente = Sabor.query.filter(Sabor.nombre == nombre, Sabor.id != sabor_id).first()
        if sabor_existente:
            flash('Error: Ya existe otro sabor con ese nombre.', 'danger')
            sabor.nombre = nombre
            sabor.descripcion = descripcion
            sabor.precio = precio
            sabor.disponible = disponible
            sabor.imagen_url = imagen_url
            return render_template('sabor_form.html', sabor=sabor)

        try:
            sabor.nombre = nombre
            sabor.descripcion = descripcion
            sabor.precio = precio
            sabor.disponible = disponible
            # CAMBIO AQUÍ: guarda la URL de imagen del formulario
            sabor.imagen_url = imagen_url
            db.session.commit()
            flash(f'Sabor "{sabor.nombre}" actualizado exitosamente.', 'success')
            return redirect(url_for('admin_sabores'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el sabor: {str(e)}', 'danger')

    return render_template('sabor_form.html', sabor=sabor)

@app.route('/admin/sabores/eliminar/<int:sabor_id>', methods=['POST'])
def admin_eliminar_sabor(sabor_id):
    sabor = Sabor.query.get_or_404(sabor_id)
    try:
        db.session.delete(sabor)
        db.session.commit()
        flash(f'Sabor "{sabor.nombre}" eliminado exitosamente.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el sabor: {str(e)}', 'danger')
    return redirect(url_for('admin_sabores'))

# --- Inicio de la Aplicación ---
if __name__ == "__main__":
    with app.app_context(): # Asegura el contexto para db.create_all() en el inicio
        db.create_all()
        # Carga los datos iniciales SOLO SI NO HAY SABORES
        if Sabor.query.count() == 0:
            print("Cargando datos iniciales de sabores...")
            # ASIGNANDO LAS RUTAS DE IMAGEN CORRECTAS Y AÑADIENDO UN 5TO SABOR
            sabor1 = Sabor(nombre="Vainilla Clásica", descripcion="El sabor dulce y cremoso de siempre.", precio=2.50, disponible=True, imagen_url="img/helado1.jpg")
            sabor2 = Sabor(nombre="Chocolate Intenso", descripcion="El chocolate más puro y delicioso.", precio=3.00, disponible=True, imagen_url="img/helado2.jpg")
            sabor3 = Sabor(nombre="Fresa Fresca", descripcion="Hecho con fresas naturales de temporada.", precio=2.75, disponible=True, imagen_url="img/helado3.jpg")
            sabor4 = Sabor(nombre="Menta Chips", descripcion="Refrescante menta con trozos de chocolate.", precio=3.20, disponible=False, imagen_url="img/helado4.jpg")
            sabor5 = Sabor(nombre="Mango Tropical", descripcion="El exótico sabor del mango recién cortado.", precio=2.80, disponible=True, imagen_url="img/helado5.jpg") # Nuevo sabor para tu 5ta imagen

            db.session.add_all([sabor1, sabor2, sabor3, sabor4, sabor5]) # Asegúrate de que todos los sabores estén aquí
            db.session.commit()
            print("Datos iniciales de sabores cargados.")
        else:
            print(f"Ya existen {Sabor.query.count()} sabores en la base de datos. No se cargaron datos iniciales.")

    app.run(debug=False)