from flask import Flask, request, jsonify
import google.generativeai as genai
from datetime import datetime
from dotenv import load_dotenv
from flask_cors import CORS, cross_origin
import os
import re

# Inicialización
app = Flask(__name__)
CORS(app)

# Cargar variables de entorno
load_dotenv()

# Configurar Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Almacenamiento de sesiones
chat_sessions = {}

# Información de la tienda
STORE_INFO = {
    "nombre": "Fashion Store",
    "productos": [
        {
            "categoria": "Camisetas",
            "precio": "Desde S/. 29.90",
            "tallas": ["S", "M", "L", "XL"]
        },
        {
            "categoria": "Pantalones",
            "precio": "Desde S/. 59.90",
            "tallas": ["28", "30", "32", "34"]
        },
        {
            "categoria": "Vestidos",
            "precio": "Desde S/. 79.90",
            "tallas": ["S", "M", "L"]
        }
    ],
    "promociones": [
        "2x1 en camisetas",
        "30% de descuento en vestidos",
        "Envío gratis por compras mayores a S/. 200"
    ],
    "horario": "Lunes a Sábado de 10:00 AM a 8:00 PM"
}

def validar_email(email):
    """Valida el formato del email"""
    patron = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(patron, email) is not None

def validar_celular(celular):
    """Valida el formato del celular (9 dígitos comenzando con 9)"""
    patron = r'^9\d{8}$'
    return re.match(patron, celular) is not None

@app.route('/api/chat', methods=['POST'])
@cross_origin()
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

    # Nueva sesión
    if not session_id or session_id not in chat_sessions:
        session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        chat_sessions[session_id] = {
            'estado': 'pidiendo_nombre',
            'datos_cliente': {}
        }
        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'response': "¡Hola! 👋 Para comenzar, ¿podrías decirme tu nombre?",
            'waiting_for': 'nombre'
        })

    session = chat_sessions[session_id]
    estado = session['estado']
    datos_cliente = session['datos_cliente']

    # Máquina de estados para recolectar información
    if estado == 'pidiendo_nombre':
        datos_cliente['nombre'] = message
        session['estado'] = 'pidiendo_email'
        return jsonify({
            'status': 'success',
            'response': f"Gracias {message}! ¿Me podrías proporcionar tu email?",
            'waiting_for': 'email'
        })

    elif estado == 'pidiendo_email':
        if not validar_email(message):
            return jsonify({
                'status': 'error',
                'response': "Por favor, ingresa un email válido (ejemplo: usuario@dominio.com)",
                'waiting_for': 'email'
            })
        datos_cliente['email'] = message
        session['estado'] = 'pidiendo_celular'
        return jsonify({
            'status': 'success',
            'response': "Perfecto! Por último, ¿me das tu número de celular? (debe empezar con 9 y tener 9 dígitos)",
            'waiting_for': 'celular'
        })

    elif estado == 'pidiendo_celular':
        if not validar_celular(message):
            return jsonify({
                'status': 'error',
                'response': "El número debe empezar con 9 y tener 9 dígitos. Por favor, intenta nuevamente.",
                'waiting_for': 'celular'
            })
        datos_cliente['celular'] = message
        session['estado'] = 'chat_activo'
        
        # Mensaje de bienvenida con resumen de datos
        bienvenida = f"""
¡Registro completado! 🎉
Tus datos registrados son:
- Nombre: {datos_cliente['nombre']}
- Email: {datos_cliente['email']}
- Celular: {datos_cliente['celular']}

¿En qué puedo ayudarte? Puedes preguntarme sobre:
1. Productos y precios
2. Promociones actuales
3. Horario de atención
        """
        return jsonify({
            'status': 'success',
            'response': bienvenida
        })

    # Chat activo - responder consultas
    try:
        prompt = f"""
        Eres un asistente virtual de {STORE_INFO['nombre']}.
        
        Información del cliente:
        Nombre: {datos_cliente['nombre']}
        Email: {datos_cliente['email']}
        Celular: {datos_cliente['celular']}
        
        Información de la tienda:
        {STORE_INFO}
        
        Pregunta del cliente: {message}
        
        Por favor, responde de manera amable y personalizada, usando el nombre del cliente.
        Usa solo la información proporcionada en STORE_INFO.
        Si te preguntan por algo que no está en los datos, menciona amablemente que no tienes esa información.
        """
        
        response = model.generate_content(prompt)
        
        return jsonify({
            'status': 'success',
            'response': response.text
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)


