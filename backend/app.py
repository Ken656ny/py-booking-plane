# app.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pymysql
import random, string
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
CORS(app)




DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "port":3307,
    "password": "1234567",
    "database": "aerolinea",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True
}

def conexion():
    return pymysql.connect(**DB_CONFIG)

@app.route("/admin/login", methods=["POST"])
def login_admin():
    data = request.get_json()
    correo = data.get("correo")
    password = data.get("password")

    if not (correo and password):
        return jsonify({"error": "Faltan datos"}), 400

    conn = conexion()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM administrador WHERE correo=%s AND password=%s", (correo, password))
        admin = cur.fetchone()

    if admin:
        return jsonify({"message": f"Bienvenido {admin['nombre']}"})
    else:
        return jsonify({"error": "Correo o contraseña incorrectos"}), 401
    
    
def query(sql, params=None, fetch=True):
    with conexion() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        if fetch:
            return cur.fetchall()
        else:
            conn.commit()
            return True

# ============================
# Helpers
# ============================
def generar_codigo_long(k=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=k))

# ============================
# Endpoints - modelos / aviones / vuelos / asientos
# ============================

@app.route("/modelo", methods=["POST"])
def crear_modelo():
    datos = request.get_json()
    nombre = datos.get("nombre")
    filas = int(datos.get("filas", 12))
    query("INSERT INTO modelo_avion (nombre, filas) VALUES (%s,%s)", (nombre, filas), fetch=False)
    return jsonify({"mensaje": f"Modelo {nombre} creado con {filas} filas"})

@app.route("/avion", methods=["POST"])
def crear_avion():
    datos = request.get_json()
    id_modelo = datos.get("id_modelo")
    matricula = datos.get("matricula")
    query("INSERT INTO avion (id_modelo, matricula) VALUES (%s,%s)", (id_modelo, matricula), fetch=False)
    return jsonify({"mensaje": f"Avión {matricula} creado y asignado al modelo {id_modelo}"})

@app.route("/vuelo", methods=["POST"])
def crear_vuelo():
    datos = request.get_json()
    id_avion = datos.get("id_avion")
    origen = datos.get("origen")
    destino = datos.get("destino")
    fecha = datos.get("fecha")  
    precio = float(datos.get("precio", 0))

    query("INSERT INTO vuelo (id_avion, origen, destino, fecha, precio) VALUES (%s,%s,%s,%s,%s)",
          (id_avion, origen, destino, fecha, precio), fetch=False)

    id_vuelo = query("SELECT id_vuelo FROM vuelo ORDER BY id_vuelo DESC LIMIT 1")[0]["id_vuelo"]

    # Obtener filas del modelo del avión
    modelo = query("""SELECT m.filas FROM modelo_avion m
                      JOIN avion a ON a.id_modelo = m.id_modelo
                      WHERE a.id_avion=%s""", (id_avion,))
    if not modelo:
        return jsonify({"error": "Avión o modelo no encontrado"}), 404

    filas = int(modelo[0]["filas"])
    columnas = ['A','B','C','D','E','F']  # siempre ABC-DEF

    # Generar asientos
    for fila in range(1, filas+1):
        for col in columnas:
            nombre_asiento = f"{col}{fila}"
            query("INSERT INTO asiento (id_vuelo, nombre_asiento, estado) VALUES (%s,%s,'DISPONIBLE')",
                  (id_vuelo, nombre_asiento), fetch=False)

    return jsonify({"mensaje": f"Vuelo creado con {filas * 6} asientos", "id_vuelo": id_vuelo})

@app.route("/vuelos", methods=["GET"])
def listar_vuelos():
    vuelos = query("""
        SELECT v.*, 
               a.matricula, 
               m.nombre AS modelo, 
               m.filas,
               COUNT(asnt.id_asiento) AS total_asientos,
               SUM(CASE WHEN asnt.estado='RESERVADO' THEN 1 ELSE 0 END) AS asientos_ocupados,
               SUM(CASE WHEN asnt.estado='DISPONIBLE' THEN 1 ELSE 0 END) AS asientos_disponibles
        FROM vuelo v
        JOIN avion a ON v.id_avion = a.id_avion
        JOIN modelo_avion m ON a.id_modelo = m.id_modelo
        LEFT JOIN asiento asnt ON asnt.id_vuelo = v.id_vuelo
        GROUP BY v.id_vuelo
        HAVING asientos_disponibles > 0
    """)
    return jsonify({"vuelos": vuelos})


@app.route("/vuelo/<int:id_vuelo>/asientos", methods=["GET"])
def obtener_asientos(id_vuelo):
    asientos = query("SELECT id_asiento, nombre_asiento, estado FROM asiento WHERE id_vuelo=%s ORDER BY CAST(SUBSTRING(nombre_asiento,2) AS UNSIGNED), LEFT(nombre_asiento,1)", (id_vuelo,))
    return jsonify({"asientos": asientos})

