from rest_framework import serializers
from account.models import User

class UserRegistrationSerializer(serializers.ModelSerializer):
    password2=serializers.CharField(style={'input_type':'password'},write_only=True)
    class Meta:
        model=User
        fields=["email","name","tc","phone_number","password","password2"]
        extra_kwargs={
            'password':{'write_only':True}
        }
    
    def validate(self,data):
        password=data.get('password')
        password2=data.get('password2')
        if password != password2:
            raise serializers.ValidationError("Password and confirm password doesn't match")
        return data

    def create(self,validate_data):
        return User.object.create_user(**validate_data)
    
class UserLoginSerializer(serializers.ModelSerializer):
    email=serializers.EmailField(max_length=255)
    class Meta:
        model=User
        fields=["email","password"]
        extra_kwargs={
            'password':{'write_only':True}
        }
    
    def validate(self,data):
        password=data.get('password')
        password2=data.get('password2')
        if password != password2:
            raise serializers.ValidationError("Password and confirm password doesn't match")
        return data

    def create(self,validate_data):
        return User.object.create_user(**validate_data)