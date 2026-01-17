#!/usr/bin/env python3
from flask import Flask, request, jsonify
import base64
import json
import time
import os  # ¡FALTABA ESTE IMPORT!
from collections import defaultdict
import threading

app = Flask(__name__)

# Almacenamiento temporal de sesiones (en memoria)
sessions = defaultdict(dict)
session_lock = threading.Lock()

def decode_dns_packet(data):
    """Decodifica paquete QUIC de consulta DNS"""
    try:
        if not data:
            return {'id': str(int(time.time())), 'data': ''}
        
        # Formato simple: {id: X, chunk: N, total: M, data: base64}
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='ignore')
        
        if data.startswith('{'):
            return json.loads(data)
        else:
            # Asumir que es base64 directo
            return {
                'id': 'default',
                'chunk': 0,
                'total': 1,
                'data': data
            }
    except Exception as e:
        print(f"Error decoding DNS packet: {e}")
        return {'id': str(int(time.time())), 'data': ''}

def encode_dns_response(quic_data):
    """Codifica respuesta para DNS"""
    try:
        return base64.b64encode(quic_data).decode('ascii')
    except:
        return ""

# AÑADIR RUTA RAÍZ PARA RENDER
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>QUIC over DoH Tunnel</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; }
            code { background: #eee; padding: 2px 5px; }
            a { color: #0066cc; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>🚀 QUIC over DoH Tunnel Server</h1>
        <p>Servidor funcionando correctamente en Render</p>
        
        <div class="endpoint">
            <strong>GET <a href="/health">/health</a></strong> - Health check del servicio
        </div>
        
        <div class="endpoint">
            <strong>GET/POST <a href="/dns-query">/dns-query</a></strong> - Endpoint DoH (RFC 8484)
        </div>
        
        <div class="endpoint">
            <strong>POST /quic-tunnel</strong> - Túnel QUIC directo
        </div>
        
        <div class="endpoint">
            <strong>GET <a href="/test">/test</a></strong> - Configuración para clientes
        </div>
        
        <h3>Ejemplos de uso:</h3>
        <pre><code>curl {request.host_url}health
curl {request.host_url}test
curl -H "accept: application/dns-json" "{request.host_url}dns-query?name=example.com&type=A"</code></pre>
        
        <p><strong>URL del servicio:</strong> {request.host_url}</p>
    </body>
    </html>
    """

# AÑADIR ENDPOINT DE CONFIGURACIÓN PARA CLIENTES
@app.route('/test')
def test_config():
    """Endpoint para que los clientes obtengan configuración"""
    return jsonify({
        "service": "quic-doh-tunnel",
        "status": "active",
        "version": "1.0.0",
        "server_time": time.time(),
        "endpoints": {
            "doh_get": f"{request.host_url}dns-query?dns=",
            "doh_post": f"{request.host_url}dns-query",
            "tunnel": f"{request.host_url}quic-tunnel",
            "health": f"{request.host_url}health"
        },
        "instructions": {
            "client": "Usa POST a /quic-tunnel con datos binarios",
            "doh": "Usa GET o POST a /dns-query según RFC 8484",
            "example": "curl -X POST {request.host_url}quic-tunnel --data-binary @file.bin"
        }
    })

@app.route('/dns-query', methods=['GET', 'POST'])
def dns_query():
    """Endpoint DoH estándar (RFC 8484)"""
    # Para GET
    if request.method == 'GET':
        dns_query_b64 = request.args.get('dns')
        if dns_query_b64:
            try:
                dns_data = base64.b64decode(dns_query_b64)
            except:
                return jsonify({"Status": 2, "message": "Invalid base64"}), 400
        else:
            # Si no hay parámetro 'dns', usar consulta estándar
            name = request.args.get('name', 'example.com')
            qtype = request.args.get('type', 'A')
            
            # Respuesta simple para pruebas
            response_data = {
                'Status': 0,
                'TC': False,
                'RD': True,
                'RA': True,
                'AD': False,
                'CD': False,
                'Question': [{'name': name, 'type': 1 if qtype == 'A' else 16}],
                'Answer': [{
                    'name': name,
                    'type': 1 if qtype == 'A' else 16,
                    'TTL': 300,
                    'data': '93.184.216.34' if qtype == 'A' else '"QUIC tunnel ready"'
                }]
            }
            return jsonify(response_data), 200, {'Content-Type': 'application/dns-json'}
    
    # Para POST
    else:
        content_type = request.headers.get('Content-Type', '')
        if 'application/dns-message' in content_type:
            dns_data = request.get_data()
        else:
            # Asumir datos binarios/quic encapsulados
            dns_data = request.get_data()
    
    # Extraer datos encapsulados (simulado)
    query_data = decode_dns_packet(dns_data)
    session_id = query_data.get('id', 'default')
    
    with session_lock:
        sessions[session_id]['last_seen'] = time.time()
        sessions[session_id]['data'] = query_data.get('data', '')
    
    # Aquí normalmente procesarías el QUIC real
    # Por ahora, simulamos una respuesta
    
    # Construir respuesta DNS estándar
    response_data = {
        'Status': 0,
        'TC': False,
        'RD': True,
        'RA': True,
        'AD': False,
        'CD': False,
        'Question': [{'name': 'quic-tunnel.example.com', 'type': 16}],
        'Answer': [{
            'name': 'quic-tunnel.example.com',
            'type': 16,  # TXT
            'TTL': 300,
            'data': encode_dns_response(b'QUIC_ACK_' + str(time.time()).encode())
        }]
    }
    
    return jsonify(response_data), 200, {'Content-Type': 'application/dns-json'}

@app.route('/quic-tunnel', methods=['POST'])
def quic_tunnel():
    """Endpoint directo para túnel QUIC (más eficiente)"""
    # Obtener datos binarios
    encrypted_data = request.get_data()
    
    if not encrypted_data:
        return jsonify({"error": "No data received"}), 400
    
    # Aquí procesarías los paquetes QUIC reales
    # Por simplicidad, echo server con metadatos
    
    # Crear respuesta con metadatos
    response_headers = {
        'Content-Type': 'application/octet-stream',
        'X-QUIC-Tunnel': 'active',
        'X-Server-Time': str(time.time()),
        'X-Data-Length': str(len(encrypted_data)),
        'X-Session-ID': str(int(time.time()))
    }
    
    # Opcional: procesar/modificar datos aquí
    # Por ahora solo echo
    response_data = encrypted_data
    
    return response_data, 200, response_headers

@app.route('/health')
def health():
    """Health check endpoint para Render y monitoreo"""
    # Limpiar sesiones antiguas (> 5 minutos)
    current_time = time.time()
    with session_lock:
        expired = [sid for sid, data in sessions.items() 
                  if current_time - data.get('last_seen', 0) > 300]
        for sid in expired:
            del sessions[sid]
    
    return jsonify({
        'status': 'ok',
        'service': 'quic-doh-proxy',
        'timestamp': current_time,
        'active_sessions': len(sessions),
        'version': '1.0.0',
        'endpoints': ['/', '/health', '/dns-query', '/quic-tunnel', '/test']
    })

@app.route('/stats')
def stats():
    """Estadísticas del servidor (solo para diagnóstico)"""
    with session_lock:
        session_list = []
        current_time = time.time()
        for sid, data in sessions.items():
            age = current_time - data.get('last_seen', current_time)
            session_list.append({
                'id': sid,
                'age_seconds': round(age, 1),
                'data_length': len(data.get('data', ''))
            })
    
    return jsonify({
        'server_time': time.time(),
        'total_sessions': len(sessions),
        'sessions': session_list,
        'memory_usage': 'N/A'  # En Render no podemos acceder a esto fácilmente
    })

# Manejo de errores
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': {
            'GET': ['/', '/health', '/test', '/stats'],
            'POST': ['/dns-query', '/quic-tunnel']
        }
    }), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({
        'error': 'Internal server error',
        'message': str(error) if app.debug else 'Contact administrator'
    }), 500

if __name__ == '__main__':
    # En Render, el puerto viene de la variable de entorno
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"🚀 Starting QUIC over DoH Tunnel Server")
    print(f"📡 Port: {port}")
    print(f"🔧 Debug: {debug_mode}")
    print(f"🌐 Endpoints:")
    print(f"   GET  /          - Home page")
    print(f"   GET  /health    - Health check")
    print(f"   GET  /test      - Client configuration")
    print(f"   GET  /stats     - Server statistics")
    print(f"   GET  /dns-query - DoH endpoint (GET)")
    print(f"   POST /dns-query - DoH endpoint (POST)")
    print(f"   POST /quic-tunnel - QUIC tunnel")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
