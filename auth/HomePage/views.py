from django.shortcuts import render
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import api_view
from rest_framework.response import Response

@extend_schema(
        request={'application/json': {'type': 'object', 'properties': {'refresh': {'type': 'string'}}}},
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.OBJECT,
                description="Logged out successfully",
                examples=[OpenApiExample('Success Response', value={'status': 'success', 'message': 'Logged out successfully'})]),
            400: OpenApiResponse(description="Invalid token")},
        tags=['Authentication'],
        summary="Logout user",
        description="Blacklist refresh token to logout")
def weatherupdates(request):

    return Response("weather")