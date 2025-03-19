import os
import base64
from flask import Flask, request, jsonify
from atlassian import Jira

app = Flask(__name__)

# Extraer credenciales desde el encabezado Authorization
def get_auth_from_request():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None, None
    try:
        credentials_str = base64.b64decode(auth_header[6:]).decode('utf-8')
        username, password = credentials_str.split(':', 1)
        return username, password
    except Exception:
        return None, None

@app.route('/rest/api/2/<path:jira_path>', methods=["GET", "POST", "PUT", "DELETE"])
def proxy_request(jira_path):
    username, password = get_auth_from_request()
    if not username or not password:
        return jsonify({"error": "Invalid authentication"}), 401

    jira_client = Jira(url="https://jira.dev.netquestapps.com", username=username, password=password)

    try:
        method = request.method
        data = request.json if request.is_json else None

        if method == "GET":
            response = jira_client.get(f"/rest/api/2/{jira_path}", params=request.args)
        elif method == "POST":
            if "issue" in jira_path:
                data = data.get("fields", {})
                data['issuetype'] = {'name': 'Ticket'}  # Forzar el tipo de ticket
                response = jira_client.issue_create(fields=data)
            else:
                response = jira_client.post(f"/rest/api/2/{jira_path}", data=data)
        elif method == "PUT":
            response = jira_client.put(f"/rest/api/2/{jira_path}", data=data)
        elif method == "DELETE":
            response = jira_client.delete(f"/rest/api/2/{jira_path}")
        else:
            return jsonify({"error": "Method not supported"}), 405

        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Error proxying request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
