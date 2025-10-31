from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from functools import wraps
import jwt
from django.conf import settings
from account.models import User

def jwt_verification(f):
    @wraps(f)
    def new_decorator(request, *args, **kwargs):
        token = 0
        auth_header = request.header.get("Authorization")

        if auth_header and auth_header.startswith('Bearer'):
            token - auth_header.split('')[1]

        if token is 0:
            return Response({"error": "User not verified"},
            status=status.HTTP_401_UNAUTHORIZED) 
        
        try:
            payload = jwt.decode(token,settings.SECRET_KEY,algorithms=['HS256'])

            getemail = payload.get('email')
            if not getemail:
                return Response({"error":"Token Has no email attatched to it"},
                                status=status.HTTP_401_UNAUTHORIZED)
            
            try:
                getuser=User.objects.get(email=getemail)
                request.getuser = getuser
            except User.DoesNotExist:
                return Response({"error":"User Does not exist with this email"},
                                status=status.HTTP_404_NOT_FOUND)


        except jwt.ExpiredSignatureError:
            return Response({"error": "Token has expired"},
                            status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({"error":"Tokens are wrong"})
        
        return f(request,*args,**kwargs)
    return new_decorator

        
        