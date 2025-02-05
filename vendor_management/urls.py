from django.urls import path
from . import views

urlpatterns = [    
            path('handle_vendor_form/', views.handle_vendor_form, name='handle_vendor_form'),
            path('send_vendor_emails/', views.send_vendor_emails, name='send_vendor_emails'),
        ]

