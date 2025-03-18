from django.urls import path
from . import views

urlpatterns = [    
        path('vendor_management/', views.handle_vendor_form, name='handle_vendor_form'),
        path('okay', views.send_vendor_emails, name='send_vendor_emails'),
        path('search_vendor_data/', views.search_vendor_data, name='search_vendor_data'),
        path('sort_vendor_data/', views.sort_vendor_data, name='sort_vendor_data'),
        path('vendor_message_template/', views.vendor_message_template, name='vendor_message_template'),  
        path('fetch-columns-vendor/', views.fetch_columns_vendor, name='fetch_columns_vendor'),  
        # path('vendor_management/', views.vendor_view, name='vendor_view'),
        ]