import json
import base64
from atlassian import Jira
import boto3

GLOBAL_REGION = "us-east-1"
ssm = boto3.client("ssm", region_name=GLOBAL_REGION)

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

def lambda_handler(event, context):
    jira_url, jira_username, jira_password = get_jira_credentials()
    if not jira_url or not jira_username or not jira_password:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to retrieve JIRA credentials"})
        }
    
    jira_client = Jira(url=jira_url, username=username, password=password)

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
