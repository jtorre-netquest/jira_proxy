import json
import os
import logging
from typing import Dict, Any
from atlassian import Jira
from aws_lambda_powertools import Logger

logger = Logger()

class JiraServerProxy:
    def __init__(self, jira_server_url: str, username: str, psw: str):
        self.jira = Jira(
            url=jira_server_url,
            username=username,
            password=psw
        )
    
    def browse_projects(self) -> list:
        """Get all accessible projects from Jira Server"""
        try:
            projects = self.jira.get_all_projects(included_archived=False)
            return [{
                'key': project['key'],
                'name': project['name'],
                'id': project['id']
            } for project in projects]
        except Exception as e:
            logger.error(f"Error fetching projects: {str(e)}")
            raise
    
    def create_issue(self, project_key: str, summary: str, description: str, issue_type: str = 'Task', **fields) -> Dict[str, Any]:
        """Create a new issue in the specified project"""
        try:
            issue_dict = {
                'project': {'key': project_key},
                'summary': summary,
                'description': description,
                'issuetype': {'name': issue_type},
                **fields
            }
            new_issue = self.jira.issue_create(fields=issue_dict)
            return {
                'key': new_issue['key'],
                'id': new_issue['id'],
                'self': new_issue['self']
            }
        except Exception as e:
            logger.error(f"Error creating issue: {str(e)}")
            raise

def get_server_url() -> str:
    """Get Jira Server URL from environment variables"""
    url = os.environ.get('JIRA_SERVER_URL')
    if not url:
        raise ValueError("JIRA_SERVER_URL environment variable is not set")
    return url

@logger.inject_lambda_context
def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        auth_header = event.get('headers', {}).get('Authorization', '')
        if not auth_header.startswith('Basic '):
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Basic authentication required'})
            }
        
        try:
            import base64
            credentials_str = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, psw = credentials_str.split(':', 1)
        except Exception:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid authentication format'})
            }
        
        jira_proxy = JiraServerProxy(get_server_url(), username, psw)
        
        path = event.get('path', '')
        method = event.get('httpMethod', '')
        
        if method == 'GET' and '/projects' in path:
            projects = jira_proxy.browse_projects()
            return {'statusCode': 200, 'body': json.dumps({'projects': projects})}
        elif method == 'GET' and '/serverInfo' in path:
            return {'statusCode': 200, 'body': json.dumps({'server_info': jira_proxy.jira.server_info()})}
        elif method == 'POST' and '/issue' in path:
            body = json.loads(event.get('body', '{}'))
            required_fields = ['project_key', 'summary', 'description']
            if not all(field in body for field in required_fields):
                return {'statusCode': 400, 'body': json.dumps({'error': 'Missing required fields'})}
            
            new_issue = jira_proxy.create_issue(
                project_key=body['project_key'],
                summary=body['summary'],
                description=body['description'],
                issue_type=body.get('issue_type', 'Task')
            )
            return {'statusCode': 201, 'body': json.dumps({'issue': new_issue})}
        
        return {'statusCode': 404, 'body': json.dumps({'error': 'Endpoint not found'})}
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {'statusCode': 500, 'body': json.dumps({'error': 'Internal server error'})}