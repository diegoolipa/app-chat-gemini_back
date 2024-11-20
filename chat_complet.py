from flask import Flask, request, jsonify
import google.generativeai as genai
import json
from datetime import datetime
from dotenv import load_dotenv
from flask_cors import CORS, cross_origin  # Importamos CORS y cross_origin
import os
import re

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost",
            "http://localhost:80",
            "http://127.0.0.1",
            "http://127.0.0.1:80",
            # Agrega aquí otros dominios permitidos cuando subas a producción
            # "https://tudominio.com"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
load_dotenv()

genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Almacenamiento de sesiones y estados
chat_sessions = {}

# Define los datos requeridos para diferentes tipos de consultas
REQUIRED_DATA = {
    'producto': ['nombre', 'email', 'celular'],
    'precio': ['nombre', 'email'],
    'promocion': ['nombre', 'email', 'celular'],
    'envio': ['nombre', 'direccion', 'celular'],
    'reclamo': ['nombre', 'email', 'celular', 'numero_pedido']
}

def validar_email(email):
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(patron, email) is not None

def validar_celular(celular):
    patron = r'^9\d{8}$'
    return re.match(patron, celular) is not None
def cargar_datos():
    """Carga los datos del archivo JSON"""
    with open('store_data.json', 'r', encoding='utf-8') as file:
        return json.load(file)

