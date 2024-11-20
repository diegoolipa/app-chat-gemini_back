from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import os

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

# Información básica de la tienda
STORE_INFO = {
    "nombre": "Fashion Store",
    "horarios": {
        "lunes_viernes": "9:00 AM - 7:00 PM",
        "sabados": "10:00 AM - 2:00 PM",
        "domingos": "Cerrado"
    },
    "direccion": "Av. Principal 123, Lima",
    "telefono": "01-234-5678"
}

@app.route('/api/chat', methods=['POST'])
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
        session_id = f"session_{len(chat_sessions) + 1}"
        chat_sessions[session_id] = {
            'estado': 'pidiendo_nombre',
            'nombre': None
        }
        return jsonify({
            'status': 'success',
            'session_id': session_id,
            'response': "¡Hola! 👋 ¿Cuál es tu nombre?",
            'waiting_for': 'nombre'
        })

    session = chat_sessions[session_id]
    print('session>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>')    
    print(session)
    # Si aún no tenemos el nombre
    if session['estado'] == 'pidiendo_nombre':
        session['nombre'] = message
        session['estado'] = 'chat_activo'
        
        # Mensaje de bienvenida con información de la tienda
        bienvenida = f"""
                    ¡Hola {message}! 👋 
                    Bienvenido(a) a {STORE_INFO['nombre']} 🏪

                    📍 Estamos ubicados en: {STORE_INFO['direccion']}

                    ⏰ Nuestros horarios son:
                    - Lunes a Viernes: {STORE_INFO['horarios']['lunes_viernes']}
                    - Sábados: {STORE_INFO['horarios']['sabados']}
                    - Domingos: {STORE_INFO['horarios']['domingos']}

                    📞 Teléfono: {STORE_INFO['telefono']}

                    ¿En qué puedo ayudarte?
                    """
        return jsonify({
            'status': 'success',
            'response': bienvenida
        })

    # Para cualquier otra consulta
    try:
        prompt = f"""
        Eres un asistente amable de {STORE_INFO['nombre']}.
        
        Información de la tienda:
        {STORE_INFO}
        
        El cliente se llama: {session['nombre']}
        Su pregunta es: {message}
        
        Responde de manera amable y personalizada usando el nombre del cliente.
        Solo proporciona información sobre los horarios y la ubicación de la tienda.
        Si preguntan por otros temas, sugiere que visiten la tienda o llamen por teléfono.
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