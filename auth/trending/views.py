from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import TrendingPlace, FunFact
from .serializers import (TrendingPlaceSerializer, TrendingPlaceCreateSerializer,FunFactSerializer,FunFactCreateUpdateSerializer)

class PlaceListCreateView(APIView): 
    @extend_schema(
    tags=['Places'],
    summary="List All Places",
    description="Get all trending places with their fun facts.",
    responses={
        200: OpenApiResponse(
            description="Trending places retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Trending places retrieved successfully",
                        "data": [
                            {
                                "id": 1,
                                "name": "Mount Everest",
                                "main": "https://cdn.com/everest_main.jpg",
                                "fun_facts": [
                                    {"id": 1, "slide": 1, "title": "Highest peak", "desc": "Mount Everest is the highest point on Earth.", "photo": "https://cdn.com/funfact1.jpg"},
                                    {"id": 2, "slide": 2, "title": "First ascent", "desc": "First climbed in 1953 by Edmund Hillary and Tenzing Norgay.", "photo": "https://cdn.com/funfact2.jpg"}
                                ]
                            },
                            {
                                "id": 2,
                                "name": "Grand Canyon",
                                "main": "https://cdn.com/grandcanyon_main.jpg",
                                "fun_facts": [
                                    {"id": 3, "slide": 1, "title": "Huge Canyon", "desc": "Average depth is about 1 mile.", "photo": "https://cdn.com/funfact3.jpg"}
                                ]
                            }
                        ]
                    },
                    response_only=True
                )
            ]
        ),
        500: OpenApiResponse(
            description="Internal server error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Internal Error",
                    value={
                        "status": "error",
                        "message": "An error occurred. Please try again later.",
                        "error_code": "INTERNAL_ERROR"
                    }
                )
            ]
        )
    }
    )
    def get(self, request):
        places = TrendingPlace.objects.all()
        serializer = TrendingPlaceSerializer(places, many=True)
        return Response(serializer.data)
    
    @extend_schema(
    tags=['Places'],
    summary="Create New Place",
    description="Create a new trending place with optional fun facts.",
    request=TrendingPlaceCreateSerializer,
    responses={
        201: OpenApiResponse(
            description="Trending place created successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Trending place created successfully",
                        "data": {
                            "id": 5,
                            "name": "Niagara Falls",
                            "main": "https://cdn.com/niagara_main.jpg",
                            "fun_facts": [
                                {"id": 21, "slide": 1, "title": "Massive Water Flow", "desc": "Over 168,000 cubic meters of water per minute.", "photo": "https://cdn.com/funfact21.jpg"}
                            ]
                        }
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "status": "error",
                        "message": "Invalid data",
                        "errors": {
                            "name": ["This field is required."],
                            "main": ["Invalid URL or file."]
                        }
                    }
                )
            ]
        )
    }
    )
    def post(self, request):
        serializer = TrendingPlaceCreateSerializer(data=request.data)
        if serializer.is_valid():
            place = serializer.save()
            response_serializer = TrendingPlaceSerializer(place)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PlaceDetailView(APIView):
    def get_place(self, place_id):
        try:
            return TrendingPlace.objects.get(id=place_id)
        except TrendingPlace.DoesNotExist:
            return None
    @extend_schema(
    tags=['Places'],
    summary="Get Place Details",
    description="Retrieve a specific trending place along with all its fun facts.",
    responses={
        200: OpenApiResponse(
            description="Place details retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Place details retrieved successfully",
                        "data": {
                            "id": 5,
                            "name": "Niagara Falls",
                            "main": "https://cdn.com/niagara_main.jpg",
                            "fun_facts": [
                                {
                                    "id": 21,
                                    "slide": 1,
                                    "title": "Massive Water Flow",
                                    "desc": "Over 168,000 cubic meters of water per minute.",
                                    "photo": "https://cdn.com/funfact21.jpg"
                                }
                            ]
                        }
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Place not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found Example",
                    value={
                        "status": "error",
                        "message": "Place not found",
                        "errors": {"place": ["No place exists with the given ID."]}
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def get(self, request, place_id):
        place = self.get_place(place_id)
        if not place:
            return Response({"error": "Place not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TrendingPlaceSerializer(place)
        return Response(serializer.data)
    
    @extend_schema(
    tags=['Places'],
    summary="Update Place",
    description="Update a trending place by its ID.",
    request=TrendingPlaceCreateSerializer,
    responses={
        200: OpenApiResponse(
            description="Place updated successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Place updated successfully",
                        "data": {
                            "id": 5,
                            "name": "Niagara Falls",
                            "main": "https://cdn.com/niagara_main.jpg",
                            "fun_facts": [
                                {
                                    "id": 21,
                                    "slide": 1,
                                    "title": "Massive Water Flow",
                                    "desc": "Over 168,000 cubic meters of water per minute.",
                                    "photo": "https://cdn.com/funfact21.jpg"
                                }
                            ]
                        }
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "status": "error",
                        "message": "Invalid data",
                        "errors": {
                            "name": ["This field may not be blank."],
                            "main": ["Invalid URL."]
                        }
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Place not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "status": "error",
                        "message": "Place not found",
                        "errors": {"place": ["No place exists with the given ID."]}
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def put(self, request, place_id):
        place = self.get_place(place_id)
        if not place:
            return Response({"error": "Place not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = TrendingPlaceCreateSerializer(place, data=request.data)
        if serializer.is_valid():
            serializer.save()
            response_serializer = TrendingPlaceSerializer(place)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
    tags=['Places'],
    summary="Delete Place",
    description="Delete a place by its ID, along with all its associated fun facts.",
    responses={
        200: OpenApiResponse(
            description="Place deleted successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Place deleted successfully"
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Place not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "status": "error",
                        "message": "Place not found",
                        "errors": {"place": ["No place exists with the given ID."]}
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def delete(self, request, place_id):
        place = self.get_place(place_id)
        if not place:
            return Response({"error": "Place not found"}, status=status.HTTP_404_NOT_FOUND)
        place.delete()
        return Response(status=status.HTTP_200_OK)

class FunFactListCreateView(APIView):
    @extend_schema(
    tags=['Places'],
    summary="List Fun Facts",
    description="Retrieve all fun facts. Optionally filter by place using place ID.",
    parameters=[
        OpenApiParameter(
            name='place',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Filter fun facts by place ID',
            required=False,
            examples=[
                OpenApiExample(
                    "Place ID 1",
                    value=1,
                    description="Retrieve fun facts for place with ID 1"
                ),
                OpenApiExample(
                    "Place ID 2",
                    value=2,
                    description="Retrieve fun facts for place with ID 2"
                )
            ]
        )
    ],
    responses={
        200: OpenApiResponse(
            description="Fun facts retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "count": 2,
                        "data": [
                            {
                                "id": 1,
                                "slide": 1,
                                "title": "Amazing View",
                                "desc": "Beautiful view from the top of the mountain",
                                "photo": "https://cdn.com/funfact1.jpg",
                                "place": 1
                            },
                            {
                                "id": 2,
                                "slide": 2,
                                "title": "Local Food",
                                "desc": "Delicious local cuisine",
                                "photo": "https://cdn.com/funfact2.jpg",
                                "place": 1
                            }
                        ]
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def get(self, request):
        place_id = request.query_params.get('place', None)
        if place_id:
            fun_facts = FunFact.objects.filter(place_id=place_id)
        else:
            fun_facts = FunFact.objects.all()
        serializer = FunFactSerializer(fun_facts, many=True)
        return Response(serializer.data)
    
    @extend_schema(
    tags=['Places'],
    summary="Create Fun Fact",
    description="Add a new fun fact to a place. The fun fact is linked to a specific trending place.",
    request=FunFactCreateUpdateSerializer,
    responses={
        201: OpenApiResponse(
            description="Fun fact created successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Fun fact created successfully",
                        "data": {
                            "id": 5,
                            "slide": 1,
                            "title": "Hidden Waterfall",
                            "desc": "A beautiful waterfall tucked away in the forest",
                            "photo": "https://cdn.com/funfact5.jpg",
                            "place": 3
                        }
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "status": "error",
                        "message": "Validation failed",
                        "errors": {
                            "title": ["This field is required."],
                            "desc": ["This field is required."]
                        }
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def post(self, request):
        serializer = FunFactCreateUpdateSerializer(data=request.data)
        if serializer.is_valid():
            fun_fact = serializer.save()
            response_serializer = FunFactSerializer(fun_fact)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FunFactDetailView(APIView):
    def get_fun_fact(self, fact_id):
        try:
            return FunFact.objects.get(id=fact_id)
        except FunFact.DoesNotExist:
            return None
        
    @extend_schema(
    tags=['Places'],
    summary="Get Fun Fact",
    description="Retrieve a specific fun fact by its ID.",
    responses={
        200: OpenApiResponse(
            description="Fun fact retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Fun fact retrieved successfully",
                        "data": {
                            "id": 5,
                            "slide": 1,
                            "title": "Hidden Waterfall",
                            "desc": "A beautiful waterfall tucked away in the forest",
                            "photo": "https://cdn.com/funfact5.jpg",
                            "place": 3
                        }
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Fun fact not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "status": "error",
                        "message": "Fun fact not found",
                        "errors": {"fact_id": ["No fun fact exists with this ID."]}
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def get(self, request, fact_id):
        fun_fact = self.get_fun_fact(fact_id)
        if not fun_fact:
            return Response({"error": "Fun fact not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FunFactSerializer(fun_fact)
        return Response(serializer.data)
    
    @extend_schema(
    tags=['Places'],
    summary="Update Fun Fact",
    description="Update a specific fun fact by its ID.",
    request=FunFactCreateUpdateSerializer,
    responses={
        200: OpenApiResponse(
            description="Fun fact updated successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Fun fact updated successfully",
                        "data": {
                            "id": 5,
                            "slide": 1,
                            "title": "Hidden Waterfall (Updated)",
                            "desc": "An updated description of the waterfall",
                            "photo": "https://cdn.com/funfact5_updated.jpg",
                            "place": 3
                        }
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Fun fact not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found",
                    value={
                        "status": "error",
                        "message": "Fun fact not found",
                        "errors": {"fact_id": ["No fun fact exists with this ID."]}
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation error",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "status": "error",
                        "message": "Validation failed",
                        "errors": {
                            "title": ["This field may not be blank."],
                            "desc": ["This field may not be blank."]
                        }
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def put(self, request, fact_id):
        fun_fact = self.get_fun_fact(fact_id)
        if not fun_fact:
            return Response({"error": "Fun fact not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = FunFactCreateUpdateSerializer(fun_fact, data=request.data)
        if serializer.is_valid():
            serializer.save()
            response_serializer = FunFactSerializer(fun_fact)
            return Response(response_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
    tags=['Places'],
    summary="Delete Fun Fact",
    description="Delete a specific fun fact by its ID.",
    responses={
        200: OpenApiResponse(
            description="Fun fact deleted successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Fun fact deleted successfully"
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Fun fact not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    "Not Found Example",
                    value={
                        "status": "error",
                        "message": "Fun fact not found",
                        "errors": {"fact_id": ["No fun fact exists with this ID."]}
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def delete(self, request, fact_id):
        fun_fact = self.get_fun_fact(fact_id)
        if not fun_fact:
            return Response({"error": "Fun fact not found"}, status=status.HTTP_404_NOT_FOUND)
        fun_fact.delete()
        return Response(status=status.HTTP_200_OK)