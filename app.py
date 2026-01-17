#!/usr/bin/env python3
from flask import Flask, request, jsonify
import base64
import json
import time
from collections import defaultdict
import threading

app = Flask(__name__)

# Almacenamiento temporal de sesiones (en memoria)
sessions = defaultdict(dict)
session_lock = threading.Lock()

def decode_dns_packet(data):
    """Decodifica paquete QUIC de consulta DNS"""
    try:
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
    except:
        return {'id': str(int(time.time())), 'data': ''}

def encode_dns_response(quic_data):
    """Codifica respuesta para DNS"""
    return base64.b64encode(quic_data).decode('ascii')

@app.route('/dns-query', methods=['GET', 'POST'])
def dns_query():
    """Endpoint DoH estándar (RFC 8484)"""
    # Para GET
    if request.method == 'GET':
        dns_query_b64 = request.args.get('dns')
        if dns_query_b64:
            dns_data = base64.b64decode(dns_query_b64)
        else:
            return '', 400
    
    # Para POST
    else:
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
        'Answer': [{
            'name': 'quic-tunnel.example.com',
            'type': 16,  # TXT
            'TTL': 300,
            'data': encode_dns_response(b'QUIC_ACK')
        }]
    }
    
    return jsonify(response_data), 200, {'Content-Type': 'application/dns-json'}

@app.route('/quic-tunnel', methods=['POST'])
def quic_tunnel():
    """Endpoint directo para túnel QUIC (más eficiente)"""
    encrypted_data = request.get_data()
    
    # Aquí procesarías los paquetes QUIC reales
    # Por simplicidad, echo server
    
    return encrypted_data, 200, {
        'Content-Type': 'application/octet-stream',
        'X-QUIC-Tunnel': 'active'
    }

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'quic-doh-proxy'})

if __name__ == '__main__':
    # En Render, el puerto viene de la variable de entorno
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