def formatear_contexto(datos):
    """Formatea los datos JSON en un contexto legible para el modelo"""
    contexto = []
    
    # Información general
    info = datos['info_general']
    contexto.append(f"Tienda: {info['nombre']}")
    contexto.append(f"Horario: {info['horario']}")
    contexto.append(f"Métodos de pago: {', '.join(info['metodos_pago'])}")
    contexto.append(f"Política de devoluciones: {info['politica_devoluciones']}")
    
    # Productos por categoría
    for categoria, info in datos['categorias'].items():
        contexto.append(f"\n{categoria.upper()}:")
        for producto in info['productos']:
            contexto.append(
                f"- {producto['nombre']}: ${producto['precio']}"
                f"\n  Tallas: {', '.join(producto['tallas'])}"
                f"\n  Colores: {', '.join(producto['colores'])}"
                f"\n  {producto['descripcion']}"
            )
    
    # Promociones vigentes
    fecha_actual = datetime.now()
    promociones_activas = []
    for promo in datos['promociones']:
        fecha_inicio = datetime.strptime(promo['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(promo['fecha_fin'], '%Y-%m-%d')
        if fecha_inicio <= fecha_actual <= fecha_fin:
            promociones_activas.append(f"- {promo['descripcion']}")
    
    if promociones_activas:
        contexto.append("\nPromociones actuales:")
        contexto.extend(promociones_activas)
    
    return "\n".join(contexto)


def identificar_tipo_consulta(mensaje):
    """Identifica el tipo de consulta basado en palabras clave"""
    mensaje = mensaje.lower()
    if any(word in mensaje for word in ['precio', 'cuesta', 'valor']):
        return 'precio'
    elif any(word in mensaje for word in ['producto', 'artículo', 'tienen', 'stock']):
        return 'producto'
    elif any(word in mensaje for word in ['promoción', 'descuento', 'oferta']):
        return 'promocion'
    elif any(word in mensaje for word in ['envío', 'enviar', 'entrega', 'delivery']):
        return 'envio'
    elif any(word in mensaje for word in ['reclamo', 'queja', 'problema']):
        return 'reclamo'
    return 'general'

def revisar_datos_faltantes(session_id, tipo_consulta):
    """Revisa qué datos faltan para el tipo de consulta"""
    if tipo_consulta not in REQUIRED_DATA:
        return None
    
    datos_requeridos = REQUIRED_DATA[tipo_consulta]
    datos_cliente = chat_sessions[session_id].get('datos_cliente', {})
    
    faltantes = []
    for dato in datos_requeridos:
        if dato not in datos_cliente or not datos_cliente[dato]:
            faltantes.append(dato)
    
    return faltantes if faltantes else None

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
@cross_origin()  # Necesitarás importar esto de flask_cors

def chat():
    if not request.is_json:
        return jsonify({
            'error': 'El contenido debe ser JSON',
            'status': 'error'
        }), 400

    data = request.get_json()
    
    if 'message' not in data:
        return jsonify({
            'error': 'El campo "message" es requerido',
            'status': 'error'
        }), 400

    session_id = data.get('session_id')
    message = data['message']

    # Crear nueva sesión si no existe
    if not session_id or session_id not in chat_sessions:
        session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        chat_sessions[session_id] = {
            'datos_cliente': {},
            'estado': 'inicial',
            'tipo_consulta': None,
            'chat_history': []
        }
        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'response': "¡Hola! Para poder ayudarte mejor, ¿podrías decirme tu nombre?",
            'waiting_for': 'nombre'
        })

    session = chat_sessions[session_id]
    estado = session['estado']
    datos_cliente = session['datos_cliente']

    # Si estamos esperando datos del cliente
    if estado == 'recolectando_datos':
        waiting_for = session.get('waiting_for')
        
        if waiting_for == 'email':
            if not validar_email(message):
                return jsonify({
                    'status': 'error',
                    'response': "El formato del email no es válido. Por favor, ingresa un email válido.",
                    'waiting_for': 'email'
                })
            datos_cliente['email'] = message
        elif waiting_for == 'celular':
            if not validar_celular(message):
                return jsonify({
                    'status': 'error',
                    'response': "El número de celular debe tener 9 dígitos y empezar con 9. Por favor, intenta nuevamente.",
                    'waiting_for': 'celular'
                })
            datos_cliente['celular'] = message
        else:
            datos_cliente[waiting_for] = message
    # Manejar la solicitud OPTIONS para CORS
    if request.method == 'OPTIONS':
        return '', 204
    # Identificar tipo de consulta
    tipo_consulta = identificar_tipo_consulta(message)
    session['tipo_consulta'] = tipo_consulta

    # Verificar datos faltantes
    datos_faltantes = revisar_datos_faltantes(session_id, tipo_consulta)

    if datos_faltantes:
        # Solicitar el primer dato faltante
        dato_requerido = datos_faltantes[0]
        session['estado'] = 'recolectando_datos'
        session['waiting_for'] = dato_requerido
        
        mensajes_solicitud = {
            'nombre': "Por favor, dime tu nombre:",
            'email': "¿Me podrías proporcionar tu email?",
            'celular': "Necesito tu número de celular (debe empezar con 9 y tener 9 dígitos):",
            'direccion': "¿Podrías proporcionarme tu dirección de envío?",
            'numero_pedido': "¿Me podrías proporcionar el número de pedido?"
        }
        
        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'response': mensajes_solicitud.get(dato_requerido, f"Por favor, proporciona tu {dato_requerido}:"),
            'waiting_for': dato_requerido
        })

    # Si tenemos todos los datos necesarios, procesamos la consulta
    try:
        store_data = cargar_datos()
        context = formatear_contexto(store_data)


        prompt = f"""
        Eres un asistente virtual de tienda.
        
        Información del cliente:
        {json.dumps(datos_cliente, indent=2)}
        
        Tipo de consulta identificada: {tipo_consulta}
        
        Información de la tienda:
        {context}

        Mensaje del cliente: {message}
        
        Por favor, responde de manera amable y personalizada, usando solo la información proporcionada y usando el nombre del cliente
        Si te preguntan por algo que no está en los datos, indícalo amablemente, si no hay data no pongas esto [Tu nombre].
        """
        
        response = model.generate_content(prompt)
        
        session['estado'] = 'conversando'
        session['chat_history'].append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'response': response.text
        })
        
        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'response': response.text,
            'collected_data': datos_cliente
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/chat-history', methods=['GET'])
@cross_origin()

def get_chat_history():
    session_id = request.args.get('session_id')
    
    if not session_id or session_id not in chat_sessions:
        return jsonify({
            'error': 'Sesión no válida',
            'status': 'error'
        }), 400
        
    return jsonify({
        'status': 'success',
        'history': chat_sessions[session_id]['chat_history'],
        'collected_data': chat_sessions[session_id]['datos_cliente']
    })

if __name__ == '__main__':
    app.run(debug=True)