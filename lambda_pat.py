import json
import base64
from atlassian import Jira

def get_auth_from_event(event):
    headers = event.get('headers', {})
    auth_header = headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        return None, None

    try:
        credentials_str = base64.b64decode(auth_header[7:]).decode('utf-8')
        username, password = credentials_str.split(':', 1)
        return username, password
    except Exception:
        return None, None

def lambda_handler(event, context):
    username, password = get_auth_from_event(event)
    if not username or not password:
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Invalid authentication"})
        }

    jira_client = Jira(url="https://jira.dev.netquestapps.com", username=username, password=password)

    try:
        method = event.get("httpMethod", "GET")
        jira_path = event.get("path", {})
        data = json.loads(event.get("body", "{}")) if event.get("body") else None
        query_params = event.get("queryStringParameters", {}) or {}

        if method == "GET":
            response = jira_client.get(jira_path, params=query_params)
        elif method == "POST":
            if "issue" in jira_path:
                data = data.get("fields", {})
                data['issuetype'] = {'name': 'Ticket'}  # Forzar el tipo de ticket
                response = jira_client.issue_create(fields=data)
            else:
                response = jira_client.post(jira_path, data=data)
        elif method == "PUT":
            response = jira_client.put(jira_path, data=data)
        elif method == "DELETE":
            response = jira_client.delete(jira_path)
        else:
            return {
                "statusCode": 405,
                "body": json.dumps({"error": "Method not supported"})
            }

        return {
            "statusCode": 200,
            "body": json.dumps(response)
        }

    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
