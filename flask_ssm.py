import os
from flask import Flask, request, jsonify
from atlassian import Jira
import boto3

app = Flask(__name__)

# Configuración global
GLOBAL_REGION = "us-east-1"
ssm = boto3.client("ssm", region_name=GLOBAL_REGION)

# Obtener credenciales de JIRA
def get_jira_credentials():
    try:
        parameters = ssm.get_parameters(
            Names=["/jira_webhook_lambda/jira_url", "/jira_webhook_lambda/jira_username", "/jira_webhook_lambda/jira_password"],
            WithDecryption=True
        )
        param_dict = {param["Name"]: param["Value"] for param in parameters["Parameters"]}

        return param_dict["/jira_webhook_lambda/jira_url"], param_dict["/jira_webhook_lambda/jira_username"], param_dict["/jira_webhook_lambda/jira_password"]
    except Exception as e:
        app.logger.error(f"Error retrieving JIRA credentials: {e}")
        return None, None, None

# Inicializar cliente Jira
JIRA_URL, JIRA_USERNAME, JIRA_PASSWORD = get_jira_credentials()
jira_client = Jira(url=JIRA_URL, username=JIRA_USERNAME, password=JIRA_PASSWORD)

@app.route('/rest/api/2/<path:jira_path>', methods=["GET", "POST", "PUT", "DELETE"])
def proxy_request(jira_path):
    try:
        method = request.method
        data = request.json if request.is_json else None
        # app.logger.error(f"Proxying request to JIRA: {method} {jira_path}")
        # app.logger.error(f"Data: {data}")
        if method == "GET":
            response = jira_client.get(f"/rest/api/2/{jira_path}", params=request.args)
        elif method == "POST":
            if "issue" in jira_path:
                data = data.get("fields",{})
                data['issuetype'] = {'name': 'Ticket'} # Necessary for the creation of tickets (aikido sends other type)
                response = jira_client.issue_create(fields=data)
            else:
                response = jira_client.post(f"/rest/api/2/{jira_path}", data=data)
        elif method == "PUT":
            response = jira_client.put(f"/rest/api/2/{jira_path}", data=data)
        elif method == "DELETE":
            response = jira_client.delete(f"/rest/api/2/{jira_path}")
        else:
            return jsonify({"error": "Method not supported"}), 405
        app.logger.info(f"Response: {response}")
        return jsonify(response)
    except Exception as e:
        app.logger.error(f"Error proxying request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
