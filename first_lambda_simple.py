import json
import os
from atlassian import Jira
from requests import HTTPError
import boto3

GLOBAL_REGION = "us-east-1"
ssm = boto3.client("ssm", region_name=GLOBAL_REGION)


def get_jira_credentials():
    JIRA_URL_PARAM = "/jira_webhook_lambda/jira_url"
    JIRA_USERNAME_PARAM = "/jira_webhook_lambda/jira_username"
    JIRA_PASSWORD_PARAM = "/jira_webhook_lambda/jira_password"

    try:
        parameters = ssm.get_parameters(
            Names=[JIRA_URL_PARAM, JIRA_USERNAME_PARAM, JIRA_PASSWORD_PARAM],
            WithDecryption=False
        )

        param_dict = {param["Name"]: param["Value"] for param in parameters["Parameters"]}

        return {
            "url": param_dict.get(JIRA_URL_PARAM, ""),
            "username": param_dict.get(JIRA_USERNAME_PARAM, ""),
            "password": param_dict.get(JIRA_PASSWORD_PARAM, "")
        }
    except Exception as e:
        print(e)
        return {"url": "", "username": "", "password": ""}

def is_aikido_event(body):
    if not isinstance(body, dict):
        return False
    required_keys = ['event_type', 'created_at', 'dispatched_at', 'payload']
    if not all(key in body for key in required_keys):
        return False
    if not isinstance(body['payload'], dict):
        return False
    if 'issue_id' not in body['payload']:
        return False
    return True

def parse_aikido_event(body):
    '''
    structure:
        - event_type: (STRING)
        - created_at: (INT)
        - dispatched_at: (INT)
        - payload: dict with:
            issue_id: (INT)
            type: (STRING, 'open_source', 'leaked_secret', 'cloud', 'iac', 'sast', 'surface_monitoring', 'malware')
            severity_score: (INT, 1-100)
            severity: (STRING, 'critical', 'high', 'medium' or 'low')
            status: (STRING, 'open')
    '''
    event_type    = body.get("event_type", "Unknown Aikido Event")
    created_at    = body.get("created_at", "Unknown")
    dispatched_at = body.get("dispatched_at", "Unknown")
    payload       = body.get("payload", {})
    issue_id      = payload.get("issue_id", "N/A")
    issue_type    = payload.get("type", "N/A")
    severity_score= payload.get("severity_score", "N/A")
    severity      = payload.get("severity", "N/A")
    status        = payload.get("status", "N/A")
    
    summary = f"Aikido - Issue {issue_id}"
    description = (
        f"Created At: {created_at}\n"
        f"Dispatched At: {dispatched_at}\n"
        f"Issue Type: {issue_type}\n"
        f"Severity Score: {severity_score}\n"
        f"Severity: {severity}\n"
        f"Status: {status}"
    )
    return summary, description

def lambda_handler(event, context):
    try:

        source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'Unknown')
        user_agent = event.get('headers', {}).get('User-Agent', 'Unknown')
        
        caller_id = event.get('headers', {}).get('X-Caller-ID', 'Not provided')
        
        print(f"Request from IP: {source_ip}, User Agent: {user_agent}, Caller ID: {caller_id}")

        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
        
        if is_aikido_event(body):
            summary, description = parse_aikido_event(body)
            print("IS AKIDO EVENT")
        else:
            event_type = body.get("event_type", "Default Event")
            payload = body.get("payload", {})
            summary = f"{event_type}: Severity {payload.get('severity', 'N/A')}"
            description = json.dumps(payload, indent=2)
        
        jira_credentials = get_jira_credentials()
        jira_url = jira_credentials["url"]
        jira_username = jira_credentials["username"]
        jira_password = jira_credentials["password"]

        jira = Jira(
            url=jira_url,
            username=jira_username,
            password=jira_password
        )

        data={
                'project': {
                    'key': 'SYS'
                },
                'summary': summary,
                'description': description,
                'issuetype': {
                    'name': 'Ticket'
                },
        }
        # deactivated until we have proper webhook connection
        # issue = jira.create_issue(fields=data)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Issue created successfully",
                # "issue_key": issue.get("key", "N/A")
            })
        }

    except HTTPError as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": e.response.text})
        }
    except Exception as e:
        print(e)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }