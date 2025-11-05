from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from django.shortcuts import get_object_or_404
from .models import Budget, ExpenseCategory
from .serializers import (BudgetSerializer,ExpenseCategorySerializer,ExpenseCategoryListSerializer)

class BudgetView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user):
        try:
            return Budget.objects.get(user=user)
        except Budget.DoesNotExist:
            return None
    @extend_schema(
        tags=["Expenses"], 
        summary="Get user's budget",
        description="Retrieve the budget for the authenticated user.",
        responses={
            200: OpenApiResponse(
                description="Budget retrieved successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Budget found",
                        value={
                            "status": "success",
                            "message": "Budget retrieved successfully",
                            "data": {
                                "id": 1,
                                "user": 3,
                                "total_budget": 5000,
                                "spent": 1200,
                                "remaining": 3800
                            }
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Budget not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Not Found Example",
                        summary="No budget found for user",
                        value={
                            "status": "error",
                            "message": "No budget found",
                            "errors": {"budget": ["No budget exists for this user."]}
                        }
                    )
                ]
            )
        }
    )
    def get(self, request):
        budget = self.get_object(request.user)
        if budget is None:
            return Response({"error": "No budget found."},status=status.HTTP_404_NOT_FOUND)
        serializer = BudgetSerializer(budget)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Expenses"], 
        summary="Create budget",
        description="Create a new budget for the authenticated user.",
        request=BudgetSerializer,
        responses={
            201: OpenApiResponse(
                description="Budget created successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Budget created",
                        value={
                            "status": "success",
                            "message": "Budget created successfully",
                            "data": {
                                "id": 1,
                                "user": 3,
                                "total_budget": 50000.00,
                                "spent": 0,
                                "remaining": 50000.00
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Bad request or budget already exists",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Budget Exists Example",
                        summary="User already has a budget",
                        value={
                            "status": "error",
                            "message": "Budget already exists",
                            "errors": {"budget": ["User already has a budget."]}
                        }
                    ),
                    OpenApiExample(
                        name="Invalid Data Example",
                        summary="Invalid request data",
                        value={
                            "status": "error",
                            "message": "Invalid data",
                            "errors": {"total": ["This field is required."]}
                        }
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                name='Create Budget Request',
                summary='Example request body',
                value={'total_budget': 50000.00},
                request_only=True
            )
        ]
    )
    def post(self, request):
        if Budget.objects.filter(user=request.user).exists():
            return Response({"error": "Budget already exists."},status=status.HTTP_400_BAD_REQUEST)       
        serializer = BudgetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Expenses"], 
        summary="Update budget",
        description="Update budget fields for the authenticated user.",
        request=BudgetSerializer,
        responses={
            200: OpenApiResponse(
                description="Budget updated successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Budget updated",
                        value={
                            "status": "success",
                            "message": "Budget updated successfully",
                            "data": {
                                "id": 1,
                                "user": 3,
                                "total_budget": 60000.00,
                                "spent": 1500,
                                "remaining": 58500.00
                            }
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid request data",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Invalid Data Example",
                        summary="Request body invalid",
                        value={
                            "status": "error",
                            "message": "Invalid data",
                            "errors": {"total_budget": ["This field must be a positive number."]}
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Budget not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Not Found Example",
                        summary="No budget exists for the user",
                        value={
                            "status": "error",
                            "message": "No budget found",
                            "errors": {"budget": ["No budget exists for this user."]}
                        }
                    )
                ]
            )
        }
    )
    def patch(self, request):
        budget = self.get_object(request.user)
        if budget is None:
            return Response(
                {"error": "No budget found."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = BudgetSerializer(budget, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        tags=["Expenses"], 
        summary="Delete budget",
        description="Delete the authenticated user's budget.",
        responses={
            204: OpenApiResponse(
                description="Budget deleted successfully",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Success Example",
                        summary="Budget deleted",
                        value={
                            "status": "success",
                            "message": "Budget deleted successfully"
                        }
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Budget not found",
                response=OpenApiTypes.OBJECT,
                examples=[
                    OpenApiExample(
                        name="Not Found Example",
                        summary="No budget exists for the user",
                        value={
                            "status": "error",
                            "message": "No budget found",
                            "errors": {"budget": ["No budget exists for this user."]}
                        }
                    )
                ]
            )
        }
    )
    def delete(self, request):
        budget = self.get_object(request.user)
        if budget is None:
            return Response({"error": "No budget found."},status=status.HTTP_404_NOT_FOUND)
        budget.delete()
        return Response({"message": "Budget deleted successfully"},status=status.HTTP_204_NO_CONTENT)

class ExpenseCategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    tags=["Expenses"], 
    summary="List all expense categories",
    description="Retrieve all expense categories for the authenticated user.",
    responses={
        200: OpenApiResponse(
            description="Expense categories retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Success Example",
                    summary="List of expense categories",
                    value={
                        "status": "success",
                        "message": "Expense categories retrieved successfully",
                        "data": [
                            {"id": 1, "name": "Food"},
                            {"id": 2, "name": "Transport"},
                            {"id": 3, "name": "Entertainment"}
                        ]
                    }
                )
            ]
        )
    }
    )
    def get(self, request):
        categories = ExpenseCategory.objects.filter(user=request.user)
        serializer = ExpenseCategoryListSerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
    tags=["Expenses"], 
    summary="Create expense category",
    description="Create a new expense category. Budget must exist before creating categories.",
    request=ExpenseCategorySerializer,
    responses={
        201: OpenApiResponse(
            description="Expense category created successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Create Food Category",
                    summary="Food category created",
                    value={
                        "status": "success",
                        "message": "Expense category created successfully",
                        "data": {
                            "id": 1,
                            "category": "Food & Dining",
                            "allocated": 10000.00
                        }
                    }
                ),
                OpenApiExample(
                    name="Create Transport Category",
                    summary="Transport category created",
                    value={
                        "status": "success",
                        "message": "Expense category created successfully",
                        "data": {
                            "id": 2,
                            "category": "Transport",
                            "allocated": 5000.00
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Bad request or budget missing",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Budget Missing",
                    summary="User has no budget",
                    value={
                        "status": "error",
                        "message": "Please create a budget first.",
                        "errors": {"budget": ["No budget exists for this user."]}
                    }
                ),
                OpenApiExample(
                    name="Category Exists",
                    summary="Category already exists",
                    value={
                        "status": "error",
                        "message": "Category already exists.",
                        "errors": {"category": ["This category already exists."]}
                    }
                )
            ]
        )
    }
    )
    def post(self, request):
        try:
            budget = Budget.objects.get(user=request.user)
        except Budget.DoesNotExist:
            return Response({"error": "Please create a budget first."},status=status.HTTP_400_BAD_REQUEST)
        category = request.data.get('category')
        if ExpenseCategory.objects.filter(user=request.user, category=category).exists():
            return Response({"error": "Category already exists."},status=status.HTTP_400_BAD_REQUEST)
        serializer = ExpenseCategorySerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user, budget=budget)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ExpenseCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user, pk):
        return get_object_or_404(ExpenseCategory, user=user, pk=pk)
    
    @extend_schema(
    tags=["Expenses"],
    summary="Get category detail",
    description="Retrieve detailed information about a specific expense category.",
    responses={
        200: OpenApiResponse(
            description="Expense category retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Success Example",
                    summary="Category details",
                    value={
                        "status": "success",
                        "message": "Expense category retrieved successfully",
                        "data": {
                            "id": 1,
                            "category": "Food & Dining",
                            "allocated": 10000.00
                        }
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Category not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Not Found Example",
                    summary="Invalid category ID",
                    value={
                        "status": "error",
                        "message": "Category not found",
                        "errors": {"category_id": ["No category exists with this ID."]}
                    }
                )
            ]
        )
    }
    )
    def get(self, request, pk):
        category = self.get_object(request.user, pk)
        serializer = ExpenseCategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
    tags=["Expenses"],
    summary="Update category",
    description="Update category fields for a specific expense category.",
    request=ExpenseCategorySerializer,
    responses={
        200: OpenApiResponse(
            description="Category updated successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Success Example",
                    summary="Updated category",
                    value={
                        "status": "success",
                        "message": "Expense category updated successfully",
                        "data": {
                            "id": 1,
                            "category": "Food & Dining",
                            "allocated": 12000.00
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid data provided",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Invalid Data Example",
                    summary="Validation error",
                    value={
                        "status": "error",
                        "message": "Invalid data",
                        "errors": {
                            "allocated": ["Ensure this value is greater than or equal to 0."]
                        }
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Category not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Not Found Example",
                    summary="Invalid category ID",
                    value={
                        "status": "error",
                        "message": "Category not found",
                        "errors": {"category_id": ["No category exists with this ID."]}
                    }
                )
            ]
        )
    }
    )
    def patch(self, request, pk):
        category = self.get_object(request.user, pk)
        serializer = ExpenseCategorySerializer(category, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
    tags=["Expenses"],
    summary="Delete category",
    description="Delete a specific expense category for the authenticated user.",
    responses={
        204: OpenApiResponse(
            description="Category deleted successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Success Example",
                    summary="Category deleted",
                    value={
                        "status": "success",
                        "message": "Expense category deleted successfully"
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Category not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Not Found Example",
                    summary="Invalid category ID",
                    value={
                        "status": "error",
                        "message": "Category not found",
                        "errors": {"category_id": ["No category exists with this ID."]}
                    }
                )
            ]
        )
    }
    )
    def delete(self, request, pk):
        category = self.get_object(request.user, pk)
        category.delete()
        return Response({"message": "Category deleted successfully"},status=status.HTTP_204_NO_CONTENT)

class BudgetSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    tags=["Expenses"],
    summary="Get budget summary",
    description="Retrieve a comprehensive summary",
    responses={
        200: OpenApiResponse(
            description="Budget summary retrieved successfully",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Success Example",
                    summary="Budget summary response",
                    value={
                        "status": "success",
                        "message": "Budget summary retrieved successfully",
                        "data": {
                            "total": 50000.00,
                            "total_allocated": 25000.00,
                            "remaining_budget": 25000.00,
                            "percentage_allocated": 50.0,
                            "percentage_remaining": 50.0,
                            "total_categories": 2,
                            "categories": [
                                {"id": 1, "category": "Food & Dining", "allocated": 10000.00},
                                {"id": 2, "category": "Transport", "allocated": 15000.00}
                            ]
                        }
                    }
                )
            ]
        ),
        404: OpenApiResponse(
            description="Budget not found",
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    name="Not Found Example",
                    summary="No budget exists for the user",
                    value={
                        "status": "error",
                        "message": "No budget found",
                        "errors": {"budget": ["No budget exists for this user."]}
                    }
                )
            ]
        )
    }
    )
    def get(self, request):
        try:
            budget = Budget.objects.get(user=request.user)
        except Budget.DoesNotExist:
            return Response({"error": "No budget found."},status=status.HTTP_404_NOT_FOUND)
        
        categories = ExpenseCategory.objects.filter(user=request.user)
        total_allocated = sum(cat.allocated for cat in categories)
        remaining_budget = budget.total - total_allocated
        total_categories = categories.count()
        percentage_allocated = round((total_allocated / budget.total) * 100, 2) if budget.total else 0
        percentage_remaining = round((remaining_budget / budget.total) * 100, 2) if budget.total else 0        
        serializer = ExpenseCategoryListSerializer(categories, many=True)         
        return Response({"total": float(budget.total),"total_allocated": float(total_allocated),"remaining_budget": float(remaining_budget),"percentage_allocated": percentage_allocated,"percentage_remaining": percentage_remaining,"total_categories": total_categories,"categories": serializer.data}, status=status.HTTP_200_OK)