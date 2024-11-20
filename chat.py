from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import os
from datetime import datetime

# Inicialización
app = Flask(__name__)
CORS(app)

# Cargar variables de entorno
load_dotenv()

# Configurar Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

# Almacenamiento simple para el historial
chat_history = {}

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

    message = data['message']
    session_id = data.get('session_id')

    # Si no hay session_id o no existe en el historial, crear una nueva sesión
    if not session_id or session_id not in chat_history:
        session_id = f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        chat_history[session_id] = []

    try:
        # Construir el contexto con el historial reciente
        context = "\n".join([
            f"Usuario: {interaction['user']}\nAsistente: {interaction['assistant']}"
            for interaction in chat_history[session_id][-5:]
        ])

        prompt = f"""
        Eres un asistente conversacional amigable y empático.
        
        Historial reciente de la conversación:
        {context}

        Usuario: {message}

        Responde de manera natural y amigable. Sé conciso pero útil.
        Mantén un tono conversacional agradable.
        """
        
        response = model.generate_content(prompt)
        response_text = response.text

        # Guardar en el historial
        chat_history[session_id].append({
            'user': message,
            'assistant': response_text,
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify({
            'status': 'success',
            'response': response_text,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/chat-history', methods=['GET'])
def get_chat_history():
    """Endpoint para ver el historial de chat"""
    session_id = request.args.get('session_id')
    
    if not session_id:
        return jsonify({
            'error': 'Se requiere session_id',
            'status': 'error'
        }), 400
        
    if session_id in chat_history:
        return jsonify({
            'status': 'success',
            'history': chat_history[session_id]
        })
        
    return jsonify({
        'status': 'error',
        'error': 'Sesión no encontrada'
    }), 404

if __name__ == '__main__':
    app.run(debug=True)