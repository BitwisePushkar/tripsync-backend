import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

@csrf_exempt
@require_http_methods(["POST"])
def chatbot(request):
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        system_prompt = data.get('system_prompt', 'Help the User with the questions.')
        api_key = data.get('api_key', '')
        if not user_message:
            return JsonResponse({'error': 'Write Something'}, status=400)
        if not api_key:
            return JsonResponse({'error': 'Chatbot API not working'}, status=400)
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": f"{system_prompt}\n\nUser: {user_message}"}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        response = requests.post(gemini_url, headers={'Content-Type': 'application/json'}, json=payload, timeout=30)
        if response.status_code != 200:
            return JsonResponse({'error': 'No response from Chatbot', 'details': response.text}, status=response.status_code)
        
        gemini_response = response.json()
        gemini_msg = gemini_response.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'No response')
        return JsonResponse({
            'success': True,
            'message': user_message,
            'response': gemini_msg
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Request timed out'}, status=504)
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Request failed: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)