# ============================
# Reservar asiento directamente
# ============================
@app.route("/vuelo/<int:id_vuelo>/reservar", methods=["POST"])
def reservar_asiento(id_vuelo):
    """
    Body:
    {
      "pagador": {"nombre":"Juan", "tipo_doc":"CC", "num_doc":"123", "correo":"juan@mail.com"},
      "pasajeros":[
          {"primer_apellido":"Perez","segundo_apellido":"Lopez","nombres":"Juan","fecha_nacimiento":"1990-01-01","genero":"M","tipo_documento":"CC","num_documento":"123","asiento":"A1"},
          {"primer_apellido":"Lopez","segundo_apellido":"Gomez","nombres":"Ana","fecha_nacimiento":"1992-02-02","genero":"F","tipo_documento":"CC","num_documento":"456","asiento":"A2"}
      ]
    }
    """
    datos = request.get_json()
    pagador = datos.get("pagador")
    pasajeros = datos.get("pasajeros", [])

    if not pagador or not pasajeros:
        return jsonify({"error": "Faltan datos"}), 400

    # Verificar disponibilidad de todos los asientos
    seat_names = [p["asiento"] for p in pasajeros]
    placeholders = ",".join(["%s"]*len(seat_names))
    sql = f"SELECT nombre_asiento FROM asiento WHERE id_vuelo=%s AND nombre_asiento IN ({placeholders}) AND estado='DISPONIBLE'"
    res = query(sql, [id_vuelo]+seat_names)
    disponibles = [r["nombre_asiento"] for r in res]

    if set(disponibles) != set(seat_names):
        return jsonify({"error": "Algunos asientos no están disponibles", "disponibles": disponibles}), 409

    codigo = generar_codigo_long(8)
    vuelo_info = query("SELECT precio FROM vuelo WHERE id_vuelo=%s", (id_vuelo,))
    precio_unit = float(vuelo_info[0]["precio"]) if vuelo_info else 0
    total = precio_unit * len(pasajeros)

    query("""INSERT INTO reserva (codigo_reserva, id_vuelo, pagador_nombre, pagador_doc_tipo, pagador_doc_num, pagador_correo, estado_pago, total)
             VALUES (%s,%s,%s,%s,%s,%s,'PENDIENTE',%s)""",
          (codigo, id_vuelo, pagador["nombre"], pagador["tipo_doc"], pagador["num_doc"], pagador["correo"], total),
          fetch=False)
    id_reserva = query("SELECT id_reserva FROM reserva WHERE codigo_reserva=%s", (codigo,))[0]["id_reserva"]

    for p in pasajeros:
        query("""INSERT INTO pasajero (primer_apellido, segundo_apellido, nombres, fecha_nacimiento, genero, tipo_documento, num_documento, celular, correo)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
              (p.get("primer_apellido"), p.get("segundo_apellido"), p.get("nombres"), p.get("fecha_nacimiento"),
               p.get("genero"), p.get("tipo_documento"), p.get("num_documento"), p.get("celular"), p.get("correo")),
              fetch=False)
        id_pasajero = query("SELECT id_pasajero FROM pasajero ORDER BY id_pasajero DESC LIMIT 1")[0]["id_pasajero"]

        # actualizar asiento a RESERVADO
        query("UPDATE asiento SET estado='RESERVADO', reservado_por=%s WHERE id_vuelo=%s AND nombre_asiento=%s",
              (id_pasajero, id_vuelo, p["asiento"]), fetch=False)

        # asociar reserva-pasajero-asiento
        id_asiento = query("SELECT id_asiento FROM asiento WHERE id_vuelo=%s AND nombre_asiento=%s", (id_vuelo, p["asiento"]))[0]["id_asiento"]
        query("INSERT INTO reserva_pasajero (id_reserva, id_pasajero, id_asiento) VALUES (%s,%s,%s)",
              (id_reserva, id_pasajero, id_asiento), fetch=False)

    return jsonify({"mensaje":"Reserva creada", "codigo_reserva":codigo, "total":total})

# ============================
# Simular pago
# ============================
@app.route("/pago/<codigo_reserva>", methods=["POST"])
def simular_pago(codigo_reserva):
    datos = request.get_json() or {}
    metodo = datos.get("metodo", "TARJETA")  
    estado = "EXITOSO" 

    reserva = query("SELECT id_reserva, total FROM reserva WHERE codigo_reserva=%s", (codigo_reserva,))
    if not reserva:
        return jsonify({"error": "reserva no encontrada"}), 404
    id_reserva = reserva[0]["id_reserva"]
    monto = float(reserva[0]["total"])

    query("INSERT INTO pago (id_reserva, metodo, estado, monto) VALUES (%s,%s,%s,%s)", (id_reserva, metodo, estado, monto), fetch=False)
    query("UPDATE reserva SET estado_pago=%s WHERE id_reserva=%s", (estado, id_reserva), fetch=False)

    return jsonify({"codigo_reserva": codigo_reserva, "estado_pago": estado, "monto": monto})

# ============================
# Generar tiquete (PDF)
# ============================
@app.route("/tiquete/<codigo_reserva>", methods=["GET"])
def generar_tiquete(codigo_reserva):
    reserva = query("SELECT * FROM reserva WHERE codigo_reserva=%s", (codigo_reserva,))
    if not reserva:
        return jsonify({"error": "Reserva no encontrada"}), 404
    reserva = reserva[0]
    pasajeros = query("""SELECT p.nombres, p.primer_apellido, p.segundo_apellido, a.nombre_asiento
                         FROM reserva_pasajero rp
                         JOIN pasajero p ON rp.id_pasajero = p.id_pasajero
                         JOIN asiento a ON rp.id_asiento = a.id_asiento
                         WHERE rp.id_reserva=%s""", (reserva["id_reserva"],))

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 760, f"Tiquete electrónico - Reserva: {codigo_reserva}")
    c.setFont("Helvetica", 11)
    c.drawString(50, 740, f"Vuelo ID: {reserva['id_vuelo']}")
    c.drawString(50, 725, f"Pagador: {reserva['pagador_nombre']} - {reserva.get('pagador_correo','')}")
    c.drawString(50, 710, f"Estado de pago: {reserva['estado_pago']}")
    c.drawString(50, 695, f"Total: {reserva.get('total',0)}")
    y = 670
    for p in pasajeros:
        c.drawString(50, y, f"{p['nombres']} {p['primer_apellido']} {p['segundo_apellido']}  -  Asiento: {p['nombre_asiento']}")
        y -= 18
        if y < 60:
            c.showPage()
            y = 760
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"tiquete_{codigo_reserva}.pdf", mimetype="application/pdf")

# ============================
# Salud
# ============================
@app.route("/")
def salud():
    return jsonify({"mensaje": "API de tiquetes corriendo"})

# crud de modelos (administrador)
@app.route("/api/modelos", methods=["GET"])
def get_modelos():
    modelos = query("SELECT * FROM modelo_avion")
    return jsonify(modelos)



@app.route("/api/modelos/<int:id_modelo>", methods=["PUT"])
def actualizar_modelo(id_modelo):
    datos = request.get_json()
    query("UPDATE modelo_avion SET nombre=%s, filas=%s WHERE id_modelo=%s",
          (datos["nombre"], datos["filas"], id_modelo), fetch=False)
    return jsonify({"mensaje":"Modelo actualizado"})

@app.route("/api/modelos/<int:id_modelo>", methods=["DELETE"])
def eliminar_modelo(id_modelo):
    query("DELETE FROM modelo_avion WHERE id_modelo=%s", (id_modelo,), fetch=False)
    return jsonify({"mensaje":"Modelo eliminado"})

# crud 

@app.route("/api/aviones", methods=["GET"])
def get_aviones():
    aviones = query("""SELECT a.*, m.nombre AS modelo_nombre
                       FROM avion a JOIN modelo_avion m ON a.id_modelo=m.id_modelo""")
    return jsonify(aviones)



@app.route("/api/aviones/<int:id_avion>", methods=["PUT"])
def actualizar_avion(id_avion):
    datos = request.get_json()
    query("UPDATE avion SET id_modelo=%s, matricula=%s WHERE id_avion=%s",
          (datos["id_modelo"], datos["matricula"], id_avion), fetch=False)
    return jsonify({"mensaje":"Avión actualizado"})

@app.route("/api/aviones/<int:id_avion>", methods=["DELETE"])
def eliminar_avion(id_avion):
    query("DELETE FROM avion WHERE id_avion=%s", (id_avion,), fetch=False)
    return jsonify({"mensaje":"Avión eliminado"})


#  crud vuelos


@app.route("/api/vuelos", methods=["GET"])
def get_vuelos():
    vuelos = query("""SELECT v.*, a.matricula, m.nombre AS modelo
                      FROM vuelo v
                      JOIN avion a ON v.id_avion=a.id_avion
                      JOIN modelo_avion m ON a.id_modelo=m.id_modelo""")
    return jsonify(vuelos)


@app.route("/api/vuelos/<int:id_vuelo>", methods=["PUT"])
def actualizar_vuelo(id_vuelo):
    datos = request.get_json()
    query("""UPDATE vuelo SET id_avion=%s, origen=%s, destino=%s, fecha=%s, precio=%s
             WHERE id_vuelo=%s""",
          (datos["id_avion"], datos["origen"], datos["destino"], datos["fecha"], datos["precio"], id_vuelo), fetch=False)
    return jsonify({"mensaje":"Vuelo actualizado"})

@app.route("/api/vuelos/<int:id_vuelo>", methods=["DELETE"])
def eliminar_vuelo(id_vuelo):
    query("DELETE FROM vuelo WHERE id_vuelo=%s", (id_vuelo,), fetch=False)
    return jsonify({"mensaje":"Vuelo eliminado"})


@app.route("/api/vuelos/filtro", methods=["GET"])
def filtro_vuelos():
    origen = request.args.get("origen")
    destino = request.args.get("destino")
    vuelos = query("SELECT v.*, a.matricula, m.nombre AS modelo FROM vuelo v JOIN avion a ON v.id_avion=a.id_avion JOIN modelo_avion m ON a.id_modelo=m.id_modelo WHERE v.origen=%s AND v.destino=%s", (origen, destino))
    return jsonify(vuelos)





if __name__ == "__main__":
    app.run(debug=True)
